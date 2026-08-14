import json
import pandas as pd
import requests
import io
import re
from datetime import datetime, timedelta

SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"

def parse_date(val):
    if pd.isna(val) or str(val).strip() in ['', '-', 'nan', 'NaN', 'None', 'null']:
        return '-'
    val_str = str(val).replace('🔴', '').strip()
    try:
        num = float(val_str)
        if 10000 <= num <= 60000:
            base_date = datetime(1899, 12, 30)
            return (base_date + timedelta(days=num)).strftime('%Y-%m-%d')
    except ValueError:
        pass
    return val_str

def shorten_name(val):
    if not val or str(val).strip() in ['-', 'nan', 'NaN', 'None', '']:
        return '-'
    s = str(val).strip()
    parts = s.split(' ')
    keywords = [p for p in parts if not re.match(r'^\d+[\-\d]*$', p) and p.upper() not in ['1CR1', '1CR2', 'CR1', 'CR2']]
    if keywords:
        last = keywords[-1]
        if re.search(r'\d', last) and len(keywords) > 1:
            keywords.pop()
        return ' '.join(keywords)
    return s

def fetch_and_parse():
    print("🚀 啟動：直讀【育種_家族階層清單】與【美國原始種源數據】完整血統資料...")
    headers = {'User-Agent': 'Mozilla/5.0'}

    # 嘗試抓取所有可能的分頁 GID
    gids_to_try = [
        "1821811808", # 育種_家族階層清單 / GLA遺傳育種
        "803517616",  # 美國原始種源數據
        "0"           # 預設首頁
    ]

    all_dfs = []
    for gid in gids_to_try:
        url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
        try:
            res = requests.get(url, headers=headers, timeout=20)
            res.encoding = 'utf-8-sig'
            if res.status_code == 200:
                df = pd.read_csv(io.StringIO(res.text), low_memory=False)
                df.columns = [str(c).replace('\n', '').replace('\r', '').strip() for c in df.columns]
                all_dfs.append(df)
        except Exception as e:
            print(f"GID {gid} 載入失敗: {e}")

    # 合併所有讀取到的資料
    combined_df = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

    def get_col(row, names):
        for n in names:
            for c in row.index:
                if n.lower() in str(c).lower():
                    v = row[c]
                    if pd.notna(v) and str(v).strip().lower() not in ['', '-', 'nan', 'none', 'null']:
                        return str(v).strip()
        return '-'

    pedigree_data = []
    
    for _, row in combined_df.iterrows():
        ear = get_col(row, ['耳號', 'Nombor', 'Ear Tag'])
        if ear == '-' or not ear:
            continue

        ear = ear.upper()
        breed = get_col(row, ['Breed', '品種', '品種代號']).upper()
        if breed == '-':
            breed = 'D' if ear.startswith('D') else ('L' if ear.startswith('L') else ('Y' if ear.startswith('Y') else 'D'))
        if 'LY' in ear:
            breed = 'LY'

        # 核心：精確對應【育種_家族階層清單】與【美國原始種源數據】的欄位
        sire_name = shorten_name(get_col(row, ['1代/2代代公(父)', '1st Sire', 'Sire Name美系父親名', '父親名', '美系父親名']))
        dam_name  = shorten_name(get_col(row, ['1代/2代代母(母)', '1st Dam', 'Dam Name美系母親名', '母親名', '美系母親名']))
        
        sire_sire = shorten_name(get_col(row, ['2代代母祖父', 'Sire美系第0代父親名(祖父)', 'Sire美系父親名(祖父)', '祖父', 'Sire Sire']))
        sire_dam  = shorten_name(get_col(row, ['2代代母祖母', 'Dam Name美系第0代母親名(祖母)', 'Dam Name美系母親名(祖母)', '祖母', 'Sire Dam']))
        
        dam_sire  = shorten_name(get_col(row, ['2代代母外公', 'Sire 美系第0代父親名(外公)', 'MGS Name 美系MGS名', '外公', 'Dam Sire']))
        dam_dam   = shorten_name(get_col(row, ['2代代母外婆', 'Dam Name美系第0代母親名(外婆)', '外婆', 'Dam Dam']))

        # 如果是一般公豬個體，自動補齊雙親
        if sire_name == '-' and sire_sire != '-': sire_name = sire_sire
        if dam_name == '-' and dam_dam != '-': dam_name = dam_dam

        mating_date = parse_date(get_col(row, ['配種日期', 'Tarikh Kahwin', 'Mating Date']))
        farrow_date = parse_date(get_col(row, ['DOB出生日期', 'Tarikh Farrowing', '分娩日期', 'DOB']))
        birth_date  = parse_date(get_col(row, ['DOB', '出生日期', 'Birth Date']))
        
        if birth_date == '-' and farrow_date != '-':
            birth_date = farrow_date

        mate_boar = get_col(row, ['當胎配種公豬', '當胎配種公', 'Jantan', '配種公豬', 'Boar'])

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": get_col(row, ['Sex', '性別']),
            "parity": get_col(row, ['胎次', 'Parity']),
            "mate": mate_boar,
            "birth_date": birth_date,
            "mating_date": mating_date,
            "dob": farrow_date,
            "weaning_date": parse_date(get_col(row, ['Weaning day', '離乳日'])),
            "spi": get_col(row, ['SPI']),
            "mli": get_col(row, ['MLI']),
            "tsi": get_col(row, ['TSI']),
            "total_born": get_col(row, ['Total born', '總生產', '總產', 'TNB']),
            "born_alive": get_col(row, ['Born alive', '活胎', 'NBA']),
            "weaning": get_col(row, ['Weaning', '離乳']),
            "weaning_wt": get_col(row, ['weaning weight', '均重']),
            "mother_wt": get_col(row, ['Mother total Weight', '生育重']),
            "tnb": get_col(row, ['TNB']),
            "nba": get_col(row, ['NBA']),
            "lteat": get_col(row, ['Lteat', 'L-Teat']),
            "rteat": get_col(row, ['Rteat', 'R-Teat']),
            "gen1_sire": sire_name,
            "gen1_dam": dam_name,
            "sire_sire": sire_sire,
            "sire_dam": sire_dam,
            "dam_sire": dam_sire,
            "dam_dam": dam_dam,
            "details": {str(k): str(v) for k, v in row.items() if pd.notna(v)}
        }
        pedigree_data.append(entry)

    print(f"🎉 成功匯入 {len(pedigree_data)} 筆完整世代階層資料！")
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fetch_and_parse()
