import json
import pandas as pd
import requests
import io
import re

SPREADSHEET_ID = "1MlhcSXitL_jWYvXVfmo6bQfQqDPIDgUt0VGIZVaB5aw"

GID_MAIN = "0"                 # 📊 育種_家族階層清單 (Col F: 耳號, Col L: DOD/淘汰日期)
GID_US_ORIGIN = "1267648620"   # 美國原始種源數據
GID_COMBINED = "84920994"      # 合併報表(配種+產房)

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
    return f"{prefix}{str(num).zfill(orig_len)}"

def find_col_exact(columns, target_name):
    for c in columns:
        c_clean = str(c).replace('\n', '').replace('\r', '').strip()
        if target_name.lower() in c_clean.lower():
            return c
    return None

def fetch_and_parse():
    print("🚀 正在從主表【📊 育種_家族階層清單】精準對齊 Col F (耳號) 與 Col L (DOD/淘汰日期)...")
    
    raw_main_csv = fetch_sheet_csv(GID_MAIN)
    if not raw_main_csv:
        print("❌ 主表 GID:0 讀取失敗！")
        return

    # 1. 讀取主表
    df_main = pd.read_csv(io.StringIO(raw_main_csv))
    df_main.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df_main.columns]

    # 🌟 精確鎖定：Col F (索引 5) 為耳號，Col L (索引 11) 為 DOD/淘汰日期
    col_ear = None
    for c in df_main.columns:
        if c.strip() == '耳號' or '耳號' in c:
            col_ear = c
            break
    if not col_ear and len(df_main.columns) >= 6:
        col_ear = df_main.columns[5] # Col F

    col_dod = None
    for c in df_main.columns:
        if 'DOD' in c.upper() or '淘汰日期' in c:
            col_dod = c
            break
    if not col_dod and len(df_main.columns) >= 12:
        col_dod = df_main.columns[11] # Col L

    print(f"🎯 鎖定耳號欄位 (Col F): [{col_ear}]")
    print(f"🎯 鎖定死亡淘汰欄位 (Col L): [{col_dod}]")

    death_map = {} # 存放所有在 Col L 記載死亡的耳號及淘汰日期字串

    pedigree_data = []
    existing_ears_in_main = set()

    for idx, row in df_main.iterrows():
        # 取耳號 (Col F)
        ear_val = str(row.get(col_ear, '')).strip() if pd.notna(row.get(col_ear)) else ""
        if not ear_val or ear_val.lower() in ['nan', 'none', '-', '', 'null', '耳號']:
            continue

        ear_upper = ear_val.upper()
        existing_ears_in_main.add(ear_upper)

        # 🌟 直接取 Col L (DOD/淘汰日期)
        dod_val = ""
        if col_dod and pd.notna(row.get(col_dod)):
            dod_val = str(row.get(col_dod)).replace('\n', ' ').strip()
        elif len(row) >= 12 and pd.notna(row.iloc[11]):
            dod_val = str(row.iloc[11]).replace('\n', ' ').strip()

        is_dead = False
        dod_clean = "-"
        if dod_val and dod_val.lower() not in ['nan', 'none', '-', '', 'null', 'dod/淘汰日期']:
            is_dead = True
            dod_clean = dod_val
            death_map[ear_upper] = dod_clean

        # 品種推導
        breed = "D"
        if 'LY' in ear_upper: breed = 'LY'
        elif 'Y' in ear_upper: breed = 'Y'
        elif 'L' in ear_upper: breed = 'L'
        
        # 性別 (Col E / 索引 4)
        sex_val = "FEMALE"
        if len(row) >= 5 and pd.notna(row.iloc[4]):
            s_raw = str(row.iloc[4]).upper()
            if "MALE" in s_raw or "公" in s_raw: sex_val = "MALE"
        if ear_upper.startswith('D') and not ear_upper.startswith('DD') and len(ear_upper) == 5:
            sex_val = "MALE"

        # 出生日 (Col K / 索引 10)
        dob_val = "-"
        if len(row) >= 11 and pd.notna(row.iloc[10]):
            d_raw = str(row.iloc[10]).strip()
            if d_raw and d_raw.lower() not in ['nan', 'none', '-']:
                dob_val = d_raw.replace('/', '-')

        # 胎次 (Col G / 索引 6)、配種公 (Col H / 索引 7)、配種日 (Col I / 索引 8)、分娩日 (Col J / 索引 9)
        parity_val = str(row.iloc[6]).strip() if len(row) >= 7 and pd.notna(row.iloc[6]) and str(row.iloc[6]).lower() not in ['nan', 'none'] else "-"
        mate_val   = str(row.iloc[7]).strip() if len(row) >= 8 and pd.notna(row.iloc[7]) and str(row.iloc[7]).lower() not in ['nan', 'none'] else "-"
        mating_d   = str(row.iloc[8]).strip() if len(row) >= 9 and pd.notna(row.iloc[8]) and str(row.iloc[8]).lower() not in ['nan', 'none'] else "-"
        farrow_d   = str(row.iloc[9]).strip() if len(row) >= 10 and pd.notna(row.iloc[9]) and str(row.iloc[9]).lower() not in ['nan', 'none'] else "-"

        # 祖代與父母品系名
        def get_v_by_kw(keywords):
            for c in df_main.columns:
                for kw in keywords:
                    if kw.lower() in c.lower():
                        v = row.get(c)
                        if pd.notna(v) and str(v).strip().lower() not in ['nan', 'none', '']:
                            return str(v).strip()
            return '-'

        entry = {
            "ear": ear_val,
            "breed": breed,
            "sex": sex_val,
            "parity": parity_val,
            "mate": mate_val,
            "birth_date": dob_val,
            "mating_date": mating_d,
            "dob": farrow_d,
            "is_dead": is_dead,
            "dod": dod_clean,
            "spi": get_v_by_kw(['SPI']),
            "mli": get_v_by_kw(['MLI']),
            "tsi": get_v_by_kw(['TSI']),
            "total_born": get_v_by_kw(['Total born', '總生產', '總生']),
            "born_alive": get_v_by_kw(['Born alive', '活胎']),
            "weaning": get_v_by_kw(['Weaning', '離乳']),
            "mother_wt": get_v_by_kw(['生育重']),
            "weaning_wt": get_v_by_kw(['均重']),
            "tnb": get_v_by_kw(['TNB']),
            "nba": get_v_by_kw(['NBA']),
            "lteat": get_v_by_kw(['左乳']),
            "rteat": get_v_by_kw(['右乳']),
            "sire_sire": get_v_by_kw(['Sire美系第0代父親名(祖父)', '祖父']),
            "sire_dam": get_v_by_kw(['Dam Name美系第0代母親名(祖母)', '祖母']),
            "dam_sire": get_v_by_kw(['Sire美系第0代父親名(外公)', '外公']),
            "dam_dam": get_v_by_kw(['Dam Name美系第0代母親名(外婆)', '外婆']),
            "gen1_sire": get_v_by_kw(['第一代公', '1st Sire']),
            "gen1_dam": get_v_by_kw(['第一代母', '1st Dam']),
            "details": {str(k).strip(): (str(v).strip() if pd.notna(v) else "") for k, v in row.items()}
        }
        pedigree_data.append(entry)

    # 2. 補充合併報表之未生產後備豬
    raw_comb_csv = fetch_sheet_csv(GID_COMBINED)
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
                        if (end_i - start_i) <= 50:
                            for cur_n in range(start_i, end_i + 1):
                                young_ear = format_tag(prefix, cur_n, orig_digits_len)
                                if young_ear not in existing_ears_in_main:
                                    existing_ears_in_main.add(young_ear)
                                    b_code = 'D'
                                    if 'LY' in prefix: b_code = 'LY'
                                    elif 'Y' in prefix: b_code = 'Y'
                                    elif 'L' in prefix: b_code = 'L'
                                    
                                    pedigree_data.append({
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
                                        "details": {"耳號": young_ear, "第一代公": sire_ear, "第一代母": dam_ear, "出生日期": f_date}
                                    })

    output_payload = {
        "pedigree": pedigree_data,
        "death_map": death_map
    }

    print(f"📊 主表解析成功：總共 {len(pedigree_data)} 筆個體")
    print(f"💀 從 Col L 成功截獲 {len(death_map)} 筆淘汰/死亡紀錄")
    if "D1405" in death_map:
        print(f"🎯【成功鎖定 D1405 淘汰紀錄】: {death_map['D1405']}")
    else:
        print("❌ 警告：依然沒抓到 D1405，請確認主表 Col F 是否為 D1405！")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)
    print("✅ data.json 成功寫入！")

if __name__ == "__main__":
    fetch_and_parse()
