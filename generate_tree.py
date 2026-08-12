import json
import pandas as pd
import requests
import io
import re
from datetime import datetime, timedelta

SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"

def parse_date_value(val):
    """自動將 Excel 日期序列號 (如 45665) 或正常日期字串轉為 YYYY-MM-DD"""
    if pd.isna(val) or str(val).strip() in ['', '-', 'nan', 'NaN', 'None', 'null']:
        return '-'
    val_str = str(val).replace('🔴', '').strip()
    try:
        num = float(val_str)
        if 10000 <= num <= 60000:
            base_date = datetime(1899, 12, 30)
            dt = base_date + timedelta(days=num)
            return dt.strftime('%Y-%m-%d')
    except ValueError:
        pass
    return val_str

def extract_number(ear_str):
    """擷取耳號純數字 (例如 DD26008 -> 26008)"""
    nums = re.findall(r'\d+', str(ear_str))
    if nums:
        return int(nums[0])
    return None

def fetch_and_parse():
    print("🚀 啟動兩軸線獨立解析：鎖定「個體出生背景」與「當胎繁殖績效」...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid=0"
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = 'utf-8-sig'
        if res.status_code != 200:
            print(f"❌ 下載失敗: {res.status_code}")
            return
        df = pd.read_csv(io.StringIO(res.text))
        df.columns = [str(c).replace('\n', '').replace('\r', '').strip() for c in df.columns]
        df = df.dropna(how='all')
    except Exception as e:
        print(f"❌ 下載錯誤: {e}")
        return

    def get_exact_col(exact_keywords):
        for kw in exact_keywords:
            for col in df.columns:
                if col.strip().lower() == kw.lower():
                    return col
        for kw in exact_keywords:
            for col in df.columns:
                if kw.lower() in col.lower():
                    return col
        return None

    col_ear = get_exact_col(['Nombor Telinga 母豬耳號 Number', '母豬耳號', '耳號', 'Ear Tag']) or df.columns[2]
    col_sex = get_exact_col(['Sex', '性別'])
    col_parity = get_exact_col(['Parity', '胎次'])
    col_mate = get_exact_col(['Jantan 配種公豬 Boar', '配種公豬', '當胎配種公'])
    col_breed = get_exact_col(['Breed', '品種'])
    
    col_birth_date = get_exact_col(['DOB', '出生日期', '個體生日'])
    col_farrow_date = get_exact_col(['Tarikh Farrowing date / Tarikh beranak (m/d)', 'Farrowing date', '分娩日期'])
    col_mating_date = get_exact_col(['Tarikh Kahwin 配種日期 Date(YMD)', 'Mating Date', '配種日期'])
    
    col_spi = get_exact_col(['SPI'])
    col_mli = get_exact_col(['MLI'])
    col_tsi = get_exact_col(['TSI'])
    col_total_born = get_exact_col(['Total born 同胎總生產數', '總生產'])
    col_born_alive = get_exact_col(['Born alive 同胎次活胎數量', '活胎'])
    col_weaning = get_exact_col(['Weaning 同胎次離乳數量', '離乳'])
    col_weaning_wt = get_exact_col(['weaning weight 同胎次離乳平均重', '均重'])

    col_sire_name = get_exact_col(['Sire Name美系父親名', 'Sire Name 美系父親名'])
    col_dam_name  = get_exact_col(['Dam Name美系母親名', 'Dam Name 美系母親名'])

    col_notch_start = get_exact_col(['Ear Notch Breeder (start)', 'Notch Breeder (start)'])
    col_notch_end   = get_exact_col(['Ear Notch Breeder (end)', 'Notch Breeder (end)'])

    # ----------------------------------------------------
    # PASS 1: 建立母豬生產同胎與耳號範圍總對照表 (Litter Origin Map)
    # ----------------------------------------------------
    litter_map = []

    for _, row in df.iterrows():
        farrow_d = parse_date_value(row.get(col_farrow_date, ''))
        mate_boar = str(row.get(col_mate, '')).strip() if pd.notna(row.get(col_mate)) else '-'
        sire_n = str(row.get(col_sire_name, '')).strip() if (col_sire_name and pd.notna(row.get(col_sire_name))) else '-'
        dam_n  = str(row.get(col_dam_name, '')).strip() if (col_dam_name and pd.notna(row.get(col_dam_name))) else '-'
        dam_ear_val = str(row.get(col_ear, '')).strip().upper() if pd.notna(row.get(col_ear)) else ''

        if col_notch_start and col_notch_end:
            start_num = extract_number(row.get(col_notch_start, ''))
            end_num   = extract_number(row.get(col_notch_end, ''))
            if start_num is not None and end_num is not None and farrow_d != '-':
                litter_map.append({
                    'start': min(start_num, end_num),
                    'end': max(start_num, end_num),
                    'origin_dob': farrow_d,        # 軸線一：本場個體的真實出生日
                    'origin_dam': dam_ear_val,     # 母親
                    'origin_sire': mate_boar,      # 父親
                    'origin_sire_sire': sire_n,    # 祖父
                    'origin_sire_dam': dam_n       # 祖母
                })

    # ----------------------------------------------------
    # PASS 2: 組裝每筆紀錄，徹底分離「個體生日」與「當胎分娩日」
    # ----------------------------------------------------
    pedigree_data = []

    for idx, row in df.iterrows():
        ear = str(row.get(col_ear, '')).strip() if pd.notna(row.get(col_ear)) else ""
        if not ear or ear.lower() in ['nan', 'none', '-', '', 'null']:
            continue

        breed = str(row.get(col_breed, '')).strip().upper() if pd.notna(row.get(col_breed)) else "D"
        if 'LY' in ear.upper(): breed = 'LY'

        def get_v(col_name):
            if col_name and pd.notna(row.get(col_name)):
                val = str(row.get(col_name)).strip()
                return val if val.lower() not in ['nan', 'none', ''] else '-'
            return '-'

        def get_date_v(col_name):
            if col_name and pd.notna(row.get(col_name)):
                return parse_date_value(row.get(col_name))
            return '-'

        raw_dob = get_date_v(col_birth_date)
        farrow_dob = get_date_v(col_farrow_date) # 軸線二：這頭母豬當次產房分娩日

        individual_dob = '-'
        inferred_sire = '-'
        inferred_dam = '-'
        inferred_sire_sire = '-'
        inferred_sire_dam = '-'

        # 軸線一判斷：美國原廠 DOB > 本場同胎耳號範圍反推 DOB
        if breed != 'LY' and raw_dob != '-':
            individual_dob = raw_dob
        else:
            ear_num = extract_number(ear)
            if ear_num is not None:
                for litter in litter_map:
                    if litter['start'] <= ear_num <= litter['end']:
                        individual_dob = litter['origin_dob']
                        inferred_dam = litter['origin_dam']
                        inferred_sire = litter['origin_sire']
                        inferred_sire_sire = litter['origin_sire_sire']
                        inferred_sire_dam = litter['origin_sire_dam']
                        break

        sire_sire_val = inferred_sire_sire if inferred_sire_sire != '-' else get_v(col_sire_name)
        sire_dam_val  = inferred_sire_dam if inferred_sire_dam != '-' else get_v(col_dam_name)

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": get_v(col_sex),
            "parity": get_v(col_parity),
            "mate": get_v(col_mate),             # 軸線二：這頭母豬當次配的公豬
            "birth_date": individual_dob,        # 軸線一：個體真實出生日 (恆定唯一，算 Age 用)
            "dob": farrow_dob,                   # 軸線二：這頭母豬當次產房分娩日 (算歷胎用)
            "spi": get_v(col_spi),
            "mli": get_v(col_mli),
            "tsi": get_v(col_tsi),
            "total_born": get_v(col_total_born),
            "born_alive": get_v(col_born_alive),
            "weaning": get_v(col_weaning),
            "weaning_wt": get_v(col_weaning_wt),
            "sire_sire": sire_sire_val,
            "sire_dam": sire_dam_val,
            "dam_sire": get_v(get_exact_col(['Sire美系父親名(外公)', '外公'])),
            "dam_dam": get_v(get_exact_col(['Dam Name美系母親名(外婆)', '外婆'])),
            "gen1_sire": inferred_sire if inferred_sire != '-' else get_v(col_mate),
            "gen1_dam": inferred_dam if inferred_dam != '-' else get_v(col_ear),
            "details": {}
        }

        for k, v in row.items():
            key_str = str(k).strip()
            if pd.isna(v):
                entry["details"][key_str] = ""
            else:
                val_str = str(v).strip()
                if '日期' in key_str or 'date' in key_str.lower() or 'dob' in key_str.lower():
                    entry["details"][key_str] = parse_date_value(val_str)
                else:
                    entry["details"][key_str] = val_str

        pedigree_data.append(entry)

    print(f"🎉 數據拆軸解析完成！共處理 {len(pedigree_data)} 筆紀錄。")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fetch_and_parse()
