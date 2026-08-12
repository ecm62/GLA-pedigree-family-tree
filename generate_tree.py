import json
import pandas as pd
import requests
import io
import re
from datetime import datetime, timedelta

SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"

def parse_date_value(val):
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
    nums = re.findall(r'\d+', str(ear_str))
    if nums:
        return int(nums[0])
    return None

def shorten_name(name_str):
    if not name_str or name_str in ['-', 'nan', 'None', '']:
        return '-'
    s = str(name_str).strip()
    parts = s.split(' ')
    keywords = [p for p in parts if not re.match(r'^\d+[\-\d]*$', p) and p.upper() not in ['1CR1', '1CR2', 'CR1', 'CR2']]
    if keywords:
        last = keywords[-1]
        if re.search(r'\d', last) and len(keywords) > 1:
            keywords.pop()
        return ' '.join(keywords)
    return s

def fetch_and_parse():
    print("🚀 啟動分流邏輯解析：4位數抓美國原始數據，5位數抓GLA育種與同胎反推...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 明確指定各分頁 GID 進行精準抓取
    # 依據您的表結構：美國原始種源數據 與 GLA遺傳育種資訊
    target_gids = {
        "us_source": "803517616",      # 美國原始種源數據 (4位數進口豬)
        "gla_breeding": "1821811808",  # 🧬GLA 遺傳育種資訊
        "main_prod": "0"               # 合併報表 (配種+產房)
    }
    
    dfs = {}
    for key, gid in target_gids.items():
        url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
        try:
            res = requests.get(url, headers=headers, timeout=12)
            res.encoding = 'utf-8-sig'
            if res.status_code == 200:
                temp_df = pd.read_csv(io.StringIO(res.text))
                temp_df.columns = [str(c).replace('\n', '').replace('\r', '').strip() for c in temp_df.columns]
                dfs[key] = temp_df.dropna(how='all')
        except Exception:
            dfs[key] = pd.DataFrame()

    # 建立「美國原始種源資料庫」(專門服務 4 位數進口豬)
    us_db = {}
    us_df = dfs.get("us_source", pd.DataFrame())
    if not us_df.empty:
        for _, row in us_df.iterrows():
            # 4位數耳號通常在第二欄或名為耳號
            ear_candidates = [str(row.get(c, '')).strip().upper() for c in us_df.columns if '耳號' in c or 'Ear Tag' in c or 'Nombor' in c]
            ear_val = next((e for e in ear_candidates if e and e != 'NAN'), '')
            if not ear_val:
                # 預設抓特定欄位
                for col_idx in [2, 6, 7]:
                    if len(us_df.columns) > col_idx:
                        val = str(row.iloc[col_idx]).strip().upper()
                        if val.isdigit() and len(val) == 4:
                            ear_val = val
                            break
            if ear_val:
                dob = parse_date_value(row.get('DOB', row.get('出生日期', '-')))
                sire = shorten_name(row.get('Sire Name美系父親-全名', row.get('Sire Name美系父親名', '-')))
                dam = shorten_name(row.get('Dam Name美系母親-全名', row.get('Dam Name美系母親名', '-')))
                us_db[ear_val] = {'dob': dob, 'sire': sire, 'dam': dam}

    # 整合主產房與GLA育種資料 (服務 5 位數自產豬與母豬歷胎績效)
    main_df = dfs.get("main_prod", pd.DataFrame())
    gla_df = dfs.get("gla_breeding", pd.DataFrame())
    
    df_list = [d for d in [main_df, gla_df] if not d.empty]
    if not df_list:
        print("❌ 無法取得生產育種數據")
        return
    df = pd.concat(df_list, ignore_index=True).drop_duplicates()

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
    col_breed = get_exact_col(['Breed', '品種', '品種代號'])
    
    col_birth_date = get_exact_col(['DOB', '出生日期', '個體生日'])
    col_farrow_date = get_exact_col(['Tarikh Farrowing date / Tarikh beranak (m/d)', 'Farrowing date', '分娩日期'])
    
    col_spi = get_exact_col(['SPI'])
    col_mli = get_exact_col(['MLI'])
    col_tsi = get_exact_col(['TSI'])
    col_total_born = get_exact_col(['Total born 同胎總生產數', '總生產'])
    col_born_alive = get_exact_col(['Born alive 同胎次活胎數量', '活胎'])
    col_weaning = get_exact_col(['Weaning 同胎次離乳數量', '離乳'])
    col_weaning_wt = get_exact_col(['weaning weight 同胎次離乳平均重', '均重'])

    col_us_sire_full = get_exact_col(['Sire Name美系父親-全名', 'Sire Name美系父親全名'])
    col_us_dam_full  = get_exact_col(['Dam Name美系母親-全名', 'Dam Name美系母親全名'])
    col_us_mgs       = get_exact_col(['MGS Name 美系MGS名', 'MGS Name美系MGS名'])

    col_notch_start = get_exact_col(['Ear Notch Breeder (start)', 'Notch Breeder (start)'])
    col_notch_end   = get_exact_col(['Ear Notch Breeder (end)', 'Notch Breeder (end)'])

    # PASS 1: 建立自產同胎反推對照表
    litter_map = []
    for _, row in df.iterrows():
        farrow_d = parse_date_value(row.get(col_farrow_date, ''))
        mate_boar = str(row.get(col_mate, '')).strip() if pd.notna(row.get(col_mate)) else '-'
        dam_ear_val = str(row.get(col_ear, '')).strip().upper() if pd.notna(row.get(col_ear)) else ''

        sire_full = str(row.get(col_us_sire_full, '')).strip() if (col_us_sire_full and pd.notna(row.get(col_us_sire_full))) else '-'
        dam_full  = str(row.get(col_us_dam_full, '')).strip() if (col_us_dam_full and pd.notna(row.get(col_us_dam_full))) else '-'

        if col_notch_start and col_notch_end:
            start_num = extract_number(row.get(col_notch_start, ''))
            end_num   = extract_number(row.get(col_notch_end, ''))
            if start_num is not None and end_num is not None and farrow_d != '-':
                litter_map.append({
                    'start': min(start_num, end_num),
                    'end': max(start_num, end_num),
                    'origin_dob': farrow_d,
                    'origin_dam': dam_ear_val,
                    'origin_sire': mate_boar,
                    'origin_sire_sire': sire_full,
                    'origin_sire_dam': dam_full
                })

    # PASS 2: 組織總表數據
    pedigree_data = []

    for idx, row in df.iterrows():
        ear = str(row.get(col_ear, '')).strip() if pd.notna(row.get(col_ear)) else ""
        if not ear or ear.lower() in ['nan', 'none', '-', '', 'null']:
            continue

        ear_upper = ear.upper()
        breed = str(row.get(col_breed, '')).strip().upper() if pd.notna(row.get(col_breed)) else "D"
        if 'LY' in ear_upper: breed = 'LY'

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

        individual_dob = '-'
        inferred_sire = '-'
        inferred_dam = '-'
        inferred_sire_sire = '-'
        inferred_sire_dam = '-'

        # 邏輯分流判斷：
        # 如果是 4 位數進口豬，直接從美國原始數據庫 (us_db) 抓 DOB 與父母
        if len(ear_upper) == 4 and ear_upper in us_db:
            individual_dob = us_db[ear_upper]['dob']
            inferred_sire = us_db[ear_upper]['sire']
            inferred_dam = us_db[ear_upper]['dam']
        else:
            # 5位數或本場自產豬：透過同胎耳號範圍反推
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

            if individual_dob == '-' and raw_dob != '-':
                individual_dob = raw_dob

        us_sire = get_v(col_us_sire_full)
        us_dam  = get_v(col_us_dam_full)

        final_gen1_sire = inferred_sire if inferred_sire != '-' else us_sire
        final_gen1_dam  = inferred_dam if inferred_dam != '-' else us_dam

        if final_gen1_sire.upper() == ear_upper: final_gen1_sire = '-'
        if final_gen1_dam.upper() == ear_upper: final_gen1_dam = '-'

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": get_v(col_sex),
            "parity": get_v(col_parity),
            "mate": get_v(col_mate),
            "birth_date": individual_dob,
            "dob": farrow_dob,
            "spi": get_v(col_spi),
            "mli": get_v(col_mli),
            "tsi": get_v(col_tsi),
            "total_born": get_v(col_total_born),
            "born_alive": get_v(col_born_alive),
            "weaning": get_v(col_weaning),
            "weaning_wt": get_v(col_weaning_wt),
            "sire_sire": shorten_name(inferred_sire_sire) if inferred_sire_sire != '-' else '-',
            "sire_dam": shorten_name(inferred_sire_dam) if inferred_sire_dam != '-' else '-',
            "dam_sire": shorten_name(get_v(col_us_mgs)),
            "dam_dam": '-',
            "gen1_sire": shorten_name(final_gen1_sire),
            "gen1_dam": shorten_name(final_gen1_dam),
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

    print(f"🎉 分流育種數據整合完成！共處理 {len(pedigree_data)} 筆紀錄。")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fetch_and_parse()
