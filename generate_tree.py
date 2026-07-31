import json
import pandas as pd
import requests
import io

SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"
GID_TREE = "0"
URL_TREE = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID_TREE}"

def fetch_and_parse():
    print("🚀 開始從 Google Sheet 下載完整交錯數據...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        res = requests.get(URL_TREE, headers=headers, timeout=15)
        res.encoding = 'utf-8-sig'
        if res.status_code != 200:
            print(f"❌ 下載失敗: {res.status_code}")
            return
        df = pd.read_csv(io.StringIO(res.text))
        print(f"✅ 成功下載！原始資料總筆數：{len(df)}")
    except Exception as e:
        print(f"❌ 下載錯誤: {e}")
        return

    if df.empty:
        return

    # 清理欄位名稱空格
    df.columns = [str(c).replace('\n', '').replace('\r', '').strip() for c in df.columns]

    def find_col(keywords):
        for kw in keywords:
            for col in df.columns:
                if kw.lower() in col.lower():
                    return col
        return None

    col_ear = find_col(['耳號', 'C']) or df.columns[2]
    col_sex = find_col(['Sex', '性別', 'B'])
    col_parity = find_col(['胎次', 'Parity', 'D'])
    col_mate = find_col(['當胎', '配種公', 'E'])
    col_dob = find_col(['DOB', '生日', 'F'])
    col_breed = find_col(['Breed', '品', 'H'])
    
    # 指數與成績欄位
    col_spi = find_col(['SPI'])
    col_mli = find_col(['MLI'])
    col_tsi = find_col(['TSI'])
    col_total_born = find_col(['Total', '總生產', 'I'])
    col_born_alive = find_col(['Born', '活胎', 'J'])
    col_weaning = find_col(['Weaning', '離乳', 'K'])
    col_weaning_wt = find_col(['weight', '均重', 'L'])

    # 祖輩欄位
    col_sire_sire = find_col(['祖父', 'Sire 美系'])
    col_sire_dam  = find_col(['祖母', 'Dam Name美系'])
    col_dam_sire  = find_col(['外公', 'Sire 美系父親名(外'])
    col_dam_dam   = find_col(['外婆', 'Dam Name美系母親名(外'])

    # 世代欄位
    col_gen1 = find_col(['第一代公'])
    col_gen2 = find_col(['第二代公'])

    pedigree_data = []

    for idx, row in df.iterrows():
        ear = str(row.get(col_ear, '')).strip() if pd.notna(row.get(col_ear)) else ""
        if not ear or ear.lower() in ['nan', 'none', '-', '', 'null']:
            continue

        breed = str(row.get(col_breed, '')).strip().upper() if pd.notna(row.get(col_breed)) else "D"
        if 'LY' in ear.upper(): breed = 'LY'
        elif 'Y' in ear.upper() and breed == 'D': breed = 'Y'
        elif 'L' in ear.upper() and breed == 'D': breed = 'L'

        def get_v(col_name):
            if col_name and pd.notna(row.get(col_name)):
                val = str(row.get(col_name)).strip()
                return val if val.lower() not in ['nan', 'none', ''] else '-'
            return '-'

        # 封裝完整詳細數據字典
        raw_details = {}
        for col_k, col_v in row.items():
            if pd.notna(col_v):
                raw_details[str(col_k).strip()] = str(col_v).strip()

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": get_v(col_sex),
            "parity": get_v(col_parity),
            "mate": get_v(col_mate),
            "dob": get_v(col_dob),
            "spi": get_v(col_spi),
            "mli": get_v(col_mli),
            "tsi": get_v(col_tsi),
            "total_born": get_v(col_total_born),
            "born_alive": get_v(col_born_alive),
            "weaning": get_v(col_weaning),
            "weaning_wt": get_v(col_weaning_wt),
            "sire_sire": get_v(col_sire_sire),
            "sire_dam": get_v(col_sire_dam),
            "dam_sire": get_v(col_dam_sire),
            "dam_dam": get_v(col_dam_dam),
            "gen1_sire": get_v(col_gen1),
            "gen2_sire": get_v(col_gen2),
            "details": raw_details
        }
        pedigree_data.append(entry)

    print(f"🎉 成功轉換！共抓取 {len(pedigree_data)} 筆包含全套 SPI/MLI/TSI 與交錯血系之數據！")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fetch_and_parse()
