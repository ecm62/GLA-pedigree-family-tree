import json
import os
import pandas as pd

# 指定你的 Google Sheet 網址（自動轉換 CSV 格式）
SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"
GID = "284410568"
GOOGLE_SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID}"

def fetch_data_and_generate():
    print("正在從 Google Sheet 下載最新數據...")
    try:import json
import os
import pandas as pd

SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"
GID = "284410568"
GOOGLE_SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID}"

def fetch_data_and_generate():
    print("正在從 Google Sheet 擷取血統與階梯欄位...")
    try:
        df = pd.read_csv(GOOGLE_SHEET_CSV_URL)
        print("✅ 成功下載 Google Sheet 資料！")
    except Exception as e:
        print(f"❌ 讀取失敗: {e}")
        df = pd.DataFrame()

    pedigree_data = {}

    if not df.empty:
        df.columns = [str(c).strip() for c in df.columns]

        ear_col = next((c for c in df.columns if '耳號' in c), None)
        sex_col = next((c for c in df.columns if 'Sex' in c or '性別' in c), None)
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

            mate_sire = str(row[mate_col]).strip() if mate_col and pd.notna(row[mate_col]) else ""
            
            # 初始化耳號節點
            if ear_tag not in pedigree_data:
                pedigree_data[ear_tag] = {
                    "ear": ear_tag,
                    "sex": str(row[sex_col]).strip() if sex_col and pd.notna(row[sex_col]) else "",
                    "sire_sire": str(row[sire_sire_col]).strip() if sire_sire_col and pd.notna(row[sire_sire_col]) else "-",
                    "sire_dam": str(row[sire_dam_col]).strip() if sire_dam_col and pd.notna(row[sire_dam_col]) else "-",
                    "dam_sire": str(row[dam_sire_col]).strip() if dam_sire_col and pd.notna(row[dam_sire_col]) else "-",
                    "dam_dam": str(row[dam_dam_col]).strip() if dam_dam_col and pd.notna(row[dam_dam_col]) else "-",
                    "gen1_sire": str(row[gen1_sire_col]).strip() if gen1_sire_col and pd.notna(row[gen1_sire_col]) else "-",
                    "gen2_sire": str(row[gen2_sire_col]).strip() if gen2_sire_col and pd.notna(row[gen2_sire_col]) else "-",
                    "details": row_dict,
                    "records": []
                }

            # 紀錄多筆當胎配種資料
            if mate_sire:
                pedigree_data[ear_tag]["records"].append({
                    "parity": str(row[parity_col]) if parity_col and pd.notna(row[parity_col]) else "-",
                    "mate": mate_sire,
                    "gen1": str(row[gen1_sire_col]).strip() if gen1_sire_col and pd.notna(row[gen1_sire_col]) else "-",
                    "gen2": str(row[gen2_sire_col]).strip() if gen2_sire_col and pd.notna(row[gen2_sire_col]) else "-"
                })

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)
    print(f"✅ 已成功轉換血統世系結構至 data.json！")

if __name__ == "__main__":
    fetch_data_and_generate()
        df = pd.read_csv(GOOGLE_SHEET_CSV_URL)
        print("✅ 成功下載 Google Sheet 資料！")
    except Exception as e:
        print(f"❌ 下載失敗: {e}")
        df = pd.DataFrame()

    nodes = {}
    edges = []

    if not df.empty:
        df.columns = [str(c).strip() for c in df.columns]

        ear_col = next((c for c in df.columns if '耳號' in c), None)
        sex_col = next((c for c in df.columns if 'Sex' in c or '性別' in c), None)
        breed_col = next((c for c in df.columns if 'Breed' in c or '品' in c), None)
        parity_col = next((c for c in df.columns if '胎次' in c or 'Parity' in c), None)
        mate_col = next((c for c in df.columns if '當胎配種公豬' in c), None)

        gen1_sire_col = next((c for c in df.columns if '第一代公' in c), None)
        gen1_dam_col = next((c for c in df.columns if '第一代母' in c), None)
        gen2_sire_col = next((c for c in df.columns if '第二代公' in c), None)
        gen2_dam_col = next((c for c in df.columns if '第二代母' in c), None)
        gen3_col = next((c for c in df.columns if '第三代' in c), None)

        def add_node(node_id, label, gen_num=1, sex="FEMALE", raw_details=None, is_mate=False):
            if node_id and str(node_id).strip().lower() != 'nan' and str(node_id).strip() != '':
                nid = str(node_id).strip()
                s_type = str(sex).upper() if sex else ""
                shape = "box" if "MALE" in s_type or "公" in s_type else "ellipse"
                
                breed_val = "D"
                if breed_col and raw_details and breed_col in raw_details:
                    b_str = str(raw_details[breed_col]).strip().upper()
                    if b_str and b_str != 'NAN': breed_val = b_str

                if nid not in nodes:
                    nodes[nid] = {
                        "id": nid,
                        "label": str(label).strip(),
                        "gen_num": int(gen_num),
                        "is_mate": is_mate,
                        "shape": shape,
                        "breed": breed_val,
                        "details": raw_details if raw_details else {"耳號": nid, "Breed": breed_val}
                    }

        def add_edge(source, target, relation="", parity=""):
            s_str, t_str = str(source).strip(), str(target).strip()
            if s_str and t_str and s_str.lower() != 'nan' and t_str.lower() != 'nan':
                edges.append({
                    "from": s_str,
                    "to": t_str,
                    "label": relation,
                    "parity": str(parity) if pd.notna(parity) else ""
                })

        for _, row in df.iterrows():
            row_dict = {k: (str(v) if pd.notna(v) else "") for k, v in row.to_dict().items()}
            ear_tag = str(row[ear_col]).strip() if ear_col and pd.notna(row[ear_col]) else ""
            
            g1_sire = str(row[gen1_sire_col]).strip() if gen1_sire_col and pd.notna(row[gen1_sire_col]) else ""
            g1_dam = str(row[gen1_dam_col]).strip() if gen1_dam_col and pd.notna(row[gen1_dam_col]) else ""
            g2_sire = str(row[gen2_sire_col]).strip() if gen2_sire_col and pd.notna(row[gen2_sire_col]) else ""
            g2_dam = str(row[gen2_dam_col]).strip() if gen2_dam_col and pd.notna(row[gen2_dam_col]) else ""
            g3 = str(row[gen3_col]).strip() if gen3_col and pd.notna(row[gen3_col]) else ""

            target_id = g3 if g3 else ear_tag
            if not target_id or target_id.lower() == 'nan':
                continue

            sex_val = row[sex_col] if sex_col and pd.notna(row[sex_col]) else "FEMALE"
            parity = row[parity_col] if parity_col and pd.notna(row[parity_col]) else ""
            mate_sire = str(row[mate_col]).strip() if mate_col and pd.notna(row[mate_col]) else ""

            # 建立第一代
            if g1_sire: add_node(g1_sire, f"1代公:{g1_sire}", gen_num=1, sex="MALE", raw_details={"耳號": g1_sire, "Breed": "D"})
            if g1_dam: add_node(g1_dam, f"1代母:{g1_dam}", gen_num=1, sex="FEMALE", raw_details={"耳號": g1_dam, "Breed": "D"})

            # 建立第二代
            if g2_sire:
                add_node(g2_sire, f"2代公:{g2_sire}", gen_num=2, sex="MALE", raw_details={"耳號": g2_sire, "Breed": "D"})
                if g1_sire: add_edge(g1_sire, g2_sire, "父")
                if g1_dam: add_edge(g1_dam, g2_sire, "母")

            if g2_dam:
                add_node(g2_dam, f"2代母:{g2_dam}", gen_num=2, sex="FEMALE", raw_details={"耳號": g2_dam, "Breed": "D"})
                if g1_sire: add_edge(g1_sire, g2_dam, "父")
                if g1_dam: add_edge(g1_dam, g2_dam, "母")

            # 建立第三代
            add_node(target_id, target_id, gen_num=3, sex=sex_val, raw_details=row_dict)
            if g2_sire: add_edge(g2_sire, target_id, "父")
            if g2_dam: add_edge(g2_dam, target_id, "母")

            # 當胎配種公
            if mate_sire:
                add_node(mate_sire, f"配種公:{mate_sire}", gen_num=2, sex="MALE", raw_details={"耳號": mate_sire, "Breed": "D"}, is_mate=True)
                edge_label = f"第{int(parity)}胎配種" if pd.notna(parity) and str(parity).isdigit() else "配種"
                add_edge(mate_sire, target_id, edge_label)

    data_payload = {
        "nodes": list(nodes.values()),
        "edges": edges
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data_payload, f, ensure_ascii=False, indent=2)
    print(f"✅ 已成功封裝 {len(nodes)} 個節點至 data.json！")

if __name__ == "__main__":
    fetch_data_and_generate()
