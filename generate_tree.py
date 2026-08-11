import json
import pandas as pd
import requests
import io

# 請確保 SPREADSHEET_ID 與 URL 設定正確
SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"
GID_TREE = "0"
URL_TREE = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID_TREE}"

def fetch_and_parse():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(URL_TREE, headers=headers)
        res.encoding = 'utf-8-sig'
        df = pd.read_csv(io.StringIO(res.text))
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    df.columns = [str(c).strip() for c in df.columns]
    
    # 建立一個 ear -> birth_date 的對照表
    # 我們只從有明確 DOB 的欄位抓取原始出生日
    birth_map = {}
    for _, row in df.iterrows():
        ear = str(row.get('耳號', '')).strip().upper()
        dob = str(row.get('DOB', '')).strip()
        if ear and dob and dob.lower() not in ['nan', 'none', '-']:
            birth_map[ear] = dob

    pedigree_data = []
    for _, row in df.iterrows():
        ear = str(row.get('耳號', '')).strip()
        if not ear or ear.lower() in ['nan', 'none', '-']: continue
        
        breed = str(row.get('Breed', 'D')).strip().upper()
        # LY 個體一律不應有上游親代資訊，確保資料乾淨
        is_ly = breed == 'LY' or 'LY' in ear.upper()
        
        entry = {
            "ear": ear,
            "breed": breed,
            "birth_date": birth_map.get(ear.upper(), '-') if not is_ly else '-', # 只有非LY才對照生日
            "dob": str(row.get('分娩日期', '-')),
            "parity": str(row.get('胎次', '-')),
            "mate": str(row.get('當胎配種公豬', '-')),
            "details": row.to_dict()
        }
        pedigree_data.append(entry)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fetch_and_parse()
