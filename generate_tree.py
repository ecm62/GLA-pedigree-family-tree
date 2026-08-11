import json
import pandas as pd
import requests
import io

SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"
GID_TREE = "0"
URL_TREE = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID_TREE}"

def fetch_and_parse():
    print("🚀 開始讀取並解析 Google Sheet 數據...")
    try:
        res = requests.get(URL_TREE, headers={'User-Agent': 'Mozilla/5.0'})
        res.encoding = 'utf-8-sig'
        df = pd.read_csv(io.StringIO(res.text))
        df.columns = [str(c).replace('\n', '').replace('\r', '').strip() for c in df.columns]
        df = df.dropna(how='all')
    except Exception as e:
        print(f"❌ 下載 CSV 失敗: {e}")
        return

    def find_col(keywords):
        for kw in keywords:
            for col in df.columns:
                if kw.lower() in col.lower():
                    return col
        return None

    col_ear = find_col(['耳號', 'Ear Tag', 'EarTag', 'Ear', 'Tag']) or df.columns[2]
    col_sex = find_col(['Sex', '性別'])
    col_parity = find_col(['胎次', 'Parity'])
    col_mate = find_col(['當胎', '配種公', 'Sire', 'Mate'])
    col_breed = find_col(['Breed', '品種'])
    
    col_birth_date = find_col(['DOB', '出生日期', '生日', '個體生日'])
    col_farrow_date = find_col(['farrowing date', '分娩日期', '產房日期', 'dob'])
    
    col_spi = find_col(['SPI'])
    col_mli = find_col(['MLI'])
    col_tsi = find_col(['TSI'])
    col_total_born = find_col(['Total', '總生產', '總生'])
    col_born_alive = find_col(['Born', '活胎'])
    col_weaning = find_col(['Weaning', '離乳'])
    col_mother_wt = find_col(['mother total', '生育重'])
    col_weaning_wt = find_col(['均重', 'weight'])
    col_tnb = find_col(['TNB'])
    col_nba = find_col(['NBA'])
    col_lteat = find_col(['lteat', '左乳'])
    col_rteat = find_col(['rteat', '右乳'])

    col_sire_sire = find_col(['Sire美系父親名(祖父)', 'sire_sire', '祖父'])
    col_sire_dam  = find_col(['Dam Name美系母親名(祖母)', 'sire_dam', '祖母'])
    col_dam_sire  = find_col(['Sire美系父親名(外公)', 'dam_sire', '外公'])
    col_dam_dam   = find_col(['Dam Name美系母親名(外婆)', 'dam_dam', '外婆'])
    col_gen1_sire = find_col(['第一代公', '1st Sire', '父親'])
    col_gen1_dam  = find_col(['第一代母', '1st Dam', '母親'])

    birth_map = {}
    for _, row in df.iterrows():
        ear_val = str(row.get(col_ear, '')).strip().upper()
        if col_birth_date and pd.notna(row.get(col_birth_date)):
            dob_val = str(row.get(col_birth_date)).strip()
            if dob_val and dob_val.lower() not in ['nan', 'none', '-', '']:
                birth_map[ear_val] = dob_val

    pedigree_data = []
    for _, row in df.iterrows():
        ear = str(row.get(col_ear, '')).strip()
        if not ear or ear.lower() in ['nan', 'none', '-']: 
            continue
        
        breed = str(row.get(col_breed, 'D')).strip().upper() if col_breed else 'D'
        if 'LY' in ear.upper(): breed = 'LY'
        is_ly = breed == 'LY' or 'LY' in ear.upper()

        def get_v(c):
            if c and pd.notna(row.get(c)):
                val = str(row.get(c)).strip()
                return val if val.lower() not in ['nan', 'none', ''] else '-'
            return '-'

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": get_v(col_sex),
            "parity": get_v(col_parity),
            "mate": get_v(col_mate),
            "birth_date": birth_map.get(ear.upper(), '-') if not is_ly else '-',
            "dob": get_v(col_farrow_date),
            "spi": get_v(col_spi),
            "mli": get_v(col_mli),
            "tsi": get_v(col_tsi),
            "total_born": get_v(col_total_born),
            "born_alive": get_v(col_born_alive),
            "weaning": get_v(col_weaning),
            "mother_wt": get_v(col_mother_wt),
            "weaning_wt": get_v(col_weaning_wt),
            "tnb": get_v(col_tnb),
            "nba": get_v(col_nba),
            "lteat": get_v(col_lteat),
            "rteat": get_v(col_rteat),
            "sire_sire": get_v(col_sire_sire),
            "sire_dam": get_v(col_sire_dam),
            "dam_sire": get_v(col_dam_sire),
            "dam_dam": get_v(col_dam_dam),
            "gen1_sire": get_v(col_gen1_sire),
            "gen1_dam": get_v(col_gen1_dam),
            "details": {str(k).strip(): (str(v).strip() if pd.notna(v) else "") for k, v in row.items()}
        }

        for col in df.columns:
            if '配種日期' in str(col) or 'mating date' in str(col).lower():
                val = str(row.get(col, '')).replace('🔴', '').strip()
                if val and val.lower() not in ['nan', 'none', '', '-']:
                    entry[col] = val

        pedigree_data.append(entry)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)
    print(f"✅ 成功寫入 data.json，共 {len(pedigree_data)} 筆紀錄")

if __name__ == "__main__":
    fetch_and_parse()
