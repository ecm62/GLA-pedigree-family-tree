import os
import re
import json
import pandas as pd
import numpy as np

def clean_name(name):
    if pd.isna(name) or not str(name).strip():
        return "-"
    name = str(name).strip()
    # 移除前綴代碼如 1CR1, 1CR2, CR2 等
    name = re.sub(r'^[0-9]*[A-Z]+[0-9]*\s+', '', name)
    # 移除耳缺號後綴如 1147-1, 1085-6, 514-1, 224-2 等
    name = re.sub(r'\s+[0-9]+-[0-9]+.*$', '', name)
    return name.strip()

def get_breed_code(tag, default="D"):
    if not tag or tag == "-":
        return default
    tag = str(tag).strip().upper()
    if tag.startswith("DD") or tag.startswith("D"):
        return "D"
    elif tag.startswith("YY") or tag.startswith("Y"):
        return "Y"
    elif tag.startswith("LL") or tag.startswith("L"):
        return "L"
    elif "LY" in tag:
        return "LY"
    return default

def load_data():
    # 1. 讀取美國原始種源數據
    us_df = pd.read_csv('2024_GLA_Genetic_遺傳整合_育種_遺傳_賣豬_美國原始種源數據.csv')
    
    # 2. 讀取育種家族階層清單
    family_df = pd.read_csv('2024_GLA_Genetic_遺傳整合_育種_遺傳_賣豬_育種_家族階層清單.csv')
    
    # 3. 建立 4 位數美系祖代快取
    ancestor_cache = {}
    for _, row in us_df.iterrows():
        tag = str(row.get('耳號', '')).strip()
        if not tag:
            continue
        ancestor_cache[tag] = {
            "sire": clean_name(row.get('Sire Name美系父親名', row.get('Sire Name美系父親-全名', '-'))),
            "dam": clean_name(row.get('Dam Name美系母親名', row.get('Dam Name美系母親-全名', '-'))),
            "mgs": clean_name(row.get('MGS Name 美系MGS名', '-')),
            "dob": str(row.get('DOB', '')).strip(),
            "breed": str(row.get('Breed', 'Duroc')).strip(),
            "sex": str(row.get('Sex', 'Gilt')).strip(),
            "spi": row.get('SPI', '-'),
            "mli": row.get('MLI', '-'),
            "tsi": row.get('TSI', '-'),
            "tnb": row.get('TNB', '-'),
            "nba": row.get('NBA', '-'),
            "lteat": row.get('Lteat', '-'),
            "rteat": row.get('Rteat', '-')
        }

    # 4. 組織個體資料結構
    database = {}

    # 先提取所有出現在家族階層清單中的個體
    grouped_family = family_df.groupby('耳號')
    
    for tag, group in grouped_family:
        tag = str(tag).strip()
        if not tag or tag == 'nan':
            continue

        base_info = ancestor_cache.get(tag, {})
        first_row = group.iloc[0]

        # 整理歷胎配種與分娩紀錄
        matings = []
        for idx, row in group.iterrows():
            m_sire = str(row.get('當胎配種公豬', '')).strip()
            if m_sire == 'nan' or not m_sire:
                continue
            
            p_sire_info = ancestor_cache.get(m_sire, {})
            matings.append({
                "parity": int(row.get('胎次(Parity)', 0)) if pd.notna(row.get('胎次(Parity)')) else idx,
                "mating_sire": m_sire,
                "mating_date": str(row.get('配種日期(Mating Date)', '-')),
                "farrow_date": str(row.get('DOB出生日期', '-')) if pd.notna(row.get('DOB出生日期')) else '-',
                "total_born": row.get('Total born同胎總生產數', '-'),
                "born_alive": row.get('Born alive同胎次活胎數量', '-'),
                "weaning": row.get('Weaning同胎次離乳數量', '-'),
                "mother_wt": row.get('Mother total Weight(母豬生育重量)', '-'),
                "wean_wt": row.get('weaning weight同胎次離乳平均重', '-'),
                "sire_sire": p_sire_info.get('sire', '-'),
                "sire_dam": p_sire_info.get('dam', '-')
            })

        # 決定祖先節點
        sire_name = base_info.get('sire', '-')
        dam_name = base_info.get('dam', '-')
        mgs_name = base_info.get('mgs', '-')

        # 向上提取祖父、祖母、外公、外婆
        s_sire = "-"
        s_dam = "-"
        d_sire = mgs_name
        d_dam = "ANNA" if dam_name == "ANNA" else "-"

        # 若父親也是 4 位數個體，直接解析父親的父母
        if sire_name in ancestor_cache:
            s_sire = ancestor_cache[sire_name].get('sire', '-')
            s_dam = ancestor_cache[sire_name].get('dam', '-')

        database[tag] = {
            "ear_tag": tag,
            "breed": base_info.get('breed', str(first_row.get('Breed', 'DUROC'))),
            "sex": base_info.get('sex', str(first_row.get('Sex', 'FEMALE'))),
            "dob": base_info.get('dob', str(first_row.get('DOB出生日期', '-'))),
            "spi": base_info.get('spi', first_row.get('SPI', '-')),
            "mli": base_info.get('mli', first_row.get('MLI', '-')),
            "tsi": base_info.get('tsi', first_row.get('TSI', '-')),
            "tnb": base_info.get('tnb', first_row.get('TNB', '-')),
            "nba": base_info.get('nba', first_row.get('NBA', '-')),
            "lteat": base_info.get('lteat', first_row.get('Lteat', '-')),
            "rteat": base_info.get('rteat', first_row.get('Rteat', '-')),
            "pedigree": {
                "sire": sire_name,
                "dam": dam_name,
                "sire_sire": s_sire,
                "sire_dam": s_dam,
                "dam_sire": d_sire,
                "dam_dam": d_dam
            },
            "matings": matings
        }

    # 寫入 data.json
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(database, f, ensure_ascii=False, indent=2)
    print("✅ data.json 產出完成，收錄豬隻筆數:", len(database))

if __name__ == '__main__':
    load_data()
