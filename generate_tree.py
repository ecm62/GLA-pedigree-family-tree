import json
import pandas as pd
import requests
import io

SPREADSHEET_ID = "1MlhcSXitL_jWYvXVfmo6bQfQqDPIDgUt0VGIZVaB5aw"
GID_MAIN = "0"  # 📊 育種_家族階層清單

def fetch_sheet_csv(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
    res.encoding = 'utf-8-sig'
    return res.text if res.status_code == 200 else ""

def fetch_and_parse():
    raw_csv = fetch_sheet_csv(GID_MAIN)
    if not raw_csv:
        print("讀取失敗")
        return

    # 直接無頭讀取純表格矩陣
    df = pd.read_csv(io.StringIO(raw_csv), header=None)
    
    pedigree_data = []
    death_map = {}

    # 逐列處理：第 6 欄是耳號(Col G)，第 11 欄是淘汰日期(Col L)
    for idx, row in df.iterrows():
        if idx < 1:  # 略過第一列標題
            continue
            
        ear = str(row[6]).strip() if pd.notna(row[6]) else ""
        if not ear or ear.lower() in ['nan', 'none', '-', '', '耳號']:
            continue
            
        ear_upper = ear.upper()
        
        # 🌟 直接抽 Col L (Index 11) 的值
        dod_raw = str(row[11]).strip() if len(row) > 11 and pd.notna(row[11]) else ""
        is_dead = False
        dod_clean = "-"

        if dod_raw and dod_raw.lower() not in ['nan', 'none', '-', '', 'null', 'dod/淘汰日期']:
            is_dead = True
            dod_clean = dod_raw
            death_map[ear_upper] = dod_clean

        pedigree_data.append({
            "ear": ear,
            "breed": "D" if ear_upper.startswith("D") else ("Y" if ear_upper.startswith("Y") else "L"),
            "sex": str(row[4]).strip() if len(row) > 4 and pd.notna(row[4]) else "MALE",  # Col E
            "birth_date": str(row[10]).strip() if len(row) > 10 and pd.notna(row[10]) else "-",  # Col K
            "is_dead": is_dead,
            "dod": dod_clean
        })

    print(f"解析完成，共 {len(pedigree_data)} 筆，死亡/淘汰共 {len(death_map)} 筆")
    if "D1405" in death_map:
        print(f"確認抽到 D1405: {death_map['D1405']}")
    else:
        print("仍未在 Col L 找到 D1405，請檢查列資料")

    output_payload = {
        "pedigree": pedigree_data,
        "death_map": death_map
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fetch_and_parse()
