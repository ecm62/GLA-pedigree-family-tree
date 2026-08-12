import json
import pandas as pd
import requests
import io
import re
from datetime import datetime, timedelta

SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"

def parse_date_value(val):
    """自動將 Excel 序列號 (如 45280) 或正常日期字串統一轉為 YYYY-MM-DD"""
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
    """擷取耳號中的純數字做範圍比對 (例如 DD26001 -> 26001)"""
    nums = re.findall(r'\d+', str(ear_str))
    if nums:
        return int(nums[0])
    return None

def fetch_and_parse():
    print("🚀 開始抓取 Google Sheet 資料並執行自產種豬同胎耳號範圍 DOB 追溯...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 嘗試抓取主頁面與育種分頁
    gids = ["0", "1821811808", "803517616"] 
    df_list = []
    
    for gid in gids:
        url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
        try:
            res = requests.get(url, headers=headers, timeout=12)
            res.encoding = 'utf-8-sig'
            if res.status_code == 200:
                temp_df = pd.read_csv(io.StringIO(res.text))
                temp_df.columns = [str(c).replace('\n', '').replace('\r', '').strip() for c in temp_df.columns]
                df_list.append(temp_df)
        except Exception as e:
            continue

    if not df_list:
        print("❌ 無法取得任何試算表分頁資料")
        return

    df = pd.concat(df_list, ignore_index=True).dropna(how='all')

    def find_col(keywords):
        for kw in keywords:
            for col in df.columns:
                if kw.lower() in col.lower():
                    return col
        return None

    col_ear = find_col(['耳號', 'Ear Tag', 'Ear']) or df.columns[2]
    col_sex = find_col(['Sex', '性別'])
    col_parity = find_col(['胎次', 'Parity'])
    col_mate = find_col(['當胎', '配種公'])
    col_breed = find_col(['Breed', '品種'])
    
    col_birth_date = find_col(['DOB', '出生日期', '個體生日'])
    col_farrow_date = find_col(['farrowing date', '分娩日期', '產房日期'])
    
    col_spi = find_col(['SPI'])
    col_mli = find_col(['MLI'])
    col_tsi = find_col(['TSI'])
    col_total_born = find_col(['Total', '總生產'])
    col_born_alive = find_col(['Born', '活胎'])
    col_weaning = find_col(['Weaning', '離乳'])
    col_weaning_wt = find_col(['均重', 'weight'])

    col_sire_sire = find_col(['Sire美系父親名(祖父)', 'sire_sire', '祖父'])
    col_sire_dam  = find_col(['Dam Name美系母親名(祖母)', 'sire_dam', '祖母'])
    col_dam_sire  = find_col(['Sire美系父親名(外公)', 'dam_sire', '外公'])
    col_dam_dam   = find_col(['Dam Name美系母親名(外婆)', 'dam_dam', '外婆'])
    col_gen1_sire = find_col(['第一代公', '1st Sire', '父親'])
    col_gen1_dam  = find_col(['第一代母', '1st Dam', '母親'])

    col_notch_start = find_col(['Ear Notch Breeder (start)', 'Notch Breeder (start)', '起始耳號', 'Ear Notch (start)'])
    col_notch_end   = find_col(['Ear Notch Breeder (end)', 'Notch Breeder (end)', '結束耳號', 'Ear Notch (end)'])

    # 建立自產同胎耳號對照地圖 (Litter Range Map)
    litter_dob_map = []
    
    for _, row in df.iterrows():
        farrow_d = parse_date_value(row.get(col_farrow_date, ''))
        if farrow_d != '-':
            start_val = extract_number(row.get(col_notch_start, '')) if col_notch_start else None
            end_val = extract_number(row.get(col_notch_end, '')) if col_notch_end else None
            
            if start_val is not None and end_val is not None:
                litter_dob_map.append({
                    'start': min(start_val, end_val),
                    'end': max(start_val, end_val),
                    'dob': farrow_d,
                    'sire': str(row.get(col_mate, '')).strip(),
                    'dam': str(row.get(col_ear, '')).strip()
                })

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
        farrow_dob = get_date_v(col_farrow_date)
        
        computed_dob = '-'
        inferred_sire = '-'
        inferred_dam = '-'

        if breed != 'LY' and raw_dob != '-':
            computed_dob = raw_dob
        else:
            # 🌟 核心反推：若 DOB 為空，使用同胎耳號範圍抓出真實分娩日 (DOB)
            ear_num = extract_number(ear)
            if ear_num is not None:
                for litter in litter_dob_map:
                    if litter['start'] <= ear_num <= litter['end']:
                        computed_dob = litter['dob']
                        inferred_sire = litter['sire']
                        inferred_dam = litter['dam']
                        break

        gen1_sire_val = get_v(col_gen1_sire)
        gen1_dam_val = get_v(col_gen1_dam)

        if gen1_sire_val == '-' and inferred_sire != '-': gen1_sire_val = inferred_sire
        if gen1_dam_val == '-' and inferred_dam != '-': gen1_dam_val = inferred_dam

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": get_v(col_sex),
            "parity": get_v(col_parity),
            "mate": get_v(col_mate),
            "birth_date": computed_dob,  # 填入反推成功之同胎分娩日
            "dob": farrow_dob,
            "spi": get_v(col_spi),
            "mli": get_v(col_mli),
            "tsi": get_v(col_tsi),
            "total_born": get_v(col_total_born),
            "born_alive": get_v(col_born_alive),
            "weaning": get_v(col_weaning),
            "weaning_wt": get_v(col_weaning_wt),
            "sire_sire": get_v(col_sire_sire),
            "sire_dam": get_v(col_sire_dam),
            "dam_sire": get_v(col_dam_sire),
            "dam_dam": get_v(col_dam_dam),
            "gen1_sire": gen1_sire_val,
            "gen1_dam": gen1_dam_val,
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

    print(f"🎉 數據追溯解析完成！共處理 {len(pedigree_data)} 筆紀錄，自產種豬耳號反推 DOB 已完成。")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fetch_and_parse()
