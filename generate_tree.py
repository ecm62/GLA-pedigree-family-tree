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
    if not name_str or name_str in ['-', 'nan', 'None', '']:
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
    print("🚀 啟動智能數字去殼比對與全血統深度雙向關聯算碼...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    target_gids = {
        "us_source": "803517616",      
        "gla_breeding": "1821811808",  
        "main_prod": "0"               
    }
    
    dfs = {}
    for key, gid in target_gids.items():
        url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
        try:
            res = requests.get(url, headers=headers, timeout=12)
            res.encoding = 'utf-8-sig'
            if res.status_code == 200:
                temp_df = pd.read_csv(io.StringIO(res.text))
                temp_df.columns = [str(c).replace('\n', '').replace('\r', '').strip() for c in temp_df.columns]
                dfs[key] = temp_df.dropna(how='all')
        except Exception as e:
            dfs[key] = pd.DataFrame()

    # 1. 建立美系種源庫 (加上純數字 mapping 解決 D1401 vs 1401 找不到的問題)
    us_identity_db = {}
    us_df = dfs.get("us_source", pd.DataFrame())
    if not us_df.empty:
        for _, row in us_df.iterrows():
            ear_val = ""
            for c in us_df.columns:
                if '耳號' in c or 'Ear Tag' in c or 'Nombor' in c:
                    v = str(row.get(c, '')).strip().upper()
                    if v and v != 'NAN':
                        ear_val = v
                        break
            if not ear_val:
                for col_idx in [2, 6, 7]:
                    if len(us_df.columns) > col_idx:
                        val = str(row.iloc[col_idx]).strip().upper()
                        if val.isdigit() and len(val) == 4:
                            ear_val = val
                            break

            if ear_val:
                dob_g = parse_date_value(row.get('DOB', row.get('出生日期', '-')))
                sire_w = shorten_name(row.get('Sire Name美系父親-全名', row.get('Sire Name美系父親名', row.get('1st Sire', '-'))))
                dam_ab = shorten_name(row.get('Dam Name美系母親-全名', row.get('Dam Name美系母親名', row.get('1st Dam', '-'))))
                sire_sire = shorten_name(row.get('Sire美系父親名(祖父)', row.get('sire_sire', '-')))
                sire_dam  = shorten_name(row.get('Dam Name美系母親名(祖母)', row.get('sire_dam', '-')))
                dam_sire  = shorten_name(row.get('MGS Name 美系MGS名', row.get('dam_sire', '-')))
                dam_dam   = shorten_name(row.get('dam_dam', '-'))

                info_dict = {
                    'birth_date': dob_g, 'sire': sire_w, 'dam': dam_ab,
                    'sire_sire': sire_sire, 'sire_dam': sire_dam,
                    'dam_sire': dam_sire, 'dam_dam': dam_dam
                }
                us_identity_db[ear_val] = info_dict
                
                # 【核心修復】同時將純數字也加入索引！
                num_key = extract_number(ear_val)
                if num_key:
                    us_identity_db[num_key] = info_dict

    # 2. 合併生產歷程
    gla_df = dfs.get("gla_breeding", pd.DataFrame())
    main_df = dfs.get("main_prod", pd.DataFrame())
    prod_df_list = [d for d in [gla_df, main_df] if not d.empty]
    prod_df = pd.concat(prod_df_list, ignore_index=True).drop_duplicates() if prod_df_list else pd.DataFrame()

    def get_exact_col(df_target, exact_keywords):
        for kw in exact_keywords:
            for col in df_target.columns:
                if col.strip().lower() == kw.lower(): return col
        for kw in exact_keywords:
            for col in df_target.columns:
                if kw.lower() in col.lower(): return col
        return None

    col_ear = get_exact_col(prod_df, ['Nombor Telinga 母豬耳號 Number', '母豬耳號', '耳號', 'Ear Tag']) or prod_df.columns[2]
    col_sex = get_exact_col(prod_df, ['Sex', '性別'])
    col_parity = get_exact_col(prod_df, ['Parity', '胎次'])
    col_mate = get_exact_col(prod_df, ['Jantan 配種公豬 Boar', '配種公豬', '當胎配種公', 'Boar'])
    col_breed = get_exact_col(prod_df, ['Breed', '品種', '品種代號'])
    col_mating_date = get_exact_col(prod_df, ['Tarikh Kahwin 配種日期 Date(YMD)', 'Mating Date', '配種日期'])
    col_farrow_date = get_exact_col(prod_df, ['Tarikh Farrowing date / Tarikh beranak (m/d)', 'Farrowing date', '分娩日期'])
    col_wean_date   = get_exact_col(prod_df, ['Weaning day / Hari cerai susu(m/d)', 'Weaning day', '離乳日'])
    
    col_spi = get_exact_col(prod_df, ['SPI'])
    col_mli = get_exact_col(prod_df, ['MLI'])
    col_tsi = get_exact_col(prod_df, ['TSI'])
    col_total_born = get_exact_col(prod_df, ['Total born 同胎總生產數', '總生產'])
    col_born_alive = get_exact_col(prod_df, ['Born alive 同胎次活胎數量', '活胎'])
    col_weaning = get_exact_col(prod_df, ['Weaning 同胎次離乳數量', '離乳'])
    col_weaning_wt = get_exact_col(prod_df, ['weaning weight 同胎次離乳平均重', '均重'])

    col_notch_start = get_exact_col(prod_df, ['Ear Notch Breeder (start)', 'Notch Breeder (start)'])
    col_notch_end   = get_exact_col(prod_df, ['Ear Notch Breeder (end)', 'Notch Breeder (end)'])

    litter_range_db = []
    for _, row in prod_df.iterrows():
        farrow_c = parse_date_value(row.get(col_farrow_date, ''))
        dam_ear = str(row.get(col_ear, '')).strip().upper() if pd.notna(row.get(col_ear)) else ''
        mate_sire = str(row.get(col_mate, '')).strip() if pd.notna(row.get(col_mate)) else '-'

        if col_notch_start and col_notch_end:
            start_num = extract_number(row.get(col_notch_start, ''))
            end_num   = extract_number(row.get(col_notch_end, ''))
            if start_num is not None and end_num is not None and farrow_c != '-':
                litter_range_db.append({
                    'start': min(start_num, end_num),
                    'end': max(start_num, end_num),
                    'birth_date': farrow_c,
                    'dam': dam_ear,
                    'sire': mate_sire
                })

    temp_list = []
    ear_unique_birth_map = {}

    for idx, row in prod_df.iterrows():
        ear = str(row.get(col_ear, '')).strip() if pd.notna(row.get(col_ear)) else ""
        if not ear or ear.lower() in ['nan', 'none', '-', '', 'null']: continue

        ear_num = extract_number(ear)
        ear_upper = ear.upper()
        breed = str(row.get(col_breed, '')).strip().upper() if pd.notna(row.get(col_breed)) else "D"
        if 'LY' in ear_upper: breed = 'LY'

        def get_v(col_name):
            if col_name and pd.notna(row.get(col_name)):
                val = str(row.get(col_name)).strip()
                return val if val.lower() not in ['nan', 'none', ''] else '-'
            return '-'

        def get_date_v(col_name):
            if col_name and pd.notna(row.get(col_name)): return parse_date_value(row.get(col_name))
            return '-'

        ind_birth_date = '-'
        ind_sire = '-'
        ind_dam = '-'
        s_sire = '-'
        s_dam = '-'
        d_sire = '-'
        d_dam = '-'

        # 【核心修復】同時比對字串與純數字
        info = us_identity_db.get(ear_upper) or us_identity_db.get(ear_num)
        
        if info:
            ind_birth_date = info['birth_date']
            ind_sire       = info['sire']
            ind_dam        = info['dam']
            s_sire         = info['sire_sire']
            s_dam          = info['sire_dam']
            d_sire         = info['dam_sire']
            d_dam          = info['dam_dam']

        elif ear_num is not None and len(str(ear_num)) == 5:
            for litter in litter_range_db:
                if litter['start'] <= ear_num <= litter['end']:
                    ind_birth_date = litter['birth_date']
                    ind_dam        = litter['dam']
                    ind_sire       = litter['sire']
                    
                    s_info = us_identity_db.get(ind_sire.upper()) or us_identity_db.get(extract_number(ind_sire))
                    if s_info:
                        s_sire = s_info['sire']
                        s_dam  = s_info['dam']
                        
                    d_info = us_identity_db.get(ind_dam.upper()) or us_identity_db.get(extract_number(ind_dam))
                    if d_info:
                        d_sire = d_info['sire']
                        d_dam  = d_info['dam']
                    break

        if ind_birth_date != '-' and ear_upper not in ear_unique_birth_map:
            ear_unique_birth_map[ear_upper] = ind_birth_date

        if ind_sire.upper() == ear_upper: ind_sire = '-'
        if ind_dam.upper() == ear_upper: ind_dam = '-'

        temp_list.append({
            "ear": ear,
            "breed": breed,
            "sex": get_v(col_sex),
            "parity": get_v(col_parity),
            "mate": get_v(col_mate),
            "raw_birth_date": ind_birth_date,
            "mating_date": get_date_v(col_mating_date),
            "dob": get_date_v(col_farrow_date),
            "weaning_date": get_date_v(col_wean_date),
            "spi": get_v(col_spi),
            "mli": get_v(col_mli),
            "tsi": get_v(col_tsi),
            "total_born": get_v(col_total_born),
            "born_alive": get_v(col_born_alive),
            "weaning": get_v(col_weaning),
            "weaning_wt": get_v(col_weaning_wt),
            "gen1_sire": shorten_name(ind_sire),
            "gen1_dam": shorten_name(ind_dam),
            "sire_sire": shorten_name(s_sire),
            "sire_dam": shorten_name(s_dam),
            "dam_sire": shorten_name(d_sire),
            "dam_dam": shorten_name(d_dam),
            "details": {str(k).strip(): (parse_date_value(v) if '日期' in str(k) or 'date' in str(k).lower() else str(v).strip()) for k, v in row.items() if pd.notna(v)}
        })

    # 強制塞入所有美系公豬 (確保 D1401 即使沒配種也能找到獨立祖先檔案)
    existing_ears = set(str(x['ear']).strip().upper() for x in temp_list)
    for k, info in us_identity_db.items():
        if isinstance(k, int): continue
        if k.upper() not in existing_ears:
            temp_list.append({
                "ear": k.upper(), "breed": "D", "sex": "MALE", "parity": "-", "mate": "-",
                "raw_birth_date": info['birth_date'], "mating_date": "-", "dob": "-", "weaning_date": "-",
                "spi": "-", "mli": "-", "tsi": "-", "total_born": "-", "born_alive": "-", "weaning": "-", "weaning_wt": "-",
                "gen1_sire": shorten_name(info['sire']), "gen1_dam": shorten_name(info['dam']),
                "sire_sire": shorten_name(info['sire_sire']), "sire_dam": shorten_name(info['sire_dam']),
                "dam_sire": shorten_name(info['dam_sire']), "dam_dam": shorten_name(info['dam_dam']),
                "details": {}
            })

    pedigree_data = []
    for item in temp_list:
        ear_u = item["ear"].upper()
        final_bdate = ear_unique_birth_map.get(ear_u, item["raw_birth_date"])
        item["birth_date"] = final_bdate
        del item["raw_birth_date"]
        pedigree_data.append(item)

    print(f"🎉 唯一生日與血統鎖定完成！總計處理 {len(pedigree_data)} 筆紀錄。")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fetch_and_parse()
