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
    if not name_str or str(name_str).strip() in ['-', 'nan', 'NaN', 'None', '']:
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
    print("🚀 啟動：0代美系種源與5位數自繁仔豬耳號區間精準鎖定串聯...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    target_gids = {
        "us_source": "803517616",      # 美國原始種源數據 (4位數)
        "main_prod": "0"               # 合併報表_配種_產房 (包含耳號區間與分娩日)
    }
    
    dfs = {}
    for key, gid in target_gids.items():
        url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
        try:
            res = requests.get(url, headers=headers, timeout=20)
            res.encoding = 'utf-8-sig'
            if res.status_code == 200:
                temp_df = pd.read_csv(io.StringIO(res.text), low_memory=False)
                temp_df.columns = [str(c).replace('\n', '').replace('\r', '').strip() for c in temp_df.columns]
                dfs[key] = temp_df.dropna(how='all')
        except Exception as e:
            print(f"⚠️ 分頁 {key} 讀取失敗: {e}")
            dfs[key] = pd.DataFrame()

    # =========================================================
    # 1. 建立 0 代美國原種庫 (4位數耳號，如 D1400, D1062, D1071, D1401)
    # =========================================================
    us_db = {}
    us_df = dfs.get("us_source", pd.DataFrame())
    
    if not us_df.empty:
        for _, row in us_df.iterrows():
            ear_val = str(row.get('耳號', row.get('Ear Tag', ''))).strip().upper()
            if not ear_val or ear_val == 'NAN':
                ear2 = str(row.get('耳號2', '')).strip()
                if ear2 and ear2.isdigit():
                    b_code = str(row.get('品種代號', 'D')).strip().upper()
                    ear_val = f"{b_code}{ear2}"

            if ear_val and ear_val != 'NAN':
                dob = parse_date_value(row.get('DOB', row.get('出生日期', '-')))
                sire_name = shorten_name(row.get('Sire Name美系父親名', row.get('Sire Name美系父親-全名', '-')))
                dam_name  = shorten_name(row.get('Dam Name美系母親名', row.get('Dam Name美系母親-全名', '-')))
                mgs_name  = shorten_name(row.get('MGS Name 美系MGS名', '-'))

                us_db[ear_val] = {
                    "birth_date": dob,
                    "sire": sire_name,
                    "dam": dam_name,
                    "mgs": mgs_name,
                    "sire_sire": sire_name,   # 0代公豬父系頂層
                    "sire_dam": dam_name,    # 0代母系頂層
                    "dam_sire": mgs_name,
                    "dam_dam": dam_name
                }
                num = extract_number(ear_val)
                if num:
                    us_db[str(num)] = us_db[ear_val]

    # =========================================================
    # 2. 建立 5 位數自產豬耳號區間庫 (由 4位數父母生下)
    # =========================================================
    prod_df = dfs.get("main_prod", pd.DataFrame())
    litter_interval_db = []
    
    # 尋找關鍵欄位
    col_dam = next((c for c in prod_df.columns if '母豬耳號' in c or 'Nombor' in c or 'Ear Tag' in c), None)
    col_sire = next((c for c in prod_df.columns if '配種公豬' in c or 'Jantan' in c or 'Boar' in c), None)
    col_farrow = next((c for c in prod_df.columns if 'Farrowing' in c or '分娩日' in c), None)
    col_mating = next((c for c in prod_df.columns if 'Kahwin' in c or '配種日' in c), None)
    col_breed = next((c for c in prod_df.columns if 'Breed' in c or '品種' in c), None)

    # 尋找耳號間距欄位 (Notch Breeder Start / End)
    col_n_start1 = next((c for c in prod_df.columns if 'Notch Breeder (start)' in c or 'Breeder (start)' in c), None)
    col_n_end1   = next((c for c in prod_df.columns if 'Notch Breeder (end)' in c or 'Breeder (end)' in c), None)

    for _, row in prod_df.iterrows():
        farrow_d = parse_date_value(row.get(col_farrow, '')) if col_farrow else '-'
        dam_e    = str(row.get(col_dam, '')).strip().upper() if col_dam and pd.notna(row.get(col_dam)) else ''
        sire_e   = str(row.get(col_sire, '')).strip().upper() if col_sire and pd.notna(row.get(col_sire)) else ''

        # 檢查耳號區間
        for start_col, end_col in [(col_n_start1, col_n_end1), (90, 91), (92, 93)]:
            try:
                s_val = row.iloc[start_col] if isinstance(start_col, int) and len(row) > start_col else row.get(start_col)
                e_val = row.iloc[end_col] if isinstance(end_col, int) and len(row) > end_col else row.get(end_col)
                s_num = extract_number(s_val)
                e_num = extract_number(e_val)
                if s_num and e_num and farrow_d != '-':
                    litter_interval_db.append({
                        "start": min(s_num, e_num),
                        "end": max(s_num, e_num),
                        "birth_date": farrow_d,
                        "dam_ear": dam_e,
                        "sire_ear": sire_e
                    })
            except Exception:
                pass

    # =========================================================
    # 3. 組合全場資料庫 (0代原種 + 1/2代自繁五位數)
    # =========================================================
    pedigree_data = []
    registered_ears = set()

    for _, row in prod_df.iterrows():
        ear = str(row.get(col_dam, '')).strip().upper() if col_dam and pd.notna(row.get(col_dam)) else ''
        if not ear or ear in ['NAN', '-', '', 'NONE']:
            continue

        ear_num = extract_number(ear)
        breed = str(row.get(col_breed, 'D')).strip().upper() if col_breed and pd.notna(row.get(col_breed)) else 'D'
        if 'LY' in ear: breed = 'LY'

        ind_birth = '-'
        ind_sire  = '-'
        ind_dam   = '-'
        s_sire    = '-'
        s_dam     = '-'
        d_sire    = '-'
        d_dam     = '-'

        # 情況 A：4 位數美國原種 (直接查美國表)
        if ear in us_db or (ear_num and len(str(ear_num)) == 4 and str(ear_num) in us_db):
            u_info = us_db.get(ear) or us_db.get(str(ear_num))
            ind_birth = u_info["birth_date"]
            ind_sire  = u_info["sire"]
            ind_dam   = u_info["dam"]
            s_sire    = u_info["sire_sire"]
            s_dam     = u_info["sire_dam"]
            d_sire    = u_info["dam_sire"]
            d_dam     = u_info["dam_dam"]

        # 情況 B：5 位數自產豬 (從耳號區間查出生日與父母耳號，再向上穿透到美國表)
        elif ear_num and len(str(ear_num)) == 5:
            for litter in litter_interval_db:
                if litter["start"] <= ear_num <= litter["end"]:
                    ind_birth = litter["birth_date"]
                    parent_dam_ear  = litter["dam_ear"]
                    parent_sire_ear = litter["sire_ear"]

                    # 查詢父親的美國血統
                    s_info = us_db.get(parent_sire_ear) or us_db.get(str(extract_number(parent_sire_ear)))
                    if s_info:
                        ind_sire = s_info["sire"]        # 父親名稱
                        s_sire   = s_info["sire"]        # 祖父
                        s_dam    = s_info["dam"]         # 祖母
                    else:
                        ind_sire = parent_sire_ear

                    # 查詢母親的美國血統
                    d_info = us_db.get(parent_dam_ear) or us_db.get(str(extract_number(parent_dam_ear)))
                    if d_info:
                        ind_dam  = d_info["dam"]         # 母親名稱
                        d_sire   = d_info["sire"]        # 外公
                        d_dam    = d_info["dam"]         # 外婆
                    else:
                        ind_dam = parent_dam_ear
                    break

        mating_d = parse_date_value(row.get(col_mating, '')) if col_mating else '-'
        farrow_d = parse_date_value(row.get(col_farrow, '')) if col_farrow else '-'
        mate_sire = str(row.get(col_sire, '-')).strip().upper() if col_sire and pd.notna(row.get(col_sire)) else '-'

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": "FEMALE" if not (ear.startswith('D') and not ear.startswith('DD')) else "MALE",
            "parity": str(row.get('Parity', row.get('胎次', '-'))).strip(),
            "mate": mate_sire,
            "birth_date": ind_birth,
            "mating_date": mating_d,
            "dob": farrow_d,
            "gen1_sire": ind_sire,
            "gen1_dam": ind_dam,
            "sire_sire": s_sire,
            "sire_dam": s_dam,
            "dam_sire": d_sire,
            "dam_dam": d_dam,
            "details": {str(k): str(v) for k, v in row.items() if pd.notna(v)}
        }
        pedigree_data.append(entry)
        registered_ears.add(ear)

    # =========================================================
    # 4. 把 0 代美國種源所有公豬/母豬強制以獨立個體補齊入庫
    # =========================================================
    for u_ear, u_info in us_db.items():
        if u_ear.isdigit() or u_ear in registered_ears:
            continue
        b_class = "D" if u_ear.startswith("D") else ("L" if u_ear.startswith("L") else "Y")
        pedigree_data.append({
            "ear": u_ear,
            "breed": b_class,
            "sex": "MALE" if not u_ear.startswith("DD") else "FEMALE",
            "parity": "-",
            "mate": "-",
            "birth_date": u_info["birth_date"],
            "mating_date": "-",
            "dob": "-",
            "gen1_sire": u_info["sire"],
            "gen1_dam": u_info["dam"],
            "sire_sire": u_info["sire_sire"],
            "sire_dam": u_info["sire_dam"],
            "dam_sire": u_info["dam_sire"],
            "dam_dam": u_info["dam_dam"],
            "details": {}
        })
        registered_ears.add(u_ear)

    print(f"🎉 資料鏈結完成！共產出 {len(pedigree_data)} 筆系譜。")
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fetch_and_parse()
