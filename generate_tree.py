import re
import json
import pandas as pd

# ==========================================
# 1. Google Sheets 資料來源與設定
# ==========================================
SHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

# 品系主題配色設定
BREED_CONFIGS = {
    "D": {"name": "杜洛克 (Duroc)", "colors": {"child": "#e74c3c", "sire": "#c0392b", "dam": "#f1948a"}},
    "Y": {"name": "約克夏 (Yorkshire)", "colors": {"child": "#3498db", "sire": "#2980b9", "dam": "#85c1e9"}},
    "L": {"name": "藍瑞斯 (Landrace)", "colors": {"child": "#2ecc71", "sire": "#27ae60", "dam": "#82e0aa"}}
}
DEFAULT_COLORS = {"child": "#95a5a6", "sire": "#7f8c8d", "dam": "#bdc3c7"}

# ==========================================
# 🧹 名稱清洗小工具（專門拿掉前綴與後綴編號）
# ==========================================
def clean_name(name_str):
    if not name_str or str(name_str).strip() in ['-', 'nan', 'None', '']:
        return ""

    name_str = str(name_str).strip()
    # 1. 移除最後面的個體/胎次編號（例如 488-8, 1096-1）
    name_clean = re.sub(r'\s*\d+-\d+\s*$', '', name_str)
    # 2. 移除最前面的開頭代號（例如 1CR2, CR2, 1CR1 等）
    name_clean = re.sub(r'^\s*([0-9]?[A-Z]{2,4}[0-9]?)\s*', '', name_clean)
    name_clean = name_clean.strip()

    return name_clean if name_clean else name_str

# ==========================================
# 2. 主運算流程
# ==========================================
def generate_graph_data():
    print("⏳ 正在從 Google Sheets 下載與解析資料...")
    try:
        df_tree = pd.read_csv(SHEET_URL)
    except Exception as e:
        print(f"❌ 下載失敗: {e}")
        return

    # 清理欄位名稱中的空格與換行符號
    df_tree.columns = [str(c).strip().replace('\n', '') for c in df_tree.columns]

    # 鎖定欄位：個體耳號、父親名 (祖父)、母親名 (祖母)
    col_ear = next((c for c in df_tree.columns if "耳號" in c or "Ear" in c), df_tree.columns[0])
    col_sire = next((c for c in df_tree.columns if "祖父" in c or "Sire" in c), df_tree.columns[4] if len(df_tree.columns) > 4 else df_tree.columns[0])
    col_dam = next((c for c in df_tree.columns if "祖母" in c or "Dam" in c), df_tree.columns[5] if len(df_tree.columns) > 5 else df_tree.columns[0])

    nodes_dict = {}
    edges_list = []
    added_edges = set()

    for _, row in df_tree.iterrows():
        child_raw = str(row[col_ear]).strip()
        if not child_raw or child_raw in ['nan', 'None', '-']:
            continue

        sire_raw = str(row[col_sire]).strip()
        dam_raw = str(row[col_dam]).strip()

        # 名稱清洗
        sire = clean_name(sire_raw)
        dam = clean_name(dam_raw)

        # 判定品系配色 (根據耳號第一個字母 D, Y, L)
        breed_code = child_raw[0].upper() if child_raw else ""
        theme = BREED_CONFIGS.get(breed_code, {"name": "其他", "colors": DEFAULT_COLORS})["colors"]

        # 1. 建立子代節點
        if child_raw not in nodes_dict:
            nodes_dict[child_raw] = {
                'id': child_raw,
                'label': child_raw,
                'shape': 'circle',
                'color': theme['child'],
                'size': 20,
                'title': f"耳號: {child_raw}\n品系代號: {breed_code}"
            }

        # 2. 建立父系節點（方形）與連線
        if sire:
            if sire not in nodes_dict:
                nodes_dict[sire] = {
                    'id': sire,
                    'label': f"父: {sire}",
                    'shape': 'square',
                    'color': theme['sire'],
                    'size': 24,
                    'title': f"父系原名: {sire_raw}"
                }
            edge_key = (sire, child_raw)
            if edge_key not in added_edges:
                edges_list.append({
                    'from': sire,
                    'to': child_raw,
                    'color': '#e74c3c',
                    'width': 1.5,
                    'title': f"父系: {sire_raw}"
                })
                added_edges.add(edge_key)

        # 3. 建立母系節點（橢圓形）與連線
        if dam:
            if dam not in nodes_dict:
                nodes_dict[dam] = {
                    'id': dam,
                    'label': f"母: {dam}",
                    'shape': 'ellipse',
                    'color': theme['dam'],
                    'size': 24,
                    'title': f"母系原名: {dam_raw}"
                }
            edge_key = (dam, child_raw)
            if edge_key not in added_edges:
                edges_list.append({
                    'from': dam,
                    'to': child_raw,
                    'color': '#e67e22',
                    'width': 1.5,
                    'title': f"母系: {dam_raw}"
                })
                added_edges.add(edge_key)

    # 封裝成標準圖形資料 JSON
    graph_data = {
        'nodes': list(nodes_dict.values()),
        'edges': edges_list
    }

    # 輸出成固定的 data.json 檔案
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 成功處理 {len(nodes_dict)} 個節點與 {len(edges_list)} 條關聯線，已輸出成 data.json！")

if __name__ == '__main__':
    generate_graph_data()
