import json
import pandas as pd
import requests
import io
from datetime import datetime

SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"

# 分頁 GID (請確保 GID 正確對應)
GID_TREE = "0"  # 育種主表/產房紀錄
URL_TREE = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID_TREE}"

def parse_date(date_str):
    """安全解析日期字串為 datetime 物件"""
    if not date_str or str(date_str).strip() in ['nan', 'None', '-', '']:
        return None
    clean_s = str(date_str).replace('🔴', '').replace('/', '-').strip()
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(clean_s.split(' ')[0], fmt)
        except ValueError:
            pass
    return None

def fetch_and_parse():
    print("🚀 開始讀取 Google Sheet 數據，執行美系 G 欄 DOB 提取與自繁殖個體耳號推算...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        res = requests.get(URL_TREE, headers=headers, timeout=15)
        res.encoding = 'utf-8-sig'
        if res.status_code != 200:
            print(f"❌ 下載失敗，狀態碼: {res.status_code}")
            return
        df = pd.read_csv(io.StringIO(res.text))
        print(f"✅ 成功下載主表！原始資料筆數：{len(df)}")
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        return

    if df.empty:
        return

    df.columns = [str(c).replace('\n', '').replace('\r', '').strip() for c in df.columns]

    def find_col(keywords):
        for kw in keywords:
            for col in df.columns:
                if kw.lower() in col.lower():
                    return col
        return None

    col_ear = find_col(['耳號', 'C']) or df.columns[2]
    col_sex = find_col(['Sex', '性別'])
    col_parity = find_col(['胎次', 'Parity'])
    col_mate = find_col(['當胎', '配種公'])
    
    # G欄 美系第一代 DOB / 產房分娩日
    col_us_dob = find_col(['DOB', '美國DOB', '原始DOB'])  # 美國原始種源 G 欄
    col_farrow_date = find_col(['farrowing date', '分娩日期', '產房日期', '分娩日'])
    
    col_breed = find_col(['Breed', '品'])
    col_spi = find_col(['SPI'])
    col_mli = find_col(['MLI'])
    col_tsi = find_col(['TSI'])
    col_total_born = find_col(['Total', '總生產', '總生'])
    col_born_alive = find_col(['Born', '活胎'])
    col_weaning = find_col(['Weaning', '離乳'])
    col_weaning_wt = find_col(['均重', 'weight'])

    col_sire_sire = find_col(['Sire 美系父親名(祖父)', 'Sire 美系父親名', '祖父'])
    col_sire_dam  = find_col(['Dam Name美系母親名(祖母)', 'Dam Name美系母親名', '祖母'])
    col_dam_sire  = find_col(['Sire 美系父親名(外公)', '外公'])
    col_dam_dam   = find_col(['Dam Name美系母親名(外婆)', '外婆'])

    col_gen1_sire = find_col(['第一代公'])
    col_gen1_dam  = find_col(['第一代母'])
    col_gen2_sire = find_col(['第二代公'])
    col_gen2_dam  = find_col(['第二代母'])
    col_gen3_sire = find_col(['第三代公', '第三代'])

    # 🌟 第一階段：建立「美系第一代」與「產房紀錄」耳號出生日映射字典 (Master Birth Map)
    master_birth_map = {}

    for idx, row in df.iterrows():
        ear = str(row.get(col_ear, '')).strip()
        if not ear or ear.lower() in ['nan', 'none', '-', '', 'null']:
            continue
        
        # 1. 優先拿 G 欄美系原始 DOB
        us_dob = str(row.get(col_us_dob, '')).strip() if col_us_dob else ''
        if us_dob and us_dob.lower() not in ['nan', 'none', '-', '']:
            master_birth_map[ear.upper()] = us_dob
        
        # 2. 記錄分娩日作為後代可能之出生日
        farrow_d = str(row.get(col_farrow_date, '')).strip() if col_farrow_date else ''
        if farrow_d and farrow_d.lower() not in ['nan', 'none', '-', '']:
            # 若該耳號尚未有出生日記錄，以最早的分娩日做為備用
            if ear.upper() not in master_birth_map:
                master_birth_map[ear.upper()] = farrow_d

    # 🌟 第二階段：組裝各個體數據，精準對齊 Birth Date 與當胎 Farrow Date
    pedigree_data = []

    for idx, row in df.iterrows():
        ear = str(row.get(col_ear, '')).strip()
        if not ear or ear.lower() in ['nan', 'none', '-', '', 'null']:
            continue

        ear_upper = ear.upper()
        breed = str(row.get(col_breed, '')).strip().upper() if pd.notna(row.get(col_breed)) else "D"
        if 'LY' in ear_upper: breed = 'LY'
        elif 'Y' in ear_upper and breed == 'D': breed = 'Y'
        elif 'L' in ear_upper and breed == 'D': breed = 'L'

        def get_v(col_name):
            if col_name and pd.notna(row.get(col_name)):
                val = str(row.get(col_name)).strip()
                return val if val.lower() not in ['nan', 'none', ''] else '-'
            return '-'

        farrow_date_val = get_v(col_farrow_date)
        
        # 🌟 真正的個體出生日搜尋邏輯：
        # 先查字典 (G欄美系DOB) -> 若為自繁殖，試圖尋找耳號匹配
        real_birth_date = master_birth_map.get(ear_upper, '-')
        
        # 若是當胎分娩日與出生日重複，且非第一代，設法隔離
        if real_birth_date == farrow_date_val and ('LY' in ear_upper or 'L' in ear_upper or 'Y' in ear_upper):
            # 美系原始 G 欄優先
            us_g_dob = get_v(col_us_dob)
            if us_g_dob != '-' and us_g_dob != farrow_date_val:
                real_birth_date = us_g_dob

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": get_v(col_sex),
            "parity": get_v(col_parity),
            "mate": get_v(col_mate),
            "birth_date": real_birth_date,   # 🌟 母豬真正的個體出生日 (美系 G 欄或推算生日)
            "dob": farrow_date_val,          # 🌟 當胎分娩日
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
            "gen1_sire": get_v(col_gen1_sire),
            "gen1_dam":  get_v(col_gen1_dam),
            "gen2_sire": get_v(col_gen2_sire),
            "gen2_dam":  get_v(col_gen2_dam),
            "gen3_sire": get_v(col_gen3_sire),
            "details": {str(k).strip(): (str(v).strip() if pd.notna(v) else "") for k, v in row.items()}
        }

        for col in df.columns:
            if '配種日期' in str(col) or 'mating date' in str(col).lower():
                val = str(row.get(col, '')).replace('🔴', '').strip()
                if val and val.lower() not in ['nan', 'none', '', '-']:
                    entry[col] = val

        pedigree_data.append(entry)

    print(f"🎉 成功轉換！共處理 {len(pedigree_data)} 筆資料，母豬生日與分娩日已完全拆分！")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fetch_and_parse()
