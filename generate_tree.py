import json
import pandas as pd
import requests
import io
import re

SPREADSHEET_ID = "1MlhcSXitL_jWYvXVfmo6bQfQqDPIDgUt0VGIZVaB5aw"
GID_MAIN = "0"                 # 📊 育種_家族階層清單
GID_US_ORIGIN = "1267648620"   # 🧬 美國原始種源數據
GID_COMBINED = "84920994"      # 📑 合併報表(配種+產房)

def fetch_sheet_csv(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
        res.encoding = 'utf-8-sig'
        if res.status_code == 200:
            return res.text
    except Exception as e:
        print(f"❌ 讀取 GID {gid} 失敗: {e}")
    return ""

def clean_str(val):
    if pd.isna(val) or val is None:
        return "-"
    s = str(val).replace('\n', ' ').replace('\r', '').strip()
    return s if s.lower() not in ['nan', 'none', '', 'null'] else "-"

def clean_name(val):
    s = clean_str(val)
    if s == "-":
        return "-"
    if re.match(r'^[\d\-]+$', s):
        return "-"
    parts = s.split(' ')
    valid_parts = [p for p in parts if not re.match(r'^[\d\-]+$', p) and p.upper() not in ['1CR1', '1CR2', 'CR1', 'CR2']]
    if valid_parts:
        if len(valid_parts) > 1 and re.search(r'\d', valid_parts[-1]):
            valid_parts.pop()
        return " ".join(valid_parts)
    return s

def fetch_and_parse():
    print("🚀 啟動全表關聯解析（包含自繁留種區間生日回填）...")

    # 1. 解析合併報表：建立留種耳號區間的生日、生父、生母對照池
    notch_ranges = []
    raw_comb = fetch_sheet_csv(GID_COMBINED)
    if raw_comb:
        try:
            df_comb = pd.read_csv(io.StringIO(raw_comb))
            clean_c = {c: str(c).strip().lower() for c in df_comb.columns}
            
            # 支援多種表頭命名：分娩日、Tarikh Beranak、Breeder Start/End
            col_farrow = next((o for o, c in clean_c.items() if '分娩日' in c or 'beranak' in c or 'farrow' in c), None)
            col_dam = next((o for o, c in clean_c.items() if '母豬耳號' in c or 'nombor telinga' in c or 'induk' in c), None)
            col_sire = next((o for o, c in clean_c.items() if '配種公豬' in c or 'jantan' in c or 'boar' in c), None)
            col_start = next((o for o, c in clean_c.items() if 'breeder' in c and 'start' in c), None)
            col_end = next((o for o, c in clean_c.items() if 'breeder' in c and 'end' in c), None)

            if col_farrow and col_start and col_end:
                for _, r in df_comb.iterrows():
                    s_tag = clean_str(r.get(col_start))
                    e_tag = clean_str(r.get(col_end))
                    f_date = clean_str(r.get(col_farrow)).replace('/', '-')
                    sire_e = clean_str(r.get(col_sire)).upper()
                    dam_e = clean_str(r.get(col_dam)).upper()

                    if s_tag != '-' and e_tag != '-' and f_date != '-':
                        nums_s = re.findall(r'\d+', s_tag)
                        nums_e = re.findall(r'\d+', e_tag)
                        prefix_s = re.findall(r'^[A-Za-z]+', s_tag)
                        pre = prefix_s[0].upper() if prefix_s else ""

                        if nums_s and nums_e:
                            n_start = int(nums_s[0])
                            n_end = int(nums_e[0])
                            dig_len = len(nums_s[0])
                            start_i = min(n_start, n_end)
                            end_i = max(n_start, n_end)

                            notch_ranges.append({
                                "prefix": pre,
                                "start": start_i,
                                "end": end_i,
                                "dig_len": dig_len,
                                "dob": f_date,
                                "sire": sire_e,
                                "dam": dam_e
                            })
            print(f"📊 已成功建立 {len(notch_ranges)} 個留種區間生日池")
        except Exception as e:
            print("⚠️ 合併報表解析異常:", e)

    # 2. 讀取美國原始種源數據
    us_data_map = {}
    raw_us = fetch_sheet_csv(GID_US_ORIGIN)
    if raw_us:
        try:
            df_us = pd.read_csv(io.StringIO(raw_us))
            col_ear_us = next((c for c in df_us.columns if '耳號' in str(c)), None)
            col_sire_us = next((c for c in df_us.columns if 'Sire Name' in str(c) or '美系父親名' in str(c)), None)
            col_dam_us = next((c for c in df_us.columns if 'Dam Name' in str(c) or '美系母親名' in str(c)), None)
            col_sex_us = next((c for c in df_us.columns if 'Sex' in str(c) or '性別' in str(c)), None)
            col_dob_us = next((c for c in df_us.columns if 'DOB' in str(c) or '出生' in str(c)), None)

            for _, r in df_us.iterrows():
                e = clean_str(r.get(col_ear_us, '')).upper()
                if e != '-':
                    us_data_map[e] = {
                        "sire": clean_name(r.get(col_sire_us, '-')),
                        "dam": clean_name(r.get(col_dam_us, '-')),
                        "sex": clean_str(r.get(col_sex_us, '-')),
                        "dob": clean_str(r.get(col_dob_us, '-')).replace('/', '-')
                    }
        except Exception as e:
            print("⚠️ 美國數據表解析異常:", e)

    # 3. 讀取主表
    raw_main = fetch_sheet_csv(GID_MAIN)
    if not raw_main:
        print("❌ 主表下載失敗！")
        return

    df_main = pd.read_csv(io.StringIO(raw_main))
    df_main.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df_main.columns]

    def find_col(keywords):
        for kw in keywords:
            for c in df_main.columns:
                if kw.lower() in c.lower():
                    return c
        return None

    c_ear = find_col(['耳號']) or df_main.columns[5]
    c_sex = find_col(['Sex', '性別']) or df_main.columns[4]
    c_parity = find_col(['胎次', 'Parity']) or df_main.columns[6]
    c_mate = find_col(['當胎配種公', '配種公']) or df_main.columns[7]
    c_mating_d = find_col(['配種日期']) or df_main.columns[8]
    c_farrow_d = find_col(['當胎分娩日', '分娩日']) or df_main.columns[9]
    c_dob = find_col(['DOB出生日期', 'DOB']) or df_main.columns[10]
    c_dod = find_col(['DOD/淘汰日期', 'DOD', '淘汰日期']) or df_main.columns[11]
    c_breed = find_col(['Breed', '品種']) or df_main.columns[14]

    # 全場耳號生產母豬確認名冊
    confirmed_sows = set()
    for _, row in df_main.iterrows():
        e = clean_str(row.get(c_ear, '')).upper()
        p = clean_str(row.get(c_parity, ''))
        fd = clean_str(row.get(c_farrow_d, ''))
        sx = clean_str(row.get(c_sex, '')).upper()
        if e != '-':
            if p != '-' or fd != '-' or 'FEMALE' in sx or 'GILT' in sx or '母' in sx or e.startswith('LY'):
                confirmed_sows.add(e)

    for e, udata in us_data_map.items():
        if 'GILT' in udata['sex'].upper() or 'FEMALE' in udata['sex'].upper() or e.startswith('LY'):
            confirmed_sows.add(e)

    pedigree_data = []
    death_map = {}
    existing_ears = set()

    for _, row in df_main.iterrows():
        ear = clean_str(row.get(c_ear, ''))
        if ear == '-' or ear == '耳號':
            continue
        ear_upper = ear.upper()
        existing_ears.add(ear_upper)

        # 淘汰/死亡
        dod_val = clean_str(row.get(c_dod, ''))
        is_dead = False
        if dod_val != '-':
            is_dead = True
            death_map[ear_upper] = dod_val

        # 性別：LY 雜交豬與經產豬強制為 FEMALE
        if ear_upper in confirmed_sows or ear_upper.startswith('LY'):
            sex = "FEMALE"
        else:
            raw_s = clean_str(row.get(c_sex, '')).upper()
            sex = "MALE" if ("MALE" in raw_s or "公" in raw_s) else "FEMALE"

        # 品種
        raw_b = clean_str(row.get(c_breed, '')).upper()
        breed = "D"
        if "YORK" in raw_b or ear_upper.startswith("Y"):
            breed = "Y"
        elif "LAND" in raw_b or ear_upper.startswith("L"):
            breed = "L"
        elif "DUROC" in raw_b or ear_upper.startswith("D"):
            breed = "D"
        if "LY" in ear_upper:
            breed = "LY"

        # 🌟 核心修復：出生日期 (DOB) 回填邏輯
        dob_val = clean_str(row.get(c_dob, ''))
        g1_sire = clean_str(row.get(find_col(['第一代公']), '-'))
        g1_dam  = clean_str(row.get(find_col(['第一代母']), '-'))

        # 若主表該欄位為空，優先至合併報表區間比對
        if dob_val == '-' or dob_val == '':
            ear_nums = re.findall(r'\d+', ear_upper)
            ear_prefix = re.findall(r'^[A-Za-z]+', ear_upper)
            if ear_nums and ear_prefix:
                num_val = int(ear_nums[0])
                pre_val = ear_prefix[0]
                for nr in notch_ranges:
                    if nr['prefix'] == pre_val and (nr['start'] <= num_val <= nr['end']):
                        dob_val = nr['dob']
                        if g1_sire == '-' and nr['sire'] != '-': g1_sire = nr['sire']
                        if g1_dam == '-' and nr['dam'] != '-':  g1_dam = nr['dam']
                        break

        # 若依然為空，查美國原始數據
        if (dob_val == '-' or dob_val == '') and ear_upper in us_data_map:
            dob_val = us_data_map[ear_upper]['dob']

        # 祖輩品系名
        us_sire = "-"
        us_dam = "-"
        for c in df_main.columns:
            if '父親名' in c:
                val = clean_name(row.get(c))
                if val != '-': us_sire = val
            if '母親名' in c:
                val = clean_name(row.get(c))
                if val != '-': us_dam = val

        if (us_sire == '-' or us_dam == '-') and ear_upper in us_data_map:
            if us_sire == '-': us_sire = us_data_map[ear_upper]['sire']
            if us_dam == '-': us_dam = us_data_map[ear_upper]['dam']

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": sex,
            "parity": clean_str(row.get(c_parity, '-')),
            "mate": clean_str(row.get(c_mate, '-')),
            "birth_date": dob_val,
            "mating_date": clean_str(row.get(c_mating_d, '-')),
            "dob": clean_str(row.get(c_farrow_d, '-')),
            "is_dead": is_dead,
            "dod": dod_val,
            "spi": clean_str(row.get(find_col(['SPI']), '-')),
            "mli": clean_str(row.get(find_col(['MLI']), '-')),
            "tsi": clean_str(row.get(find_col(['TSI']), '-')),
            "total_born": clean_str(row.get(find_col(['Total born', '總生產']), '-')),
            "born_alive": clean_str(row.get(find_col(['Born alive', '活胎']), '-')),
            "weaning": clean_str(row.get(find_col(['Weaning', '離乳']), '-')),
            "mother_wt": clean_str(row.get(find_col(['生育重']), '-')),
            "wean_wt": clean_str(row.get(find_col(['均重']), '-')),
            "tnb": clean_str(row.get(find_col(['TNB']), '-')),
            "nba": clean_str(row.get(find_col(['NBA']), '-')),
            "lteat": clean_str(row.get(find_col(['左乳']), '-')),
            "rteat": clean_str(row.get(find_col(['右乳']), '-')),
            "gen1_sire": g1_sire,
            "gen1_dam": g1_dam,
            "sire_sire": us_sire,
            "sire_dam": us_dam,
            "dam_sire": us_sire,
            "dam_dam": us_dam,
            "details": {str(k).strip(): clean_str(v) for k, v in row.items()}
        }
        pedigree_data.append(entry)

    # 4. 補充尚未生產的純後備留種豬
    for nr in notch_ranges:
        if (nr['end'] - nr['start']) <= 50 and nr['end'] >= nr['start']:
            for cur_n in range(nr['start'], nr['end'] + 1):
                young_ear = f"{nr['prefix']}{str(cur_n).zfill(nr['dig_len'])}"
                if young_ear not in existing_ears:
                    existing_ears.add(young_ear)
                    b_code = 'D'
                    if 'LY' in nr['prefix']: b_code = 'LY'
                    elif 'Y' in nr['prefix']: b_code = 'Y'
                    elif 'L' in nr['prefix']: b_code = 'L'

                    pedigree_data.append({
                        "ear": young_ear,
                        "breed": b_code,
                        "sex": "FEMALE",
                        "parity": "-",
                        "mate": "-",
                        "birth_date": nr['dob'],
                        "mating_date": "-",
                        "dob": "-",
                        "is_dead": False,
                        "dod": "-",
                        "spi": "-", "mli": "-", "tsi": "-",
                        "total_born": "-", "born_alive": "-", "weaning": "-",
                        "mother_wt": "-", "wean_wt": "-",
                        "tnb": "-", "nba": "-", "lteat": "-", "rteat": "-",
                        "gen1_sire": nr['sire'],
                        "gen1_dam": nr['dam'],
                        "sire_sire": "-", "sire_dam": "-", "dam_sire": "-", "dam_dam": "-",
                        "details": {"耳號": young_ear, "第一代公": nr['sire'], "第一代母": nr['dam'], "出生日期": nr['dob']}
                    })

    output = {
        "pedigree": pedigree_data,
        "death_map": death_map
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 解析完成！總計個體: {len(pedigree_data)}")
    if "LY10906" in [p['ear'] for p in pedigree_data]:
        p_item = next(p for p in pedigree_data if p['ear'] == 'LY10906')
        print(f"🎯 驗證 LY10906 -> 生日: {p_item['birth_date']}, 性別: {p_item['sex']}, 生母: {p_item['gen1_dam']}, 生父: {p_item['gen1_sire']}")

if __name__ == "__main__":
    fetch_and_parse()
