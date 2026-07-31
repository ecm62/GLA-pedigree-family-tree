import json
import pandas as pd
import requests
import io

# 🌟 指定 Google Sheet ID 與三個工作表 (GID) 的 CSV 導出網址
SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"

# 1. 家族樹 (模式B)
GID_TREE = "0"
# 2. 母豬育種價值分析
GID_INDEX = "1872161273"  # 若您有專屬 GID，可替換；此處同時支援備用合併邏輯

URL_TREE = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID_TREE}"

def fetch_and_parse():
    print("🚀 開始從 Google Sheet 下載精確數據...")
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        res = requests.get(URL_TREE, headers=headers)
        res.encoding = 'utf-8'
        if res.status_code != 200:
            print(f"❌ 下載失敗，HTTP 狀態碼: {res.status_code}")
            return
        
        df = pd.read_csv(io.StringIO(response.text if 'response' in locals() else res.text))
        print(f"✅ 成功讀取 CSV！總共有 {len(df)} 筆個體資料。")
    except Exception as e:
        print(f"❌ 讀取發生例外錯誤: {e}")
        return

    # 清除欄位首尾空白標題
    df.columns = [str(c).strip() for c in df.columns]

    # 🎯 確切對齊抓取到的欄位名稱
    EAR_COL = "耳號 (C)"
    PARITY_COL = "胎次 (D)"
    MATE_COL = "當胎配種公 (E)"
    DOB_COL = "出生日期 (F)"
    SIRE_SIRE_COL = "祖父 (Z:Sire)"
    SIRE_DAM_COL = "祖母 (AF:Dam)"
    DAM_SIRE_COL = "外公 (AM:Sire)"
    DAM_DAM_COL = "外婆 (AS:Dam)"

    pedigree_data = []

    for idx, row in df.iterrows():
        # 抓取主角耳號
        ear = str(row.get(EAR_COL, '')).strip() if pd.notna(row.get(EAR_COL)) else ""
        
        if not ear or ear.lower() in ['nan', 'none', '-', '']:
            continue

        # 自動判斷品種 (依據耳號字首)
        ear_upper = ear.upper()
        if 'LY' in ear_upper:
            breed = 'LY'
        elif 'YY' in ear_upper or ear_upper.startswith('Y'):
            breed = 'Y'
        elif 'LL' in ear_upper or ear_upper.startswith('L'):
            breed = 'L'
        else:
            breed = 'D'  # 預設為杜洛克 (D)

        # 抓取祖輩血統名稱
        sire_sire = str(row.get(SIRE_SIRE_COL, '-')).strip() if pd.notna(row.get(SIRE_SIRE_COL)) else "-"
        sire_dam  = str(row.get(SIRE_DAM_COL, '-')).strip() if pd.notna(row.get(SIRE_DAM_COL)) else "-"
        dam_sire  = str(row.get(DAM_SIRE_COL, '-')).strip() if pd.notna(row.get(DAM_SIRE_COL)) else "-"
        dam_dam   = str(row.get(DAM_DAM_COL, '-')).strip() if pd.notna(row.get(DAM_DAM_COL)) else "-"
        
        dob       = str(row.get(DOB_COL, '-')).strip() if pd.notna(row.get(DOB_COL)) else "-"
        parity    = str(row.get(PARITY_COL, '-')).strip() if pd.notna(row.get(PARITY_COL)) else "-"
        mate_sire = str(row.get(MATE_COL, '-')).strip() if pd.notna(row.get(MATE_COL)) else "-"

        # 建立格式化個體字典
        entry = {
            "ear": ear,
            "breed": breed,
            "sex": "FEMALE" if breed in ['LY', 'Y', 'L'] else "MALE",
            "parity": parity,
            "mate": mate_sire,
            "sire_sire": sire_sire if sire_sire != "" else "-",
            "sire_dam": sire_dam if sire_dam != "" else "-",
            "dam_sire": dam_sire if dam_sire != "" else "-",
            "dam_dam": dam_dam if dam_dam != "" else "-",
            "gen1_sire": mate_sire if mate_sire != "" else "-",
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

    print(f"🎉 成功轉換！共抓取到 {len(pedigree_data)} 筆完整的個體血統數據！")

    # 寫入 data.json
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fetch_and_parse()
