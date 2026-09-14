import json
import pandas as pd
import requests
import io
import re

SPREADSHEET_ID = "1MlhcSXitL_jWYvXVfmo6bQfQqDPIDgUt0VGIZVaB5aw"

GID_US_ORIGIN = "1267648620"   # 美國原始種源數據 (4 位數純種生日)
GID_COMBINED = "84920994"      # 合併報表(配種+產房) (留種區間 KN~KO 與分娩日 BJ)
GID_DEATH = "1606643507"       # Death sow and gilt (Import) 官方死亡分頁
GID_MAIN = "0"                 # 主表 / 育種家族階層清單

def fetch_sheet_csv(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
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

def format_tag(prefix, num, orig_len):
    # 保持原耳號數字位數（如 5 位數補零）
    num_str = str(num).zfill(orig_len)
    return f"{prefix}{num_str}"

def fetch_and_parse():
    print("🚀 正在從 Google Sheets 建立全場血統庫（含未生產後備留種個體）...")
    
    df_main = fetch_sheet_csv(GID_MAIN)
    if df_main.empty:
        print("❌ 主表資料為空！")
        return

    # 1. 官方死亡清單
    df_death = fetch_sheet_csv(GID_DEATH)
    official_death_set = set()
    if not df_death.empty:
        ear_col_death = next((c for c in df_death.columns if 'Ear Tag' in c or '耳號' in c or 'Ear' in c), None)
        if not ear_col_death:
            ear_col_death = df_death.columns[2] if len(df_death.columns) > 2 else df_death.columns[0]
        for _, r in df_death.iterrows():
            e = str(r.get(ear_col_death, '')).strip().upper()
            if e and e.lower() not in ['nan', 'none', '-', '']:
                official_death_set.add(e)
    print(f"💀 官方死亡名單載入完成，共計 {len(official_death_set)} 筆")

    # 2. 4 位數美系純種原種生日對照
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
                    us_dob_map[e] = d.replace('/', '-')

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

    # 3. 處理「合併報表」：提取所有出生紀錄與留種區間個體
    df_comb = fetch_sheet_csv(GID_COMBINED)
    notch_ranges = []
    registered_young_pigs = {} # 保存未生產留種小豬的血統資料 { ear_tag: entry }

    if not df_comb.empty:
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
                        orig_digits_len = len(re.findall(r'\d+', s_tag)[0])

                        # 記錄區間對照
                        if f_date and f_date.lower() not in ['nan', 'none', '-', '']:
                            notch_ranges.append({
                                'prefix': prefix,
                                'start': start_i,
                                'end': end_i,
                                'dob': f_date
                            })

                        # 🌟 核心創舉：自動為此留種區間內的每頭新留種豬建立實體血統檔
                        # 即使牠們一生未配種未分娩，也能獨立存在並擁有父母親！
                        # 避免異常區間過大，限定區間數 <= 50 頭
                        if (end_i - start_i) <= 50:
                            for cur_n in range(start_i, end_i + 1):
                                young_ear = format_tag(prefix, cur_n, orig_digits_len)
                                # 推導品種
                                b_code = 'D'
                                if 'LY' in prefix: b_code = 'LY'
                                elif 'Y' in prefix: b_code = 'Y'
                                elif 'L' in prefix: b_code = 'L'

                                registered_young_pigs[young_ear] = {
                                    "ear": young_ear,
                                    "breed": b_code,
                                    "sex": "FEMALE", # 留種母預設
                                    "parity": "-",
                                    "mate": "-",
                                    "birth_date": f_date if f_date and f_date != '-' else "-",
                                    "mating_date": "-",
                                    "dob": "-",
                                    "is_dead": young_ear in official_death_set,
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

    print(f"📦 已從合併報表留種區間中實體化解析出 {len(registered_young_pigs)} 頭留種新豬隻檔案（包含未生產個體）")

    # 4. 處理主表生產紀錄
    existing_ears_in_main = set()
    pedigree_data = []

    for _, row in df_main.iterrows():
        ear = str(row.get(col_ear, '')).strip() if pd.notna(row.get(col_ear)) else ""
        if not ear or ear.lower() in ['nan', 'none', '-', '', 'null']:
            continue
        
        ear_upper = ear.upper()
        existing_ears_in_main.add(ear_upper)

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
            "is_dead": ear_upper in official_death_set,
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

    # 5. 🌟 關鍵合併：將「留種區間內存在、但主表尚未有生產紀錄的後備豬隻」無縫補入主資料庫！
    appended_count = 0
    for y_ear, y_data in registered_young_pigs.items():
        if y_ear not in existing_ears_in_main:
            pedigree_data.append(y_data)
            appended_count += 1

    print(f"🎉 資料合併完成！總計 {len(pedigree_data)} 筆個體資料（已成功補入 {appended_count} 頭未生產留種新豬）。")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)
    print("✅ 成功寫入 data.json！現在可以查詢未生產後備豬隻的完整三代父母與血統。")

if __name__ == "__main__":
    fetch_and_parse()
