import json
import pandas as pd
import requests
import io
import re
from datetime import datetime, timedelta

SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"

def parse_date_value(val):
    if pd.isna(val) or str(val).strip() in ['', '-', 'nan', 'NaN', 'None', 'null']:
        return '-'
    val_str = str(val).replace('🔴', '').strip()
    try:
        num = float(val_str)
        if 10000 <= num <= 60000:
            base_date = datetime(1899, 12, 30)
            dt = base_date + timedelta(days=num)
            return dt.strftime('%Y-%m-%d')
    except ValueError:
        pass
    return val_str

def extract_number(ear_str):
    nums = re.findall(r'\d+', str(ear_str))
    if nums:
        return int(nums[0])
    return None

def shorten_name(name_str):
    if not name_str or str(name_str).strip() in ['-', 'nan', 'NaN', 'None', '']:
        return '-'
    s = str(name_str).strip()
    parts = s.split(' ')
    keywords = [p for p in parts if not re.match(r'^\d+[\-\d]*$', p) and p.upper() not in ['1CR1', '1CR2', 'CR1', 'CR2']]
    if keywords:
        last = keywords[-1]
        if re.search(r'\d', last) and len(keywords) > 1:
            keywords.pop()
        return ' '.join(keywords)
    return s

def fetch_and_parse():
    print("🚀 啟動：全種源美系公豬庫與生產履歷雙向血統穿透聚合...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    target_gids = {
        "us_source": "803517616",      # 美國原始種源數據 (含公豬父母祖代)
        "gla_breeding": "1821811808",  # GLA 遺傳育種資訊
        "main_prod": "0"               # 配種與分娩表
    }
    
    dfs = {}
    for key, gid in target_gids.items():
        url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
        try:
            res = requests.get(url, headers=headers, timeout=15)
            res.encoding = 'utf-8-sig'
            if res.status_code == 200:
                temp_df = pd.read_csv(io.StringIO(res.text))
                temp_df.columns = [str(c).replace('\n', '').replace('\r', '').strip() for c in temp_df.columns]
                dfs[key] = temp_df.dropna(how='all')
        except Exception as e:
            print(f"⚠️ 分頁 {key} 讀取失敗: {e}")
            dfs[key] = pd.DataFrame()

    def get_val_fuzzy(row, candidate_keys):
        """強效模糊比對：只要欄位名稱包含關鍵字就抓取"""
        for ck in candidate_keys:
            ck_clean = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', ck.lower())
            for col in row.index:
                col_clean = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', str(col).lower())
                if ck_clean in col_clean:
                    v = row[col]
                    if pd.notna(v) and str(v).strip().lower() not in ['', '-', 'nan', 'none', 'null']:
                        return str(v).strip()
        return '-'

    # ==========================================
    # 1. 建立完整的美系種源字典（不論公母，全數建檔）
    # ==========================================
    us_identity_db = {}
    us_df = dfs.get("us_source", pd.DataFrame())
    
    if not us_df.empty:
        for _, row in us_df.iterrows():
            ear_val = get_val_fuzzy(row, ['耳號', 'Ear Tag', 'Nombor', 'Ear'])
            if ear_val == '-':
                for col_idx in [2, 6, 7]:
                    if len(us_df.columns) > col_idx:
                        val = str(row.iloc[col_idx]).strip().upper()
                        if val.isdigit() and len(val) == 4:
                            ear_val = val
                            break

            if ear_val != '-':
                ear_upper = ear_val.upper()
                dob_g = parse_date_value(get_val_fuzzy(row, ['DOB', '出生日期', 'Birth Date']))
                
                sire_w    = shorten_name(get_val_fuzzy(row, ['Sire Name美系父親-全名', 'Sire Name美系父親名', '1st Sire', '父親']))
                dam_ab    = shorten_name(get_val_fuzzy(row, ['Dam Name美系母親-全名', 'Dam Name美系母親名', '1st Dam', '母親']))
                sire_sire = shorten_name(get_val_fuzzy(row, ['Sire美系父親名(祖父)', 'sire_sire', '祖父']))
                sire_dam  = shorten_name(get_val_fuzzy(row, ['Dam Name美系母親名(祖母)', 'sire_dam', '祖母']))
                dam_sire  = shorten_name(get_val_fuzzy(row, ['MGS Name 美系MGS名', 'dam_sire', '外公', 'MGS']))
                dam_dam   = shorten_name(get_val_fuzzy(row, ['dam_dam', '外婆']))

                info = {
                    'ear': ear_upper,
                    'birth_date': dob_g,
                    'sire': sire_w,
                    'dam': dam_ab,
                    'sire_sire': sire_sire,
                    'sire_dam': sire_dam,
                    'dam_sire': dam_sire,
                    'dam_dam': dam_dam,
                    'details': {str(k).strip(): str(v).strip() for k, v in row.items() if pd.notna(v)}
                }
                
                # 建立多重索引 (D1401, 1401, 1401純數字)
                us_identity_db[ear_upper] = info
                num = extract_number(ear_upper)
                if num:
                    us_identity_db[str(num)] = info
                    us_identity_db[f"D{num}"] = info
                    us_identity_db[f"L{num}"] = info
                    us_identity_db[f"Y{num}"] = info

    # ==========================================
    # 2. 處理生產歷程與五位數自產豬
    # ==========================================
    gla_df = dfs.get("gla_breeding", pd.DataFrame())
    main_df = dfs.get("main_prod", pd.DataFrame())
    prod_df = pd.concat([d for d in [gla_df, main_df] if not d.empty], ignore_index=True).drop_duplicates() if (not gla_df.empty or not main_df.empty) else pd.DataFrame()

    litter_range_db = []
    if not prod_df.empty:
        for _, row in prod_df.iterrows():
            farrow_c = parse_date_value(get_val_fuzzy(row, ['Tarikh Farrowing', 'Farrowing date', '分娩日期']))
            dam_ear = get_val_fuzzy(row, ['Nombor Telinga', '母豬耳號', '耳號', 'Ear Tag']).upper()
            mate_sire = get_val_fuzzy(row, ['Jantan', '配種公豬', '當胎配種公', 'Boar'])
            notch_start = get_val_fuzzy(row, ['Notch Breeder (start)', 'Ear Notch Breeder (start)'])
            notch_end   = get_val_fuzzy(row, ['Notch Breeder (end)', 'Ear Notch Breeder (end)'])

            s_num = extract_number(notch_start)
            e_num = extract_number(notch_end)
            if s_num is not None and e_num is not None and farrow_c != '-':
                litter_range_db.append({
                    'start': min(s_num, e_num),
                    'end': max(s_num, e_num),
                    'birth_date': farrow_c,
                    'dam': dam_ear,
                    'sire': mate_sire
                })

    pedigree_data = []
    processed_ears = set()

    # 先將生產表個體組裝入庫
    if not prod_df.empty:
        for _, row in prod_df.iterrows():
            ear = get_val_fuzzy(row, ['Nombor Telinga', '母豬耳號', '耳號', 'Ear Tag'])
            if ear == '-' or not ear: continue
            
            ear_upper = ear.upper()
            ear_num = extract_number(ear)
            breed = get_val_fuzzy(row, ['Breed', '品種', '品種代號']).upper()
            if breed == '-': breed = 'D' if ear_upper.startswith('D') else ('L' if ear_upper.startswith('L') else ('Y' if ear_upper.startswith('Y') else 'D'))
            if 'LY' in ear_upper: breed = 'LY'

            ind_bdate = '-'
            ind_sire = '-'
            ind_dam = '-'
            s_sire = '-'
            s_dam = '-'
            d_sire = '-'
            d_dam = '-'

            # 命中美系種源庫
            info = us_identity_db.get(ear_upper) or us_identity_db.get(str(ear_num) if ear_num else '')
            if info:
                ind_bdate = info['birth_date']
                ind_sire  = info['sire']
                ind_dam   = info['dam']
                s_sire    = info['sire_sire']
                s_dam     = info['sire_dam']
                d_sire    = info['dam_sire']
                d_dam     = info['dam_dam']
            elif ear_num is not None and len(str(ear_num)) == 5:
                # 命中五位數自產豬
                for litter in litter_range_db:
                    if litter['start'] <= ear_num <= litter['end']:
                        ind_bdate = litter['birth_date']
                        ind_dam   = litter['dam']
                        ind_sire  = litter['sire']
                        
                        s_info = us_identity_db.get(ind_sire.upper()) or us_identity_db.get(str(extract_number(ind_sire)))
                        if s_info:
                            s_sire = s_info['sire']
                            s_dam  = s_info['dam']
                        d_info = us_identity_db.get(ind_dam.upper()) or us_identity_db.get(str(extract_number(ind_dam)))
                        if d_info:
                            d_sire = d_info['sire']
                            d_dam  = d_info['dam']
                        break

            entry = {
                "ear": ear_upper,
                "breed": breed,
                "sex": get_val_fuzzy(row, ['Sex', '性別']),
                "parity": get_val_fuzzy(row, ['Parity', '胎次']),
                "mate": get_val_fuzzy(row, ['Jantan', '配種公豬', '當胎配種公', 'Boar']),
                "birth_date": ind_bdate,
                "mating_date": parse_date_value(get_val_fuzzy(row, ['Tarikh Kahwin', 'Mating Date', '配種日期'])),
                "dob": parse_date_value(get_val_fuzzy(row, ['Tarikh Farrowing', 'Farrowing date', '分娩日期'])),
                "weaning_date": parse_date_value(get_val_fuzzy(row, ['Weaning day', '離乳日'])),
                "spi": get_val_fuzzy(row, ['SPI']),
                "mli": get_val_fuzzy(row, ['MLI']),
                "tsi": get_val_fuzzy(row, ['TSI']),
                "total_born": get_val_fuzzy(row, ['Total born', '總生產']),
                "born_alive": get_val_fuzzy(row, ['Born alive', '活胎']),
                "weaning": get_val_fuzzy(row, ['Weaning', '離乳']),
                "weaning_wt": get_val_fuzzy(row, ['weaning weight', '均重']),
                "gen1_sire": ind_sire,
                "gen1_dam": ind_dam,
                "sire_sire": s_sire,
                "sire_dam": s_dam,
                "dam_sire": d_sire,
                "dam_dam": d_dam,
                "details": {str(k).strip(): str(v).strip() for k, v in row.items() if pd.notna(v)}
            }
            pedigree_data.append(entry)
            processed_ears.add(ear_upper)

    # ==========================================
    # 3. 【核心關鍵】把所有美系種源公豬強制寫入個體清單！
    # ==========================================
    for ear_key, info in us_identity_db.items():
        if ear_key in processed_ears or re.match(r'^\d+$', ear_key):
            continue
        
        # 建立完整的獨立公豬個體
        b_class = "D"
        if ear_key.startswith("L"): b_class = "L"
        elif ear_key.startswith("Y"): b_class = "Y"

        pedigree_data.append({
            "ear": ear_key,
            "breed": b_class,
            "sex": "MALE",
            "parity": "-",
            "mate": "-",
            "birth_date": info['birth_date'],
            "mating_date": "-",
            "dob": "-",
            "weaning_date": "-",
            "spi": "-",
            "mli": "-",
            "tsi": "-",
            "total_born": "-",
            "born_alive": "-",
            "weaning": "-",
            "weaning_wt": "-",
            "gen1_sire": info['sire'],
            "gen1_dam": info['dam'],
            "sire_sire": info['sire_sire'],
            "sire_dam": info['sire_dam'],
            "dam_sire": info['dam_sire'],
            "dam_dam": info['dam_dam'],
            "details": info.get('details', {})
        })
        processed_ears.add(ear_key)

    print(f"🎉 聚合完成！共導出 {len(pedigree_data)} 筆完整系譜個體。")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fetch_and_parse()
