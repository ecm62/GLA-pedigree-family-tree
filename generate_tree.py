import json
import os
import pandas as pd

# 指定你的 Google Sheet ID 與網頁 ID (GID)
SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"
GID = "284410568"
GOOGLE_SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID}"

def fetch_data_and_generate():
    print("正在從 Google Sheet 擷取血統與詳細育種數據...")
    try:
        # 下載 CSV 格式資料
        df = pd.read_csv(GOOGLE_SHEET_CSV_URL)
        print("✅ 成功下載 Google Sheet 資料！")
    except Exception as e:
        print(f"❌ 下載失敗: {e}")
        df = pd.DataFrame()

    pedigree_data = []

    if not df.empty:
        # 清理欄位名稱空格
        df.columns = [str(c).strip() for c in df.columns]

        # 1. 識別關鍵欄位 (模糊對應繁簡中文與英文)
        ear_col = next((c for c in df.columns if '耳號' in c), None)
        sex_col = next((c for c in df.columns if 'Sex' in c or '性別' in c), None)
        breed_col = next((c for c in df.columns if 'Breed' in c or '品' in c), None)
        parity_col = next((c for c in df.columns if '胎次' in c or 'Parity' in c), None)
        mate_col = next((c for c in df.columns if '當胎配種公豬' in c), None)
        dob_col = next((c for c in df.columns if 'DOB' in c or '出生日期' in c), None)
        dod_col = next((c for c in df.columns if '淘汰日期' in c), None)

        # 指數欄位
        spi_col = next((c for c in df.columns if 'SPI' in c), None)
        mli_col = next((c for c in df.columns if 'MLI' in c), None)
        tsi_col = next((c for c in df.columns if 'TSI' in c), None)

        # 同胎成績欄位
        total_born_col = next((c for c in df.columns if 'total born' in c.lower() or '總生' in c), None)
        born_alive_col = next((c for c in df.columns if 'born alive' in c.lower() or '活胎' in c), None)
        weaning_num_col = next((c for c in df.columns if 'weaning' in c.lower() and 'weight' not in c.lower() and '數量' in c), None)
        weaning_weight_col = next((c for c in df.columns if 'weaning weight' in c.lower() or '均重' in c), None)

        # 2. 祖輩與世代欄位 (最重要)
        sire_sire_col = next((c for c in df.columns if 'Sire 美系父親名(祖父)' in c or '祖父' in c), None)
        sire_dam_col = next((c for c in df.columns if 'Dam Name 美系母親名(祖母)' in c or '祖母' in c), None)
        dam_sire_col = next((c for c in df.columns if 'Sire 美系父親名(外公)' in c or '外公' in c), None)
        dam_dam_col = next((c for c in df.columns if 'Dam Name 美系母親名(外婆)' in c or '外婆' in c), None)
        gen1_col = next((c for c in df.columns if '第一代公' in c), None)
        gen2_col = next((c for c in df.columns if '第二代公' in c), None)

        # 3. 遍歷 Excel 資料列
        for _, row in df.iterrows():
            # 將該列所有資料轉為字串並清理 nan
            row_dict = {k: (str(v).strip() if pd.notna(v) and str(v).lower() != 'nan' else "") for k, v in row.to_dict().items()}
            
            # 抓取主角耳號 (精確去除空格)
            ear_tag = row_dict.get(ear_col, "").strip()
            if not ear_tag or ear_tag.lower() == 'nan':
                continue

            # 安全抓取各項成績與指數防止 undefined
            details = {
                "ear": ear_tag,
                "breed": row_dict.get(breed_col, "D").strip().upper(), # 品種
                "sex": row_dict.get(sex_col, "FEMALE").strip().upper(), # 性別
                "dob": row_dict.get(dob_col, "-"), # 生日
                "dod": row_dict.get(dod_col, "-"), # 淘汰日期
                "spi": row_dict.get(spi_col, "-"), 
                "mli": row_dict.get(mli_col, "-"), 
                "tsi": row_dict.get(tsi_col, "-"),
                "parity": row_dict.get(parity_col, "-"), # 胎次
                "mate": row_dict.get(mate_col, "-"), # 配種公
                "total_born": row_dict.get(total_born_col, "-"), # 總產
                "born_alive": row_dict.get(born_alive_col, "-"), # 活胎
                "weaning_num": row_dict.get(weaning_num_col, "-"), # 離乳數
                "weaning_weight": row_dict.get(weaning_weight_col, "-"), # 均重
                # 標準階梯世系欄位 (最重要)
                "sire_sire": row_dict.get(sire_sire_col, "-"), # 祖父
                "sire_dam": row_dict.get(sire_dam_col, "-"),   # 祖母
                "dam_sire": row_dict.get(dam_sire_col, "-"),   # 外公
                "dam_dam": row_dict.get(dam_dam_col, "-"),     # 外婆
                "gen1": row_dict.get(gen1_col, "-"),           # 第一代
                "gen2": row_dict.get(gen2_col, "-"),           # 第二代
                # 原始資料備份用於更進階搜尋
                "raw": row_dict 
            }
            pedigree_data.append(details)

    # 4. 將清理好的資料寫入 data.json
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)
    print(f"✅ 已成功整理並且封裝 {len(pedigree_data)} 筆資料至 data.json！")

if __name__ == "__main__":
    fetch_data_and_generate()
