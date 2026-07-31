import json
import pandas as pd

# Google Sheet CSV 下載網址
SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"
GID = "284410568"
GOOGLE_SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID}"

def fetch_data_and_generate():
    print("正在從 Google Sheet 擷取血統與數據...")
    try:
        # 強制指定 encoding 與抓取 CSV
        df = pd.read_csv(GOOGLE_SHEET_CSV_URL)
        print(f"✅ 成功下載資料！共取得 {len(df)} 行數據。")
    except Exception as e:
        print(f"❌ 讀取失敗: {e}")
        df = pd.DataFrame()

    pedigree_data = []

    if not df.empty:
        # 清理欄位名稱標題的空白空格
        df.columns = [str(c).replace('\n', '').strip() for c in df.columns]

        # 靈活匹配欄位標題 (降低名稱精準度要求)
        ear_col = next((c for c in df.columns if '耳號' in c), df.columns[1] if len(df.columns) > 1 else None)
        sex_col = next((c for c in df.columns if 'sex' in c.lower() or '性別' in c), None)
        breed_col = next((c for c in df.columns if 'breed' in c.lower() or '品' in c), None)
        parity_col = next((c for c in df.columns if '胎次' in c or 'parity' in c.lower()), None)
        mate_col = next((c for c in df.columns if '配種公' in c), None)

        sire_sire_col = next((c for c in df.columns if '祖父' in c or ('sire' in c.lower() and '外' not in c and '母' not in c)), None)
        sire_dam_col = next((c for c in df.columns if '祖母' in c or ('dam' in c.lower() and '外' not in c)), None)
        dam_sire_col = next((c for c in df.columns if '外公' in c), None)
        dam_dam_col = next((c for c in df.columns if '外婆' in c), None)

        gen1_sire_col = next((c for c in df.columns if '第一代' in c or '1代' in c), None)
        gen2_sire_col = next((c for c in df.columns if '第二代' in c or '2代' in c), None)

        for _, row in df.iterrows():
            row_dict = {k: (str(v).strip() if pd.notna(v) else "") for k, v in row.to_dict().items()}
            
            ear_tag = ""
            if ear_col and pd.notna(row[ear_col]):
                ear_tag = str(row[ear_col]).strip()

            # 若抓不到耳號標題，備用逐欄尋找耳號樣式
            if not ear_tag or ear_tag.lower() == 'nan':
                for col_name in df.columns:
                    val_str = str(row[col_name]).strip()
                    if val_str and val_str.lower() != 'nan' and ('DD' in val_str.upper() or 'LY' in val_str.upper() or 'D' in val_str.upper()):
                        ear_tag = val_str
                        break

            if not ear_tag or ear_tag.lower() == 'nan':
                continue

            breed_val = "D"
            if breed_col and pd.notna(row[breed_col]):
                b_str = str(row[breed_col]).strip().upper()
                if b_str and b_str != 'NAN':
                    breed_val = b_str

            entry = {
                "ear": ear_tag,
                "breed": breed_val,
                "sex": str(row[sex_col]).strip() if sex_col and pd.notna(row[sex_col]) else "",
                "parity": str(row[parity_col]).strip() if parity_col and pd.notna(row[parity_col]) else "-",
                "mate": str(row[mate_col]).strip() if mate_col and pd.notna(row[mate_col]) else "-",
                "sire_sire": str(row[sire_sire_col]).strip() if sire_sire_col and pd.notna(row[sire_sire_col]) else "-",
                "sire_dam": str(row[sire_dam_col]).strip() if sire_dam_col and pd.notna(row[sire_dam_col]) else "-",
                "dam_sire": str(row[dam_sire_col]).strip() if dam_sire_col and pd.notna(row[dam_sire_col]) else "-",
                "dam_dam": str(row[dam_dam_col]).strip() if dam_dam_col and pd.notna(row[dam_dam_col]) else "-",
                "gen1_sire": str(row[gen1_sire_col]).strip() if gen1_sire_col and pd.notna(row[gen1_sire_col]) else "-",
                "gen2_sire": str(row[gen2_sire_col]).strip() if gen2_sire_col and pd.notna(row[gen2_sire_col]) else "-",
                "details": row_dict
            }
            pedigree_data.append(entry)

    print(f"解析成功！共產生 {len(pedigree_data)} 筆血統資料。")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fetch_data_and_generate()
