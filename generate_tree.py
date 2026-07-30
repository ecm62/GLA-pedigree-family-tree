import json
import os
import pandas as pd

SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"
GID = "284410568"
GOOGLE_SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID}"

def fetch_data_and_generate():
    print("正在從 Google Sheet 擷取血統與數據...")
    try:
        df = pd.read_csv(GOOGLE_SHEET_CSV_URL)
        print("✅ 成功下載 Google Sheet 資料！")
    except Exception as e:
        print(f"❌ 讀取失敗: {e}")
        df = pd.DataFrame()

    pedigree_data = []

    if not df.empty:
        df.columns = [str(c).strip() for c in df.columns]

        ear_col = next((c for c in df.columns if '耳號' in c), None)
        sex_col = next((c for c in df.columns if 'Sex' in c or '性別' in c), None)
        breed_col = next((c for c in df.columns if 'Breed' in c or '品' in c), None)
        parity_col = next((c for c in df.columns if '胎次' in c or 'Parity' in c), None)
        mate_col = next((c for c in df.columns if '當胎配種公豬' in c), None)

        # 祖輩欄位
        sire_sire_col = next((c for c in df.columns if '祖父' in c or 'Sire 美系父親名' in c), None)
        sire_dam_col = next((c for c in df.columns if '祖母' in c or 'Dam Name 美系母親名' in c and '外' not in c), None)
        dam_sire_col = next((c for c in df.columns if '外公' in c), None)
        dam_dam_col = next((c for c in df.columns if '外婆' in c), None)

        # 世代欄位
        gen1_sire_col = next((c for c in df.columns if '第一代公' in c), None)
        gen2_sire_col = next((c for c in df.columns if '第二代公' in c), None)

        for _, row in df.iterrows():
            row_dict = {k: (str(v) if pd.notna(v) else "") for k, v in row.to_dict().items()}
            ear_tag = str(row[ear_col]).strip() if ear_col and pd.notna(row[ear_col]) else ""
            
            if not ear_tag or ear_tag.lower() == 'nan':
                continue

            breed_val = str(row[breed_col]).strip().upper() if breed_col and pd.notna(row[breed_col]) else "D"

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

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)
    print(f"✅ 已成功轉換 {len(pedigree_data)} 筆資料至 data.json！")

if __name__ == "__main__":
    fetch_data_and_generate()
