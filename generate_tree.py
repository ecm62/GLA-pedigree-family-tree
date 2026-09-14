import json
import pandas as pd
import requests
import io
import re

SPREADSHEET_ID = "1MlhcSXitL_jWYvXVfmo6bQfQqDPIDgUt0VGIZVaB5aw"
GID_MAIN = "0" # 主表本身即包含 DOD/淘汰日期

def fetch_sheet_csv(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
        res.encoding = 'utf-8-sig'
        if res.status_code == 200:
            return res.text
    except Exception as e:
        print(f"讀取 GID {gid} 失敗: {e}")
    return ""

def find_col(df, keywords):
    for kw in keywords:
        for col in df.columns:
            if kw.lower() in col.lower():
                return col
    return None

def fetch_and_parse():
    print("正在從主表解析血統與內建 DOD/淘汰日期...")
    raw_main_csv = fetch_sheet_csv(GID_MAIN)
    if not raw_main_csv:
        print("主表資料為空")
        return

    df_main = pd.read_csv(io.StringIO(raw_main_csv))
    df_main.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df_main.columns]

    col_ear = find_col(df_main, ['母豬耳號', '耳號', 'Ear Tag', 'Ear']) or df_main.columns[6] # Col G 通常是耳號
    col_sex = find_col(df_main, ['Sex', '性別'])
    col_parity = find_col(df_main, ['胎次', 'Parity'])
    col_mate = find_col(df_main, ['當胎配種公', '配種公豬', '當胎', '配種公'])
    col_breed = find_col(df_main, ['Breed', '品種', '品系'])
    col_mating_date = find_col(df_main, ['配種日期', '配種日', 'Mating Date'])
    col_farrow_date = find_col(df_main, ['分娩日期', '分娩日', 'farrowing date'])
    
    # 🌟 直接抓取主表內建的淘汰/死亡欄位 (Col L: DOD/淘汰日期)
    col_dod = find_col(df_main, ['DOD', '淘汰日期', '死亡日期'])

    pedigree_data = []
    official_death_set = set()

    for _, row in df_main.iterrows():
        ear = str(row.get(col_ear, '')).strip() if pd.notna(row.get(col_ear)) else ""
        if not ear or ear.lower() in ['nan', 'none', '-', '', 'null']:
            continue
        
        ear_upper = ear.upper()
        
        # 🌟 精準判定：只要 Col L (DOD) 有資料且不是空白，即代表死亡/淘汰
        dod_val = str(row.get(col_dod, '')).strip() if col_dod and pd.notna(row.get(col_dod)) else ""
        is_dead = False
        if dod_val and dod_val.lower() not in ['nan', 'none', '-', '', 'null']:
            is_dead = True
            official_death_set.add(ear_upper)

        breed = str(row.get(col_breed, '')).strip().upper() if pd.notna(row.get(col_breed)) else "D"
        if 'LY' in ear_upper: breed = 'LY'
        elif 'Y' in ear_upper and breed == 'D': breed = 'Y'
        elif 'L' in ear_upper and breed == 'D': breed = 'L'

        def get_v(col_name):
            if col_name and pd.notna(row.get(col_name)):
                val = str(row.get(col_name)).strip()
                return val if val.lower() not in ['nan', 'none', ''] else '-'
            return '-'

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": get_v(col_sex),
            "parity": get_v(col_parity),
            "mate": get_v(col_mate),
            "birth_date": get_v(find_col(df_main, ['DOB', '出生日期', '生日'])),
            "mating_date": get_v(col_mating_date),
            "dob": get_v(col_farrow_date),
            "is_dead": is_dead,
            "dod": dod_val if is_dead else "-",
            "spi": get_v(find_col(df_main, ['SPI'])),
            "mli": get_v(find_col(df_main, ['MLI'])),
            "tsi": get_v(find_col(df_main, ['TSI'])),
            "total_born": get_v(find_col(df_main, ['Total born', '總生產', '總生'])),
            "born_alive": get_v(find_col(df_main, ['Born alive', '活胎'])),
            "weaning": get_v(find_col(df_main, ['Weaning', '離乳'])),
            "mother_wt": get_v(find_col(df_main, ['mother total', '生育重'])),
            "weaning_wt": get_v(find_col(df_main, ['均重', 'weight'])),
            "tnb": get_v(find_col(df_main, ['TNB'])),
            "nba": get_v(find_col(df_main, ['NBA'])),
            "lteat": get_v(find_col(df_main, ['lteat', '左乳'])),
            "rteat": get_v(find_col(df_main, ['rteat', '右乳'])),
            "gen1_sire": get_v(find_col(df_main, ['第一代公', '1st Sire'])),
            "gen1_dam": get_v(find_col(df_main, ['第一代母', '1st Dam'])),
            "details": {str(k).strip(): (str(v).strip() if pd.notna(v) else "") for k, v in row.items()}
        }
        pedigree_data.append(entry)

    output_payload = {
        "pedigree": pedigree_data,
        "death_list": sorted(list(official_death_set))
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)
    print(f"data.json 輸出成功！共包含 {len(pedigree_data)} 筆資料，其中已精準標記 {len(official_death_set)} 頭死亡個體（如 D1405）。")

if __name__ == "__main__":
    fetch_and_parse()
