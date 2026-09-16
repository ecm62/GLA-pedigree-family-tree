import json
import pandas as pd
import requests
import io
import re

SPREADSHEET_ID = "1MlhcSXitL_jWYvXVfmo6bQfQqDPIDgUt0VGIZVaB5aw"
GID_MAIN = "0"                 # 📊 育種_家族階層清單
GID_US_ORIGIN = "1267648620"   # 🧬 美國原始種源數據
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

def clean_str(val):
    if pd.isna(val) or val is None:
        return "-"
    s = str(val).replace('\n', ' ').replace('\r', '').strip()
    return s if s.lower() not in ['nan', 'none', '', 'null'] else "-"

def clean_name(val):
    s = clean_str(val)
    if s == "-":
        return "-"
    if re.match(r'^[\d\-]+$', s):
        return "-"
    parts = s.split(' ')
    valid_parts = [p for p in parts if not re.match(r'^[\d\-]+$', p) and p.upper() not in ['1CR1', '1CR2', 'CR1', 'CR2']]
    if valid_parts:
        if len(valid_parts) > 1 and re.search(r'\d', valid_parts[-1]):
            valid_parts.pop()
        return " ".join(valid_parts)
    return s

def fetch_and_parse():
    print("🚀 正在整合美國原始數據與家族階層清單...")

    # 1. 讀取美國原始種源數據 (圖一)
    us_data_map = {}
    raw_us = fetch_sheet_csv(GID_US_ORIGIN)
    if raw_us:
        df_us = pd.read_csv(io.StringIO(raw_us))
        df_us.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df_us.columns]
        
        col_ear_us = next((c for c in df_us.columns if '耳號' in c), None)
        col_sire_us = next((c for c in df_us.columns if 'Sire Name' in c or '美系父親名' in c), None)
        col_dam_us = next((c for c in df_us.columns if 'Dam Name' in c or '美系母親名' in c), None)
        col_sex_us = next((c for c in df_us.columns if 'Sex' in c or '性別' in c), None)
        col_dob_us = next((c for c in df_us.columns if 'DOB' in c or '出生' in c), None)

        for _, r in df_us.iterrows():
            e = clean_str(r.get(col_ear_us, '')).upper()
            if e != '-':
                us_data_map[e] = {
                    "sire": clean_name(r.get(col_sire_us, '-')),
                    "dam": clean_name(r.get(col_dam_us, '-')),
                    "sex": clean_str(r.get(col_sex_us, '-')),
                    "dob": clean_str(r.get(col_dob_us, '-')).replace('/', '-')
                }

    # 2. 讀取主表 (圖二)
    raw_main = fetch_sheet_csv(GID_MAIN)
    if not raw_main:
        print("❌ 主表讀取失敗！")
        return

    df_main = pd.read_csv(io.StringIO(raw_main))
    df_main.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df_main.columns]

    # 動態確認欄位
    def find_col(keywords):
        for kw in keywords:
            for c in df_main.columns:
                if kw.lower() in c.lower():
                    return c
        return None

    c_ear = find_col(['耳號']) or df_main.columns[5]
    c_sex = find_col(['Sex', '性別']) or df_main.columns[4]
    c_parity = find_col(['胎次', 'Parity']) or df_main.columns[6]
    c_mate = find_col(['當胎配種公', '配種公']) or df_main.columns[7]
    c_mating_d = find_col(['配種日期']) or df_main.columns[8]
    c_farrow_d = find_col(['當胎分娩日', '分娩日']) or df_main.columns[9]
    c_dob = find_col(['DOB出生日期', 'DOB']) or df_main.columns[10]
    c_dod = find_col(['DOD/淘汰日期', 'DOD', '淘汰日期']) or df_main.columns[11]
    c_breed = find_col(['Breed', '品種']) or df_main.columns[14]

    # 全場耳號母豬確認名冊
    confirmed_sows = set()
    for _, row in df_main.iterrows():
        e = clean_str(row.get(c_ear, '')).upper()
        p = clean_str(row.get(c_parity, ''))
        fd = clean_str(row.get(c_farrow_d, ''))
        sx = clean_str(row.get(c_sex, '')).upper()
        if e != '-':
            if p != '-' or fd != '-' or 'FEMALE' in sx or 'GILT' in sx or '母' in sx:
                confirmed_sows.add(e)

    for e, udata in us_data_map.items():
        if 'GILT' in udata['sex'].upper() or 'FEMALE' in udata['sex'].upper():
            confirmed_sows.add(e)

    pedigree_data = []
    death_map = {}

    for _, row in df_main.iterrows():
        ear = clean_str(row.get(c_ear, ''))
        if ear == '-' or ear == '耳號':
            continue
        ear_upper = ear.upper()

        # 淘汰/死亡
        dod = clean_str(row.get(c_dod, ''))
        is_dead = False
        if dod != '-':
            is_dead = True
            death_map[ear_upper] = dod

        # 性別
        if ear_upper in confirmed_sows or ear_upper.startswith('LY'):
            sex = "FEMALE"
        else:
            raw_s = clean_str(row.get(c_sex, '')).upper()
            sex = "MALE" if ("MALE" in raw_s or "公" in raw_s) else "FEMALE"

        # 品種
        raw_b = clean_str(row.get(c_breed, '')).upper()
        breed = "D"
        if "YORK" in raw_b or ear_upper.startswith("Y"):
            breed = "Y"
        elif "LAND" in raw_b or ear_upper.startswith("L"):
            breed = "L"
        elif "DUROC" in raw_b or ear_upper.startswith("D"):
            breed = "D"
        if "LY" in ear_upper:
            breed = "LY"

        # 提取父母品系名（雙向整合圖一與圖二）
        us_sire = "-"
        us_dam = "-"
        
        # 優先從主表欄位取
        for c in df_main.columns:
            if '父親名' in c:
                val = clean_name(row.get(c))
                if val != '-': us_sire = val
            if '母親名' in c:
                val = clean_name(row.get(c))
                if val != '-': us_dam = val

        # 若主表該欄位為空，回溯美國原始數據表 (圖一)
        if (us_sire == '-' or us_dam == '-') and ear_upper in us_data_map:
            if us_sire == '-': us_sire = us_data_map[ear_upper]['sire']
            if us_dam == '-': us_dam = us_data_map[ear_upper]['dam']

        dob_val = clean_str(row.get(c_dob, ''))
        if dob_val == '-' and ear_upper in us_data_map:
            dob_val = us_data_map[ear_upper]['dob']

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": sex,
            "parity": clean_str(row.get(c_parity, '-')),
            "mate": clean_str(row.get(c_mate, '-')),
            "birth_date": dob_val,
            "mating_date": clean_str(row.get(c_mating_d, '-')),
            "dob": clean_str(row.get(c_farrow_d, '-')),
            "is_dead": is_dead,
            "dod": dod,
            "sire_sire": us_sire,
            "sire_dam": us_dam,
            "dam_sire": us_sire,
            "dam_dam": us_dam,
            "gen1_sire": clean_str(row.get(find_col(['第一代公']), '-')),
            "gen1_dam": clean_str(row.get(find_col(['第一代母']), '-')),
            "details": {str(k).strip(): clean_str(v) for k, v in row.items()}
        }
        pedigree_data.append(entry)

    output = {
        "pedigree": pedigree_data,
        "death_map": death_map
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 成功產出 data.json！個體數: {len(pedigree_data)}")

if __name__ == "__main__":
    fetch_and_parse()
