import json
import pandas as pd
import requests
import io

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

    # 清理欄位名稱中的空格與換行
    df.columns = [str(c).replace('\n', '').replace('\r', '').strip() for c in df.columns]

    # 彈性尋找欄位名稱的輔助函數
    def find_col(df, keywords):
        for kw in keywords:
            for col in df.columns:
                if kw.lower() in col.lower():
                    return col
        return None

    col_ear = find_col(df, ['耳號', 'Ear'])
    col_dob = find_col(df, ['DOB', '出生日期', '生日'])
    col_farrow = find_col(df, ['分娩日期', 'farrow'])
    col_parity = find_col(df, ['胎次', 'parity'])
    col_mate = find_col(df, ['配種公', 'mate', '當胎'])
    col_breed = find_col(df, ['breed', '品種'])

    birth_map = {}
    for _, row in df.iterrows():
        if col_ear and col_dob:
            ear = str(row.get(col_ear, '')).strip().upper()
            dob = str(row.get(col_dob, '')).strip()
            if ear and dob and dob.lower() not in ['nan', 'none', '-']:
                birth_map[ear] = dob

    pedigree_data = []
    for _, row in df.iterrows():
        ear = str(row.get(col_ear, '')).strip() if col_ear else ''
        if not ear or ear.lower() in ['nan', 'none', '-']: 
            continue
        
        breed = str(row.get(col_breed, 'D')).strip().upper() if col_breed else 'D'
        is_ly = breed == 'LY' or 'LY' in ear.upper()
        
        entry = {
            "ear": ear,
            "breed": breed,
            "birth_date": birth_map.get(ear.upper(), '-') if not is_ly else '-',
            "dob": str(row.get(col_farrow, '-')) if col_farrow else '-',
            "parity": str(row.get(col_parity, '-')) if col_parity else '-',
            "mate": str(row.get(col_mate, '-')) if col_mate else '-',
            "details": {str(k).strip(): (str(v).strip() if pd.notna(v) else "") for k, v in row.items()}
        }
        pedigree_data.append(entry)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)
    print(f"✅ 成功寫入 data.json，共 {len(pedigree_data)} 筆紀錄")

if __name__ == "__main__":
    fetch_and_parse()
