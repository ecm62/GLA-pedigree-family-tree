import json
import pandas as pd
import requests
import io
import re

SPREADSHEET_ID = "1MlhcSXitL_jWYvXVfmo6bQfQqDPIDgUt0VGIZVaB5aw"

GID_US_ORIGIN = "1267648620"  # 美國原始種源數據 (4 位數純種生日 DOB)
GID_COMBINED = "84920994"     # 合併報表(配種+產房) (5 位數自繁區間 KN~KO 與分娩日 BJ)
GID_MAIN = "0"                # 主表 / 育種家族階層清單

def fetch_sheet_csv(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        res.encoding = 'utf-8-sig'
        if res.status_code == 200:
            df = pd.read_csv(io.StringIO(res.text))
            df.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df.columns]
            return df.dropna(how='all')
    except Exception as e:
        print(f"❌ 讀取 GID {gid} 失敗: {e}")
    return pd.DataFrame()

def extract_number(tag_str):
    nums = re.findall(r'\d+', str(tag_str))
    return int(nums[0]) if nums else None

def get_prefix(tag_str):
    chars = re.findall(r'^[A-Za-z]+', str(tag_str))
    return chars[0].upper() if chars else ""

def fetch_and_parse():
    print("🚀 正在從多個 Google Sheets 分頁聯合抓取出生日、血統與淘汰/死亡狀態數據...")
    
    # 1. 主表
    df_main = fetch_sheet_csv(GID_MAIN)
    if df_main.empty:
        print("❌ 主表資料為空！")
        return

    # 2. 4 位數純種美系原種 DOB (美國原始種源數據)
    df_us = fetch_sheet_csv(GID_US_ORIGIN)
    us_dob_map = {}
    if not df_us.empty:
        ear_col_us = next((c for c in df_us.columns if '耳號' in c or 'Ear' in c), df_us.columns[2])
        dob_col_us = next((c for c in df_us.columns if 'DOB' in c.upper() or '出生' in c or '生日' in c), None)
        if ear_col_us and dob_col_us:
            for _, r in df_us.iterrows():
                e = str(r.get(ear_col_us, '')).strip().upper()
                d = str(r.get(dob_col_us, '')).strip()
                if e and d and d.lower() not in ['nan', 'none', '-', '']:
                    us_dob_map[e] = d

    # 3. 5 位數自繁區間對照 (合併報表 Col KN ~ Col KO 與 Col BJ 分娩日)
    df_comb = fetch_sheet_csv(GID_COMBINED)
    notch_ranges = []
    if not df_comb.empty:
        col_farrow = next((c for c in df_comb.columns if '分娩日' in c or 'Farrowing date' in c), None)
        col_start = next((c for c in df_comb.columns if 'Breeder (start)' in c or 'Breeder(start)' in c or 'Ear Notch Breeder (start)' in c), None)
        col_end = next((c for c in df_comb.columns if 'Breeder (end)' in c or 'Breeder(end)' in c or 'Ear Notch Breeder (end)' in c), None)
        
        if col_farrow and col_start and col_end:
            for _, r in df_comb.iterrows():
                f_date = str(r.get(col_farrow, '')).strip()
                s_tag = str(r.get(col_start, '')).strip()
                e_tag = str(r.get(col_end, '')).strip()
                
                if f_date and f_date.lower() not in ['nan', 'none', '-', ''] and s_tag and e_tag:
                    s_num = extract_number(s_tag)
                    e_num = extract_number(e_tag)
                    prefix = get_prefix(s_tag)
                    if s_num is not None and e_num is not None:
                        notch_ranges.append({
                            'prefix': prefix,
                            'start': min(s_num, e_num),
                            'end': max(s_num, e_num),
                            'dob': f_date
                        })

    def find_col(df, keywords):
        for kw in keywords:
            for col in df.columns:
                if kw.lower() in col.lower():
                    return col
        return None

    col_ear = find_col(df_main, ['母豬耳號', '耳號', 'Ear Tag', 'Ear', 'C']) or df_main.columns[2]
    col_sex = find_col(df_main, ['Sex', '性別'])
    col_parity = find_col(df_main, ['胎次', 'Parity'])
    col_mate = find_col(df_main, ['當胎配種公', '配種公豬', '當胎', '配種公', 'Mate', 'Sire'])
    col_breed = find_col(df_main, ['Breed', '品種', '品系', '品'])
    col_mating_date = find_col(df_main, ['配種日期', '配種日', 'Mating Date', 'Tarikh Kahwin', 'Kahwin'])
    col_farrow_date = find_col(df_main, ['分娩日期', '分娩日', 'farrowing date', '產房日期', 'dob'])
    col_status = find_col(df_main, ['狀態', 'Status', '淘汰原因', '離場原因', '淘汰', '死亡'])

    pedigree_data = []
    for _, row in df_main.iterrows():
        ear = str(row.get(col_ear, '')).strip() if pd.notna(row.get(col_ear)) else ""
        if not ear or ear.lower() in ['nan', 'none', '-', '', 'null']:
            continue
        
        ear_upper = ear.upper()
        breed = str(row.get(col_breed, '')).strip().upper() if pd.notna(row.get(col_breed)) else "D"
        if 'LY' in ear_upper: breed = 'LY'
        elif 'Y' in ear_upper and breed == 'D': breed = 'Y'
        elif 'L' in ear_upper and breed == 'D': breed = 'L'

        def get_v(col_name):
            if col_name and pd.notna(row.get(col_name)):
                val = str(row.get(col_name)).strip()
                return val if val.lower() not in ['nan', 'none', ''] else '-'
            return '-'

        # 🌟 精準雙軌出生日搜尋
        birth_date_val = '-'
        if breed == 'LY' or 'LY' in ear_upper:
            birth_date_val = '-'
        elif ear_upper in us_dob_map:
            birth_date_val = us_dob_map[ear_upper]
        else:
            ear_num = extract_number(ear_upper)
            ear_pre = get_prefix(ear_upper)
            if ear_num is not None:
                for nr in notch_ranges:
                    if (not ear_pre or not nr['prefix'] or ear_pre == nr['prefix']) and (nr['start'] <= ear_num <= nr['end']):
                        birth_date_val = nr['dob']
                        break
            
            if birth_date_val == '-':
                main_dob_col = find_col(df_main, ['DOB', '出生日期', '生日'])
                if main_dob_col and pd.notna(row.get(main_dob_col)):
                    v = str(row.get(main_dob_col)).strip()
                    if v and v.lower() not in ['nan', 'none', '-', '']:
                        birth_date_val = v

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": get_v(col_sex),
            "parity": get_v(col_parity),
            "mate": get_v(col_mate),
            "birth_date": birth_date_val,
            "mating_date": get_v(col_mating_date),
            "dob": get_v(col_farrow_date),
            "status": get_v(col_status),
            "spi": get_v(find_col(df_main, ['SPI'])),
            "mli": get_v(find_col(df_main, ['MLI'])),
            "tsi": get_v(find_col(df_main, ['TSI'])),
            "total_born": get_v(find_col(df_main, ['Total born', 'Total', '總生產', '總生'])),
            "born_alive": get_v(find_col(df_main, ['Born alive', 'Born', '活胎'])),
            "weaning": get_v(find_col(df_main, ['Weaning', '離乳'])),
            "mother_wt": get_v(find_col(df_main, ['mother total', '生育重'])),
            "weaning_wt": get_v(find_col(df_main, ['均重', 'weight'])),
            "tnb": get_v(find_col(df_main, ['TNB'])),
            "nba": get_v(find_col(df_main, ['NBA'])),
            "lteat": get_v(find_col(df_main, ['lteat', '左乳'])),
            "rteat": get_v(find_col(df_main, ['rteat', '右乳'])),
            "sire_sire": get_v(find_col(df_main, ['Sire美系第0代父親名(祖父)', 'Sire 美系第0代父親名(祖父)', '祖父'])),
            "sire_dam": get_v(find_col(df_main, ['Dam Name美系第0代母親名(祖母)', 'Dam Name 美系第0代母親名(祖母)', '祖母'])),
            "dam_sire": get_v(find_col(df_main, ['Sire美系第0代父親名(外公)', 'Sire 美系第0代父親名(外公)', '外公'])),
            "dam_dam": get_v(find_col(df_main, ['Dam Name美系第0代母親名(外婆)', 'Dam Name 美系第0代母親名(外婆)', '外婆'])),
            "gen1_sire": get_v(find_col(df_main, ['第一代公', '1st Sire'])),
            "gen1_dam": get_v(find_col(df_main, ['第一代母', '1st Dam'])),
            "details": {str(k).strip(): (str(v).strip() if pd.notna(v) else "") for k, v in row.items()}
        }

        pedigree_data.append(entry)

    print(f"🎉 數據解析完成！共處理 {len(pedigree_data)} 筆紀錄。")
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)
    print("✅ 成功寫入 data.json")

if __name__ == "__main__":
    fetch_and_parse()
