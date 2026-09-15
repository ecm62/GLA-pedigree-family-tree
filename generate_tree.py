import json
import pandas as pd
import requests
import io
import re

SPREADSHEET_ID = "1MlhcSXitL_jWYvXVfmo6bQfQqDPIDgUt0VGIZVaB5aw"

GID_MAIN = "0"                 # 📊 育種_家族階層清單 (包含 Col L: DOD/淘汰日期)
GID_US_ORIGIN = "1267648620"   # 美國原始種源數據 (4 位數純種生日)
GID_COMBINED = "84920994"      # 合併報表(配種+產房) (留種區間 KN~KO 與分娩日 BJ)

def fetch_sheet_csv(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
        res.encoding = 'utf-8-sig'
        if res.status_code == 200:
            return res.text
    except Exception as e:
        print(f"❌ 讀取 GID {gid} 失敗: {e}")
    return ""

def extract_number(tag_str):
    nums = re.findall(r'\d+', str(tag_str))
    return int(nums[0]) if nums else None

def get_prefix(tag_str):
    chars = re.findall(r'^[A-Za-z]+', str(tag_str))
    return chars[0].upper() if chars else ""

def format_tag(prefix, num, orig_len):
    num_str = str(num).zfill(orig_len)
    return f"{prefix}{num_str}"

def find_col(df, keywords):
    for kw in keywords:
        for col in df.columns:
            if kw.lower() in col.lower():
                return col
    return None

def fetch_and_parse():
    print("🚀 正在從 Google Sheets 主表掃描血統與 Col L (DOD/淘汰日期)...")
    
    raw_main_csv = fetch_sheet_csv(GID_MAIN)
    if not raw_main_csv:
        print("❌ 主表資料為空！")
        return

    df_main = pd.read_csv(io.StringIO(raw_main_csv))
    df_main.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df_main.columns]

    # 1. 鎖定耳號欄位與 Col L (DOD/淘汰日期)
    col_ear = find_col(df_main, ['母豬耳號', '耳號', 'Ear Tag', 'Ear'])
    if not col_ear and len(df_main.columns) >= 7:
        col_ear = df_main.columns[6] # Col G 通常為耳號

    col_dod = None
    for c in df_main.columns:
        c_clean = c.upper()
        if 'DOD' in c_clean or '淘汰日期' in c or '死亡日期' in c:
            col_dod = c
            break
    if not col_dod and len(df_main.columns) >= 12:
        col_dod = df_main.columns[11] # 第 12 欄 (索引 11，即 Col L)

    print(f"📌 耳號鎖定欄位: [{col_ear}]")
    print(f"📌 淘汰死亡鎖定欄位 (Col L): [{col_dod}]")

    col_sex = find_col(df_main, ['Sex', '性別'])
    col_parity = find_col(df_main, ['胎次', 'Parity'])
    col_mate = find_col(df_main, ['當胎配種公', '配種公豬', '當胎', '配種公'])
    col_breed = find_col(df_main, ['Breed', '品種', '品系'])
    col_mating_date = find_col(df_main, ['配種日期', '配種日', 'Mating Date'])
    col_farrow_date = find_col(df_main, ['當胎分娩日', '分娩日期', '分娩日'])
    col_dob = find_col(df_main, ['DOB出生日期', 'DOB', '出生日期', '生日'])

    death_map = {} # 存放耳號對應的死亡字串，例如 { "D1405": "2024-04-11 ⚫ (Die)" }

    # 2. 4 位數美系純種原種生日對照
    raw_us_csv = fetch_sheet_csv(GID_US_ORIGIN)
    us_dob_map = {}
    if raw_us_csv:
        df_us = pd.read_csv(io.StringIO(raw_us_csv))
        df_us.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df_us.columns]
        ear_col_us = next((c for c in df_us.columns if '耳號' in c or 'Ear' in c), None)
        dob_col_us = next((c for c in df_us.columns if 'DOB' in c.upper() or '出生' in c or '生日' in c), None)
        if ear_col_us and dob_col_us:
            for _, r in df_us.iterrows():
                e = str(r.get(ear_col_us, '')).strip().upper()
                d = str(r.get(dob_col_us, '')).strip()
                if e and d and d.lower() not in ['nan', 'none', '-', '']:
                    us_dob_map[e] = d.replace('/', '-')

    # 3. 合併報表耳號區間
    raw_comb_csv = fetch_sheet_csv(GID_COMBINED)
    notch_ranges = []
    registered_young_pigs = {}

    if raw_comb_csv:
        df_comb = pd.read_csv(io.StringIO(raw_comb_csv))
        clean_cols = {c: re.sub(r'\s+', ' ', str(c)).strip() for c in df_comb.columns}
        col_farrow = next((orig for orig, cl in clean_cols.items() if '分娩日' in cl or 'farrowing date' in cl.lower()), None)
        col_dam = next((orig for orig, cl in clean_cols.items() if '母豬耳號' in cl or 'nombor telinga' in cl.lower()), None)
        col_sire = next((orig for orig, cl in clean_cols.items() if '配種公豬' in cl or 'boar mated' in cl.lower()), None)
        col_start = next((orig for orig, cl in clean_cols.items() if 'breeder (start)' in cl.lower() or 'breeder(start)' in cl.lower()), None)
        col_end = next((orig for orig, cl in clean_cols.items() if 'breeder (end)' in cl.lower() or 'breeder(end)' in cl.lower()), None)

        if col_farrow and col_start and col_end:
            for _, r in df_comb.iterrows():
                f_date = str(r.get(col_farrow, '')).strip().replace('/', '-')
                dam_ear = str(r.get(col_dam, '')).strip().upper() if col_dam else '-'
                sire_ear = str(r.get(col_sire, '')).strip().upper() if col_sire else '-'
                s_tag = str(r.get(col_start, '')).strip()
                e_tag = str(r.get(col_end, '')).strip()

                if s_tag and e_tag and s_tag.lower() not in ['nan', 'none', '-', '']:
                    s_num = extract_number(s_tag)
                    e_num = extract_number(e_tag)
                    prefix = get_prefix(s_tag)
                    
                    if s_num is not None and e_num is not None:
                        start_i = min(s_num, e_num)
                        end_i = max(s_num, e_num)
                        digits_match = re.findall(r'\d+', s_tag)
                        orig_digits_len = len(digits_match[0]) if digits_match else 5

                        if f_date and f_date.lower() not in ['nan', 'none', '-', '']:
                            notch_ranges.append({
                                'prefix': prefix,
                                'start': start_i,
                                'end': end_i,
                                'dob': f_date
                            })

                        if (end_i - start_i) <= 50:
                            for cur_n in range(start_i, end_i + 1):
                                young_ear = format_tag(prefix, cur_n, orig_digits_len)
                                b_code = 'D'
                                if 'LY' in prefix: b_code = 'LY'
                                elif 'Y' in prefix: b_code = 'Y'
                                elif 'L' in prefix: b_code = 'L'

                                registered_young_pigs[young_ear] = {
                                    "ear": young_ear,
                                    "breed": b_code,
                                    "sex": "FEMALE",
                                    "parity": "-",
                                    "mate": "-",
                                    "birth_date": f_date if f_date and f_date != '-' else "-",
                                    "mating_date": "-",
                                    "dob": "-",
                                    "is_dead": False,
                                    "dod": "-",
                                    "spi": "-", "mli": "-", "tsi": "-",
                                    "total_born": "-", "born_alive": "-", "weaning": "-",
                                    "mother_wt": "-", "weaning_wt": "-",
                                    "tnb": "-", "nba": "-", "lteat": "-", "rteat": "-",
                                    "sire_sire": "-", "sire_dam": "-", "dam_sire": "-", "dam_dam": "-",
                                    "gen1_sire": sire_ear if sire_ear and sire_ear != 'NAN' else "-",
                                    "gen1_dam": dam_ear if dam_ear and dam_ear != 'NAN' else "-",
                                    "details": {
                                        "耳號": young_ear,
                                        "第一代公": sire_ear,
                                        "第一代母": dam_ear,
                                        "出生日期": f_date,
                                        "備註": "系統依留種耳號區間自動實體化建檔"
                                    }
                                }

    # 4. 解析主表生產與淘汰數據
    existing_ears_in_main = set()
    pedigree_data = []

    for _, row in df_main.iterrows():
        ear = str(row.get(col_ear, '')).strip() if pd.notna(row.get(col_ear)) else ""
        if not ear or ear.lower() in ['nan', 'none', '-', '', 'null']:
            continue
        
        ear_upper = ear.upper()
        existing_ears_in_main.add(ear_upper)

        # 🌟 從 Col L 取得淘汰資訊
        dod_raw = str(row.get(col_dod, '')).strip() if col_dod and pd.notna(row.get(col_dod)) else ""
        is_dead = False
        dod_clean = "-"
        if dod_raw and dod_raw.lower() not in ['nan', 'none', '-', '', 'null']:
            is_dead = True
            dod_clean = dod_raw
            death_map[ear_upper] = dod_clean

        breed = str(row.get(col_breed, '')).strip().upper() if pd.notna(row.get(col_breed)) else "D"
        if 'LY' in ear_upper: breed = 'LY'
        elif 'Y' in ear_upper and breed == 'D': breed = 'Y'
        elif 'L' in ear_upper and breed == 'D': breed = 'L'

        def get_v(col_name):
            if col_name and pd.notna(row.get(col_name)):
                val = str(row.get(col_name)).strip()
                return val if val.lower() not in ['nan', 'none', ''] else '-'
            return '-'

        # 生日解析
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
                        birth_date_val = v.replace('/', '-')

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": get_v(col_sex),
            "parity": get_v(col_parity),
            "mate": get_v(col_mate),
            "birth_date": birth_date_val,
            "mating_date": get_v(col_mating_date),
            "dob": get_v(col_farrow_date),
            "is_dead": is_dead,
            "dod": dod_clean,
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

    # 補入未生產新留種豬
    for y_ear, y_data in registered_young_pigs.items():
        if y_ear not in existing_ears_in_main:
            pedigree_data.append(y_data)

    output_payload = {
        "pedigree": pedigree_data,
        "death_map": death_map
    }

    print(f"💀 成功提取出 {len(death_map)} 筆淘汰/死亡個體！")
    if "D1405" in death_map:
        print(f"🎯 確認抓取到 D1405: {death_map['D1405']}")
    else:
        print("⚠️ 警告：仍未在 Col L 找到 D1405，請檢查主表資料")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)
    print("✅ 已成功寫入 data.json！")

if __name__ == "__main__":
    fetch_and_parse()
