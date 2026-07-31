import json
import pandas as pd
import requests
import io

SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"
GID_TREE = "0"

# 使用 pub 導出與標準 csv 導出備用網址
URL_TREE = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID_TREE}"

def fetch_and_parse():
    print("🚀 開始從 Google Sheet 下載數據...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        res = requests.get(URL_TREE, headers=headers, timeout=15)
        res.encoding = 'utf-8-sig' # 處理 BOM 與萬國碼
        
        if res.status_code != 200:
            print(f"❌ 下載失敗，HTTP 狀態碼: {res.status_code}")
            return

        # 檢查是否被重定向到登入頁 HTML
        if "<html" in res.text.lower():
            print("❌ 抓取到 HTML 網頁而非 CSV，請確認 Google Sheet 已開啟『知道連結的任何人皆可存取』！")
            return

        df = pd.read_csv(io.StringIO(res.text))
        print(f"✅ 成功下載 CSV！原始資料總筆數：{len(df)}")
    except Exception as e:
        print(f"❌ 下載拋出例外錯誤: {e}")
        return

    if df.empty:
        print("⚠️ 警告：讀取到的 DataFrame 為空！")
        return

    # 清理所有欄位標題（移除空格、換行符號、特殊可見字元）
    df.columns = [str(c).replace('\n', '').replace('\r', '').strip() for c in df.columns]
    print("📋 抓取到的欄位標題：", list(df.columns))

    # 🎯 動態精確對應欄位 (模糊匹配，避免因空格錯字抓不到)
    def find_col(keywords):
        for kw in keywords:
            for col in df.columns:
                if kw in col:
                    return col
        return None

    col_ear = find_col(['耳號', 'C']) or df.columns[0]
    col_parity = find_col(['胎次', 'D'])
    col_mate = find_col(['當胎配種公', 'E'])
    col_dob = find_col(['出生日期', 'F'])
    col_sire_sire = find_col(['祖父', 'Z:Sire', 'Sire'])
    col_sire_dam = find_col(['祖母', 'AF:Dam', 'Dam'])
    col_dam_sire = find_col(['外公', 'AM:Sire'])
    col_dam_dam = find_col(['外婆', 'AS:Dam'])

    pedigree_data = []

    for idx, row in df.iterrows():
        ear = str(row.get(col_ear, '')).strip() if pd.notna(row.get(col_ear)) else ""
        
        # 過濾無效耳號
        if not ear or ear.lower() in ['nan', 'none', '-', '', 'null']:
            continue

        ear_upper = ear.upper()
        if 'LY' in ear_upper:
            breed = 'LY'
        elif 'YY' in ear_upper or ear_upper.startswith('Y'):
            breed = 'Y'
        elif 'LL' in ear_upper or ear_upper.startswith('L'):
            breed = 'L'
        else:
            breed = 'D'

        def get_str(col_name):
            if col_name and pd.notna(row.get(col_name)):
                val = str(row.get(col_name)).strip()
                return val if val.lower() not in ['nan', 'none', ''] else '-'
            return '-'

        sire_sire = get_str(col_sire_sire)
        sire_dam  = get_str(col_sire_dam)
        dam_sire  = get_str(col_dam_sire)
        dam_dam   = get_str(col_dam_dam)
        dob       = get_str(col_dob)
        parity    = get_str(col_parity)
        mate_sire = get_str(col_mate)

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": "FEMALE" if breed in ['LY', 'Y', 'L'] else "MALE",
            "parity": parity,
            "mate": mate_sire,
            "sire_sire": sire_sire,
            "sire_dam": sire_dam,
            "dam_sire": dam_sire,
            "dam_dam": dam_dam,
            "gen1_sire": mate_sire,
            "gen2_sire": "-",
            "details": {
                "Breed": breed,
                "Ear Tag": ear,
                "DOB": dob,
                "Parity": parity,
                "Mating Sire": mate_sire,
                "Sire_Sire": sire_sire,
                "Sire_Dam": sire_dam,
                "Dam_Sire": dam_sire,
                "Dam_Dam": dam_dam,
                "SPI": "-",
                "MLI": "-",
                "TSI": "-"
            }
        }
        pedigree_data.append(entry)

    print(f"🎉 成功轉換！共處理 {len(pedigree_data)} 筆有效耳號資料！")

    # 寫入 data.json
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fetch_and_parse()
