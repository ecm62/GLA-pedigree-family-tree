import json
import pandas as pd
import requests
import io
import re

SPREADSHEET_ID = "1MlhcSXitL_jWYvXVfmo6bQfQqDPIDgUt0VGIZVaB5aw"
GID_MAIN = "0"                 # 📊 育種_家族階層清單
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

def fetch_and_parse():
    print("🚀 正在精確掃描【📊 育種_家族階層清單】Col L (DOD/淘汰日期)...")
    
    raw_main_csv = fetch_sheet_csv(GID_MAIN)
    if not raw_main_csv:
        print("❌ 主表資料為空！")
        return

    df_main = pd.read_csv(io.StringIO(raw_main_csv))
    # 清理所有欄位名稱的多餘換行與空格
    df_main.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df_main.columns]

    # 1. 🌟 精確鎖定耳號欄位與 Col L (DOD/淘汰日期)
    col_ear = None
    for c in df_main.columns:
        if c in ['耳號', '母豬耳號', 'Ear Tag', 'Ear']:
            col_ear = c
            break
    if not col_ear:
        col_ear = df_main.columns[6] # Col G 通常是耳號欄位

    # 尋找 Col L: DOD/淘汰日期
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

    def find_col(df, keywords):
        for kw in keywords:
            for col in df.columns:
                if kw.lower() in col.lower():
                    return col
        return None

    col_sex = find_col(df_main, ['Sex', '性別'])
    col_parity = find_col(df_main, ['胎次', 'Parity'])
    col_mate = find_col(df_main, ['當胎配種公', '配種公豬', '當胎', '配種公'])
    col_breed = find_col(df_main, ['Breed', '品種', '品系'])
    col_mating_date = find_col(df_main, ['配種日期', '配種日', 'Mating Date'])
    col_farrow_date = find_col(df_main, ['當胎分娩日', '分娩日期', '分娩日'])
    col_dob = find_col(df_main, ['DOB出生日期', 'DOB', '出生日期', '生日'])

    pedigree_data = []
    death_map = {} # { "D1405": "2024-04-11 ⚫ (Die)" }

    for idx, row in df_main.iterrows():
        ear = str(row.get(col_ear, '')).strip() if pd.notna(row.get(col_ear)) else ""
        if not ear or ear.lower() in ['nan', 'none', '-', '', 'null']:
            continue
        
        ear_upper = ear.upper()

        # 🌟 2. 嚴格檢查 Col L (DOD/淘汰日期)
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

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": get_v(col_sex),
            "parity": get_v(col_parity),
            "mate": get_v(col_mate),
            "birth_date": get_v(col_dob),
            "mating_date": get_v(col_mating_date),
            "dob": get_v(col_farrow_date),
            "is_dead": is_dead,
            "dod": dod_clean, # 🌟 寫入完整的淘汰字串，例如 2024-04-11 ⚫ (Die)
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

    # 輸出結構化資料
    output_payload = {
        "pedigree": pedigree_data,
        "death_map": death_map # 包含全部已淘汰/死亡豬隻的完整 DOD 字典
    }

    print(f"💀 成功從 Col L 提取出 {len(death_map)} 筆淘汰/死亡個體！")
    if "D1405" in death_map:
        print(f"🎯 確認抓取到 D1405: {death_map['D1405']}")
    else:
        print("⚠️ 警告：仍未在 Col L 找到 D1405，請確認 Col L 標題或試算表狀態")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)
    print("✅ 已成功寫入 data.json！")

if __name__ == "__main__":
    fetch_and_parse()
