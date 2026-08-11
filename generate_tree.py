import json
import pandas as pd
import requests
import io

SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"
GID_TREE = "0"
URL_TREE = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID_TREE}"

def fetch_and_parse():
    try:
        res = requests.get(URL_TREE, headers={'User-Agent': 'Mozilla/5.0'})
        res.encoding = 'utf-8-sig'
        df = pd.read_csv(io.StringIO(res.text))
        df.columns = [str(c).strip() for c in df.columns]
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    pedigree_data = []
    for _, row in df.iterrows():
        # 這是您原始結構中對應每一列資料的方式
        entry = {
            "ear": str(row.get('耳號', '')).strip(),
            "breed": str(row.get('Breed', 'D')).strip().upper(),
            "birth_date": str(row.get('出生日期', '-')),
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
