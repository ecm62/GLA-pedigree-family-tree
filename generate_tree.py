import json
import pandas as pd
import requests
import io
import re

SPREADSHEET_ID = "1MlhcSXitL_jWYvXVfmo6bQfQqDPIDgUt0VGIZVaB5aw"

# 🌟 鎖定最新出處 GID
GID_MAIN = "836462358"         # 📊 育種_家族階層清單 (含最新 G3_父代/母代 全名與指標)
GID_US_ORIGIN = "1297296053"   # 🧬 美國原始種源數據
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

def clean_metric_num(val):
    s = clean_str(val)
    if s == "-": return "-"
    # 確保抓到的是合法數值，排除文字錯位
    m = re.search(r'^\d+(\.\d+)?$', s)
    return m.group(0) if m else "-"

def fetch_and_parse():
    print("🚀 正在抓取最新官方四代親譜與全名指標資料庫...")

    # 1. 讀取美國原種庫 (GID: 1297296053)
    us_data_map = {}
    raw_us = fetch_sheet_csv(GID_US_ORIGIN)
    if raw_us:
        try:
            df_us = pd.read_csv(io.StringIO(raw_us))
            df_us.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df_us.columns]
            col_ear_us = next((c for c in df_us.columns if '耳號' in c), None)
            col_sire_us = next((c for c in df_us.columns if 'Sire Name' in c or '美系父親名' in c), None)
            col_dam_us = next((c for c in df_us.columns if 'Dam Name' in c or '美系母親名' in c), None)
            col_sex_us = next((c for c in df_us.columns if 'Sex' in c or '性別' in c), None)
            col_dob_us = next((c for c in df_us.columns if 'DOB' in c or '出生' in c), None)

            for _, r in df_us.iterrows():
                e = clean_str(r.get(col_ear_us, '')).upper()
                if e != '-':
                    us_data_map[e] = {
                        "sire": clean_str(r.get(col_sire_us, '-')),
                        "dam": clean_str(r.get(col_dam_us, '-')),
                        "sex": clean_str(r.get(col_sex_us, '-')),
                        "dob": clean_str(r.get(col_dob_us, '-')).replace('/', '-')
                    }
        except Exception as e:
            print("⚠️ 美國數據表解析異常:", e)

    # 2. 讀取主表「育種_家族階層清單」 (GID: 836462358)
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

    # 🌟 最新標準親代全名與指標欄位 (支援截圖最新表頭)
    c_g3_sire_name = find_col(['G3_父代Sire全名', 'G3_父代全名', 'Sire美系第0代父親(祖父)-全名', 'Sire美系第0代父親(外公)-全名', 'Sire Name美系父親名'])
    c_g3_sire_spi  = find_col(['G3_父代SPI', 'Sire_SPI'])
    c_g3_sire_mli  = find_col(['G3_父代MLI', 'Sire_MLI'])

    c_g3_dam_name  = find_col(['G3_母代Dam全名', 'G3_母代全名', 'Dam 美系第0代母親(祖母)-全名', 'Dam 美系第0代母親(外婆)-全名', 'Dam Name美系母親名'])
    c_g3_dam_spi   = find_col(['G3_母代SPI', 'Dam_SPI'])
    c_g3_dam_mli   = find_col(['G3_母代MLI', 'Dam_MLI'])

    # 祖輩 (Grandparents) 全名欄位
    c_ss_name = find_col(['Sire美系第0代父親(祖父)-全名', 'Sire 美系第0代父親(祖父)-全名', 'Sire美系第0代父親名(祖父)'])
    c_sd_name = find_col(['Dam 美系第0代母親(祖母)-全名', 'Dam Name美系第0代母親名(祖母)'])
    c_ds_name = find_col(['Sire 美系第0代父親(外公)-全名', 'Sire美系第0代父親(外公)-全名', 'Sire美系第0代父親名(外公)'])
    c_dd_name = find_col(['Dam 美系第0代母親(外婆)-全名', 'Dam Name美系第0代母親名(外婆)'])

    # 自繁親代欄位 (支援五位數自繁種豬)
    c_gen1_sire = find_col(['G6/G7公(父)', 'G5/G6公(父)', 'G4/G5公(父)', '第一代公', '1st Sire'])
    c_gen1_dam  = find_col(['G6/G7母(母)', 'G5/G6母(母)', 'G4/G5母(母)', '第一代母', '1st Dam'])

    pedigree_data = []
    death_map = {}

    for _, row in df_main.iterrows():
        ear = clean_str(row.get(c_ear, ''))
        if ear == '-' or ear == '耳號':
            continue
        ear_upper = ear.upper()

        dod_val = clean_str(row.get(c_dod, ''))
        is_dead = False
        if dod_val != '-':
            is_dead = True
            death_map[ear_upper] = dod_val

        p_val = clean_str(row.get(c_parity, '-'))
        fd_val = clean_str(row.get(c_farrow_d, '-'))

        # 性別判定
        raw_s = clean_str(row.get(c_sex, '')).upper()
        if 'FEMALE' in raw_s or 'GILT' in raw_s or '母' in raw_s or ear_upper.startswith('LY') or p_val != '-' or fd_val != '-':
            sex = "FEMALE"
        else:
            sex = "MALE"

        raw_b = clean_str(row.get(c_breed, '')).upper()
        breed = "D"
        if "YORK" in raw_b or ear_upper.startswith("Y"): breed = "Y"
        elif "LAND" in raw_b or ear_upper.startswith("L"): breed = "L"
        elif "DUROC" in raw_b or ear_upper.startswith("D"): breed = "D"
        if "LY" in ear_upper: breed = "LY"

        dob_val = clean_str(row.get(c_dob, ''))
        if (dob_val == '-' or dob_val == '') and ear_upper in us_data_map:
            dob_val = us_data_map[ear_upper]['dob']

        # 🌟 最新標準親本全名與育種值讀取
        parent_sire_full = clean_str(row.get(c_g3_sire_name, '-'))
        parent_sire_spi  = clean_metric_num(row.get(c_g3_sire_spi, '-'))
        parent_sire_mli  = clean_metric_num(row.get(c_g3_sire_mli, '-'))

        parent_dam_full  = clean_str(row.get(c_g3_dam_name, '-'))
        parent_dam_spi   = clean_metric_num(row.get(c_g3_dam_spi, '-'))
        parent_dam_mli   = clean_metric_num(row.get(c_g3_dam_mli, '-'))

        # 祖輩全名
        ss_full = clean_str(row.get(c_ss_name, '-'))
        sd_full = clean_str(row.get(c_sd_name, '-'))
        ds_full = clean_str(row.get(c_ds_name, '-'))
        dd_full = clean_str(row.get(c_dd_name, '-'))

        # 容錯回溯美國原種庫
        if parent_sire_full == '-' and ear_upper in us_data_map:
            parent_sire_full = us_data_map[ear_upper]['sire']
        if parent_dam_full == '-' and ear_upper in us_data_map:
            parent_dam_full = us_data_map[ear_upper]['dam']

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": sex,
            "parity": p_val,
            "mate": clean_str(row.get(c_mate, '-')),
            "birth_date": dob_val,
            "mating_date": clean_str(row.get(c_mating_d, '-')),
            "dob": fd_val,
            "is_dead": is_dead,
            "dod": dod_val,
            "spi": clean_metric_num(row.get(find_col(['SPI']), '-')),
            "mli": clean_metric_num(row.get(find_col(['MLI']), '-')),
            "tsi": clean_metric_num(row.get(find_col(['TSI']), '-')),
            "total_born": clean_str(row.get(find_col(['Total born', '總生產']), '-')),
            "born_alive": clean_str(row.get(find_col(['Born alive', '活胎']), '-')),
            "weaning": clean_str(row.get(find_col(['Weaning', '離乳']), '-')),
            "mother_wt": clean_str(row.get(find_col(['生育重']), '-')),
            "wean_wt": clean_str(row.get(find_col(['均重']), '-')),
            "tnb": clean_metric_num(row.get(find_col(['TNB']), '-')),
            "nba": clean_metric_num(row.get(find_col(['NBA']), '-')),
            "lteat": clean_str(row.get(find_col(['左乳']), '-')),
            "rteat": clean_str(row.get(find_col(['右乳']), '-')),
            # 自繁生父生母
            "gen1_sire": clean_str(row.get(c_gen1_sire, '-')),
            "gen1_dam": clean_str(row.get(c_gen1_dam, '-')),
            # 🌟 官方四代造冊標準欄位
            "g3_sire_full": parent_sire_full,
            "g3_sire_spi": parent_sire_spi,
            "g3_sire_mli": parent_sire_mli,
            "g3_dam_full": parent_dam_full,
            "g3_dam_spi": parent_dam_spi,
            "g3_dam_mli": parent_dam_mli,
            # 祖輩全名
            "ss_full": ss_full,
            "sd_full": sd_full,
            "ds_full": ds_full,
            "dd_full": dd_full,
            "details": {str(k).strip(): clean_str(v) for k, v in row.items()}
        }
        pedigree_data.append(entry)

    output = {
        "pedigree": pedigree_data,
        "death_map": death_map
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"🎉 成功生成 data.json！收錄 {len(pedigree_data)} 頭個體，官方四代親譜全名與指標已全部鎖定。")

if __name__ == "__main__":
    fetch_and_parse()
