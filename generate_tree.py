import io
import json
import re
from datetime import datetime
import pandas as pd
import requests

# 🌟 新資料來源：《💻🐷🪰整合2(育種端)》
SPREADSHEET_ID = "1CwvYVhvKpSKTbuyA0pEYHXHTnORSpNKQAVFmNEpkHyE"

# 🌟 精確定位《💻🐷🪰整合2(育種端)》分頁 GID
GID_HIERARCHY = "538252601"   # 📊 育種_家族階層清單(轉)
GID_US_ORIGIN = "624453592"   # 美國原始種源數據(轉)
GID_CARCASS   = "1828266796"  # 肉豬與屠宰回溯
GID_DEATH     = "1502904612"  # 種豬死亡與淘汰整併(自動)(轉)
GID_BLOOD     = "982285822"   # 📊 育種_血統比例(轉)
GID_SOW_EVAL  = "1267383696"  # 母豬育種與系譜
GID_BOAR_EVAL = "686220243"   # 公豬育種與採精


def fetch_sheet_csv(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=60)
        res.encoding = 'utf-8-sig'
        if res.status_code == 200:
            return res.text
        print(f"❌ 抓取 GID {gid} 失敗: HTTP {res.status_code}")
    except Exception as e:
        print(f"❌ 連線 GID {gid} 異常: {e}")
    return ""


def clean_val(val):
    if pd.isna(val) or val is None:
        return "-"
    s = str(val).replace('\n', ' ').replace('\r', '').strip()
    return s if s.lower() not in ['nan', 'none', '', 'null', 'undefined'] else "-"


def clean_num(val):
    s = clean_val(val)
    if s == "-":
        return "-"
    if re.match(r'^-?\d+\.0$', s):
        return s[:-2]
    m = re.search(r'^-?\d+(\.\d+)?$', s)
    return m.group(0) if m else "-"


def normalize_ear(val, default_breed=""):
    s = clean_val(val).upper()
    if s == "-":
        return "-"
    if s.endswith(".0"):
        s = s[:-2]
    if s.isdigit() and len(s) <= 4 and default_breed:
        b = default_breed.upper()
        prefix = 'D' if b.startswith('D') else ('L' if b.startswith('L') else ('Y' if b.startswith('Y') else ''))
        if prefix:
            return f"{prefix}{s}"
    return s


def find_col(kws, df, exact_first=True):
    if df is None or df.empty:
        return None
    if exact_first:
        for kw in kws:
            for c in df.columns:
                if c.strip().lower() == kw.strip().lower():
                    return c
    for kw in kws:
        for c in df.columns:
            if kw.lower() in c.lower():
                return c
    return None


def is_positive_flag(val):
    s = clean_val(val).upper()
    return s not in ['-', '0', '0.0', 'FALSE', 'NO', 'N', '正常']


def main():
    print("🚀 [1/6] 抓取《種豬死亡與淘汰整併(自動)(轉)》...")
    raw_death = fetch_sheet_csv(GID_DEATH)
    df_death = pd.read_csv(io.StringIO(raw_death), low_memory=False) if raw_death else pd.DataFrame()
    df_death.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df_death.columns]

    death_map = {}
    if not df_death.empty:
        c_d_ear = find_col(['EarTag', '耳號'], df_death)
        c_d_date = find_col(['Date', '日期'], df_death)
        c_d_stat = find_col(['Status', '狀態'], df_death)
        for _, r in df_death.iterrows():
            ear = normalize_ear(r.get(c_d_ear))
            if ear == "-":
                continue
            dt = clean_val(r.get(c_d_date))
            st = clean_val(r.get(c_d_stat))
            death_map[ear] = dt if dt != "-" else (st if st != "-" else "DEAD/CULLED")
    print(f"   ✓ 載入 {len(death_map)} 筆死淘紀錄。")

    print("🚀 [2/6] 抓取《母豬育種與系譜》與《公豬育種與採精》補充近交F與等級...")
    eval_meta = {}
    for gid, ear_kws in [(GID_SOW_EVAL, ['Ear No.', '耳號']), (GID_BOAR_EVAL, ['Boar Ear', '耳號'])]:
        raw_ev = fetch_sheet_csv(gid)
        df_ev = pd.read_csv(io.StringIO(raw_ev), low_memory=False) if raw_ev else pd.DataFrame()
        df_ev.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df_ev.columns]
        if not df_ev.empty:
            c_e = find_col(ear_kws, df_ev)
            c_b = find_col(['Breed', '品種'], df_ev)
            c_f = find_col(['Inbreeding F', '近交F', '近交係數'], df_ev)
            c_g = find_col(['Grade', '等級'], df_ev)
            for _, r in df_ev.iterrows():
                b_str = clean_val(r.get(c_b))
                ear = normalize_ear(r.get(c_e), b_str)
                if ear == "-":
                    continue
                f_val = clean_num(r.get(c_f))
                g_val = clean_val(r.get(c_g))
                if ear not in eval_meta:
                    eval_meta[ear] = {"f": f_val, "grade": g_val}
                else:
                    if eval_meta[ear]["f"] == "-" and f_val != "-":
                        eval_meta[ear]["f"] = f_val
                    if eval_meta[ear]["grade"] == "-" and g_val != "-":
                        eval_meta[ear]["grade"] = g_val
    print(f"   ✓ 載入 {len(eval_meta)} 頭個體近交F與等級索引。")

    print("🚀 [3/6] 抓取《美國原始種源數據(轉)》...")
    raw_us = fetch_sheet_csv(GID_US_ORIGIN)
    df_us = pd.read_csv(io.StringIO(raw_us), low_memory=False) if raw_us else pd.DataFrame()
    df_us.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df_us.columns]

    us_dict = {}
    if not df_us.empty:
        for _, r in df_us.iterrows():
            pen = r.get(find_col(['手寫卡號', 'Pen No'], df_us))
            breed = clean_val(r.get(find_col(['品種', 'Breed'], df_us)))
            if pen is None or pd.isna(pen) or breed == "-":
                continue
            try:
                pen_num = int(float(pen))
            except Exception:
                continue

            prefix = 'D' if 'duroc' in breed.lower() else ('L' if 'land' in breed.lower() else ('Y' if 'york' in breed.lower() else ''))
            ear_tag = f"{prefix}{pen_num}"
            sex_raw = clean_val(r.get(find_col(['性別', 'Sex'], df_us)))
            sex = "MALE" if ('boar' in sex_raw.lower() or '公' in sex_raw or 'male' in sex_raw.lower()) else "FEMALE"

            us_dict[ear_tag] = {
                "ear": ear_tag,
                "breed": breed.upper(),
                "sex": sex,
                "full_name": clean_val(r.get(find_col(['G4_本代全名', '全名'], df_us))),
                "family_line": clean_val(r.get(find_col(['【G4_本代】品系家族名', '品系家族名'], df_us))),
                "spi": clean_num(r.get(find_col(['G4_SPI', 'SPI'], df_us))),
                "mli": clean_num(r.get(find_col(['G4_MLI', 'MLI'], df_us))),
                "tsi": clean_num(r.get(find_col(['G4_TSI', 'TSI'], df_us))),
                "sire_full": clean_val(r.get(find_col(['G3_父代Sire全名', 'G3_美系父親Sire'], df_us))),
                "sire_line": clean_val(r.get(find_col(['【G3_父代Sire】品系家族名', 'G3_父品系家族名'], df_us))),
                "sire_spi": clean_num(r.get(find_col(['G3_父代SPI', 'G3_父SPI'], df_us))),
                "sire_mli": clean_num(r.get(find_col(['G3_父代MLI', 'G3_父MLI'], df_us))),
                "dam_full": clean_val(r.get(find_col(['G3_母代Dam全名', 'G3_美系母親Dam'], df_us))),
                "dam_line": clean_val(r.get(find_col(['【G3_母代Dam】品系家族名', 'G3_母品系家族名'], df_us))),
                "dam_spi": clean_num(r.get(find_col(['G3_母代SPI', 'G3_母SPI'], df_us))),
                "dam_mli": clean_num(r.get(find_col(['G3_母代MLI', 'G3_母MLI'], df_us))),
                "ss_full": clean_val(r.get(find_col(['G2_祖父SS全名', 'G2_祖父SS(全名)'], df_us))),
                "ss_line": clean_val(r.get(find_col(['【G2_祖父SS】品系家族名', 'G2_祖父SS(品系名)'], df_us))),
                "sd_full": clean_val(r.get(find_col(['G2_祖母SD全名', 'G2_祖母SD(全名)'], df_us))),
                "sd_line": clean_val(r.get(find_col(['【G2_祖母SD】品系家族名', 'G2_祖母SD(品系名)'], df_us))),
                "ds_full": clean_val(r.get(find_col(['G2_外祖父DS全名', 'G2_外祖父DS(全名)'], df_us))),
                "ds_line": clean_val(r.get(find_col(['【G2_外祖父DS】品系家族名', 'G2_外祖父DS(品系名)'], df_us))),
                "dd_full": clean_val(r.get(find_col(['G2_外祖母DD全名', 'G2_外祖母DD(全名)'], df_us))),
                "dd_line": clean_val(r.get(find_col(['【G2_外祖母DD】品系家族名', 'G2_外祖母DD(品系名)'], df_us))),
                "g1_nodes": {
                    "sss": clean_val(r.get(find_col(['【G1_曾祖父SSS】品系家族名', 'G1_曾祖父SSS(品系名)'], df_us))),
                    "ssd": clean_val(r.get(find_col(['【G1_曾祖母SSD】品系家族名', 'G1_曾祖母SSD(品系名)'], df_us))),
                    "sds": clean_val(r.get(find_col(['【G1_曾祖父SDS】品系家族名', 'G1_曾祖父SDS(品系名)'], df_us))),
                    "sdd": clean_val(r.get(find_col(['【G1_曾祖母SDD】品系家族名', 'G1_曾祖母SDD(品系名)'], df_us))),
                    "dss": clean_val(r.get(find_col(['【G1_曾外祖父DSS】品系家族名', 'G1_曾外祖父DSS(品系名)'], df_us))),
                    "dsd": clean_val(r.get(find_col(['【G1_曾外祖母DSD】品系家族名', 'G1_曾外祖母DSD(品系名)'], df_us))),
                    "dds": clean_val(r.get(find_col(['【G1_曾外祖父DDS】品系家族名', 'G1_曾外祖父DDS(品系名)'], df_us))),
                    "ddd": clean_val(r.get(find_col(['【G1_曾外祖母DDD】品系家族名', 'G1_曾外祖母DDD(品系名)'], df_us)))
                }
            }
    print(f"   ✓ 載入 {len(us_dict)} 頭美系原種檔案。")

    print("🚀 [4/6] 抓取《📊 育種_家族階層清單(轉)》...")
    raw_hier = fetch_sheet_csv(GID_HIERARCHY)
    df_hier = pd.read_csv(io.StringIO(raw_hier), low_memory=False) if raw_hier else pd.DataFrame()
    df_hier.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df_hier.columns]

    c_ear   = find_col(['耳號'], df_hier) or '耳號'
    c_sex   = find_col(['Sex', '性別'], df_hier) or 'Sex'
    c_p     = find_col(['胎次(Parity)', '胎次', 'Parity'], df_hier) or '胎次'
    c_mate  = find_col(['當胎配種公豬', '配種公'], df_hier) or '當胎配種公豬'
    c_md    = find_col(['配種日期'], df_hier) or '配種日期'
    c_fd    = find_col(['當胎分娩日', '分娩日'], df_hier) or '當胎分娩日'
    c_dob   = find_col(['DOB出生日期', 'DOB'], df_hier) or 'DOB'
    c_dod   = find_col(['DOD/淘汰日期', '淘汰日期', 'DOD'], df_hier) or 'DOD/淘汰日期'
    c_breed = find_col(['Breed', '品種'], df_hier) or 'Breed'
    c_age   = find_col(['目前年齡(歲)', '目前年齡'], df_hier) or '目前年齡(歲)'
    c_used  = find_col(['已使用年限(年)', '已使用年限'], df_hier) or '已使用年限(年)'
    c_g5_s  = find_col(['G5_直屬父(Sire)', 'G5_直屬父'], df_hier) or 'G5_直屬父(Sire)'
    c_g5_d  = find_col(['G5_直屬母(Dam)', 'G5_直屬母'], df_hier) or 'G5_直屬母(Dam)'

    pedigree_list = []
    known_ears = set()

    for _, r in df_hier.iterrows():
        breed_raw = clean_val(r.get(c_breed)).upper()
        ear_upper = normalize_ear(r.get(c_ear), breed_raw)
        if ear_upper == "-" or ear_upper == "耳號":
            continue
        known_ears.add(ear_upper)

        dod = clean_val(r.get(c_dod))
        if dod != "-":
            death_map[ear_upper] = dod
        elif ear_upper in death_map:
            dod = death_map[ear_upper]

        breed = breed_raw
        if breed == "-":
            breed = "LY" if ear_upper.startswith("LY") else (
                "Y" if ear_upper.startswith("Y") else (
                "L" if ear_upper.startswith("L") else (
                "D" if ear_upper.startswith("D") else "UNKNOWN")))
        else:
            if "YORK" in breed: breed = "Y"
            elif "LAND" in breed: breed = "L"
            elif "DUROC" in breed: breed = "D"
            elif "LY" in breed or "YL" in breed: breed = "LY"

        sire_full = clean_val(r.get(find_col(['G3_美系父親Sire(全名)', 'G3_父代Sire全名'], df_hier)))
        sire_line = clean_val(r.get(find_col(['G3_父品系家族名', '【G3_父代Sire】品系家族名'], df_hier)))
        dam_full  = clean_val(r.get(find_col(['G3_美系母親Dam(全名)', 'G3_母代Dam全名'], df_hier)))
        dam_line  = clean_val(r.get(find_col(['G3_母品系家族名', '【G3_母代Dam】品系家族名'], df_hier)))

        us_meta = us_dict.get(ear_upper, {})
        if sire_full == "-" and us_meta:
            sire_full = us_meta.get("sire_full", "-")
            sire_line = us_meta.get("sire_line", "-")
        if dam_full == "-" and us_meta:
            dam_full = us_meta.get("dam_full", "-")
            dam_line = us_meta.get("dam_line", "-")

        sex_raw = clean_val(r.get(c_sex)).upper()
        is_female = (sex_raw in ["FEMALE", "F", "母", "SOW", "GILT"]) or ear_upper.startswith("LY")
        ev = eval_meta.get(ear_upper, {"f": "-", "grade": "-"})

        entry = {
            "ear": ear_upper,
            "breed": breed,
            "sex": "FEMALE" if is_female else "MALE",
            "parity": clean_num(r.get(c_p)),
            "mate": normalize_ear(r.get(c_mate)),
            "mating_date": clean_val(r.get(c_md)),
            "farrow_date": clean_val(r.get(c_fd)),
            "dob": clean_val(r.get(c_dob)),
            "dod": dod,
            "current_age": clean_num(r.get(c_age)),
            "used_years": clean_num(r.get(c_used)),
            "g5_sire": normalize_ear(r.get(c_g5_s)),
            "g5_dam": normalize_ear(r.get(c_g5_d)),
            "total_born": clean_num(r.get(find_col(['同胎總產', 'Total born', '總產'], df_hier))),
            "born_alive": clean_num(r.get(find_col(['活胎', 'Born alive'], df_hier))),
            "weaning": clean_num(r.get(find_col(['離乳數', 'Weaning'], df_hier))),
            "spi": clean_num(r.get(find_col(['計算 SPI', 'SPI'], df_hier))),
            "mli": clean_num(r.get(find_col(['母系指數', 'MLI'], df_hier))),
            "tsi": clean_num(r.get(find_col(['終端公豬指數', 'TSI', 'PSI'], df_hier))),
            "inbreeding_f": ev["f"],
            "grade": ev["grade"],
            "g3_sire_full": sire_full,
            "g3_sire_line": sire_line,
            "g3_sire_spi": clean_num(r.get(find_col(['G3_父SPI', 'G3_父代SPI'], df_hier))),
            "g3_sire_mli": clean_num(r.get(find_col(['G3_父MLI', 'G3_父代MLI'], df_hier))),
            "g3_dam_full": dam_full,
            "g3_dam_line": dam_line,
            "g3_dam_spi": clean_num(r.get(find_col(['G3_母SPI', 'G3_母代SPI'], df_hier))),
            "g3_dam_mli": clean_num(r.get(find_col(['G3_母MLI', 'G3_母代MLI'], df_hier))),
            "ss_full": clean_val(r.get(find_col(['G2_祖父SS(全名)', 'G2_祖父SS全名'], df_hier))),
            "ss_line": clean_val(r.get(find_col(['G2_祖父SS(品系名)', '【G2_祖父SS】品系家族名'], df_hier))),
            "sd_full": clean_val(r.get(find_col(['G2_祖母SD(全名)', 'G2_祖母SD全名'], df_hier))),
            "sd_line": clean_val(r.get(find_col(['G2_祖母SD(品系名)', '【G2_祖母SD】品系家族名'], df_hier))),
            "ds_full": clean_val(r.get(find_col(['G2_外祖父DS(全名)', 'G2_外祖父DS全名'], df_hier))),
            "ds_line": clean_val(r.get(find_col(['G2_外祖父DS(品系名)', '【G2_外祖父DS】品系家族名'], df_hier))),
            "dd_full": clean_val(r.get(find_col(['G2_外祖母DD(全名)', 'G2_外祖母DD全名'], df_hier))),
            "dd_line": clean_val(r.get(find_col(['G2_外祖母DD(品系名)', '【G2_外祖母DD】品系家族名'], df_hier))),
            "g1_nodes": {
                "sss": clean_val(r.get(find_col(['G1_曾祖父SSS(品系名)', '【G1_曾祖父SSS】品系家族名'], df_hier))),
                "ssd": clean_val(r.get(find_col(['G1_曾祖母SSD(品系名)', '【G1_曾祖母SSD】品系家族名'], df_hier))),
                "sds": clean_val(r.get(find_col(['G1_曾祖父SDS(品系名)', '【G1_曾祖父SDS】品系家族名'], df_hier))),
                "sdd": clean_val(r.get(find_col(['G1_曾祖母SDD(品系名)', '【G1_曾祖母SDD】品系家族名'], df_hier))),
                "dss": clean_val(r.get(find_col(['G1_曾外祖父DSS(品系名)', '【G1_曾外祖父DSS】品系家族名'], df_hier))),
                "dsd": clean_val(r.get(find_col(['G1_曾外祖母DSD(品系名)', '【G1_曾外祖母DSD】品系家族名'], df_hier))),
                "dds": clean_val(r.get(find_col(['G1_曾外祖父DDS(品系名)', '【G1_曾外祖父DDS】品系家族名'], df_hier))),
                "ddd": clean_val(r.get(find_col(['G1_曾外祖母DDD(品系名)', '【G1_曾外祖母DDD】品系家族名'], df_hier)))
            }
        }
        pedigree_list.append(entry)

    for boar_ear, bdata in us_dict.items():
        if boar_ear not in known_ears:
            ev = eval_meta.get(boar_ear, {"f": "-", "grade": "-"})
            pedigree_list.append({
                "ear": boar_ear,
                "breed": bdata["breed"][0] if bdata["breed"] in ['LANDRACE', 'YORKSHIRE', 'DUROC'] else bdata["breed"],
                "sex": bdata["sex"], "parity": "-", "mate": "-", "mating_date": "-", "farrow_date": "-", "dob": "-",
                "dod": death_map.get(boar_ear, "-"),
                "current_age": "-", "used_years": "-",
                "g5_sire": "-", "g5_dam": "-",
                "total_born": "-", "born_alive": "-", "weaning": "-",
                "spi": bdata["spi"], "mli": bdata["mli"], "tsi": bdata["tsi"],
                "inbreeding_f": ev["f"], "grade": ev["grade"],
                "g3_sire_full": bdata["sire_full"], "g3_sire_line": bdata["sire_line"],
                "g3_sire_spi": bdata["sire_spi"], "g3_sire_mli": bdata["sire_mli"],
                "g3_dam_full": bdata["dam_full"], "g3_dam_line": bdata["dam_line"],
                "g3_dam_spi": bdata["dam_spi"], "g3_dam_mli": bdata["dam_mli"],
                "ss_full": bdata["ss_full"], "ss_line": bdata["ss_line"],
                "sd_full": bdata["sd_full"], "sd_line": bdata["sd_line"],
                "ds_full": bdata["ds_full"], "ds_line": bdata["ds_line"],
                "dd_full": bdata["dd_full"], "dd_line": bdata["dd_line"],
                "g1_nodes": bdata["g1_nodes"]
            })

    print("🚀 [5/6] 抓取《📊 育種_血統比例(轉)》...")
    raw_blood = fetch_sheet_csv(GID_BLOOD)
    df_blood = pd.read_csv(io.StringIO(raw_blood), low_memory=False) if raw_blood else pd.DataFrame()
    df_blood.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df_blood.columns]

    bloodline_map = {}
    if not df_blood.empty:
        c_b_ear = find_col(['查詢耳號', '耳號'], df_blood)
        blood_cols = [c for c in df_blood.columns if ('♂' in c or '♀' in c)]
        for _, r in df_blood.iterrows():
            ear = normalize_ear(r.get(c_b_ear))
            if ear == "-":
                continue
            ratios = {}
            for bc in blood_cols:
                val = clean_num(r.get(bc))
                if val != "-":
                    try:
                        num = float(val)
                        if num > 0:
                            ratios[bc] = round(num, 4)
                    except Exception:
                        pass
            if ratios:
                bloodline_map[ear] = ratios
    print(f"   ✓ 載入 {len(bloodline_map)} 頭個體始祖血統百分比。")

    print("🚀 [6/6] 抓取《肉豬與屠宰回溯》屠體與遺傳缺陷庫...")
    ear_to_line = {}
    for p in pedigree_list:
        if p["ear"] not in ear_to_line and p["g3_sire_line"] != "-":
            ear_to_line[p["ear"]] = p["g3_sire_line"]

    raw_carcass = fetch_sheet_csv(GID_CARCASS)
    df_carcass = pd.read_csv(io.StringIO(raw_carcass), low_memory=False) if raw_carcass else pd.DataFrame()
    df_carcass.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df_carcass.columns]

    carcass_list = []
    if not df_carcass.empty:
        c_p_ear  = find_col(['Porker Ear', '肉豬耳號'], df_carcass)
        c_sire   = find_col(['Sire', '父本公豬'], df_carcass)
        c_dam    = find_col(['Dam', '母本母豬'], df_carcass)
        c_wt     = find_col(['Market Wt', '銷售體重'], df_carcass)
        c_adg1   = find_col(['ADG1'], df_carcass)
        c_adg2   = find_col(['ADG2'], df_carcass)
        c_tw     = find_col(['TW-ADG'], df_carcass)
        c_yield  = find_col(['Carcass Yield', '屠宰得肉率'], df_carcass)
        c_hernia = find_col(['Hernia', '疝氣'], df_carcass)
        c_crypt  = find_col(['Cryptorchid', '隱睪'], df_carcass)
        c_prolap = find_col(['Prolapse', '脫肛'], df_carcass)
        c_leg    = find_col(['Leg Defect', '肢蹄缺陷'], df_carcass)
        c_red    = find_col(['Red Spot', '肌肉紅點'], df_carcass)
        c_stunt  = find_col(['Stunted', '發育遲緩'], df_carcass)

        for _, r in df_carcass.iterrows():
            ear  = normalize_ear(r.get(c_p_ear))
            sire = normalize_ear(r.get(c_sire))
            dam  = normalize_ear(r.get(c_dam))
            if ear == "-" or (sire == "-" and dam == "-"):
                continue

            defects = []
            if is_positive_flag(r.get(c_hernia)): defects.append('疝氣(Hernia)')
            if is_positive_flag(r.get(c_crypt)):  defects.append('隱睪(Crypt)')
            if is_positive_flag(r.get(c_prolap)): defects.append('脫肛(Prolapse)')
            if is_positive_flag(r.get(c_leg)):    defects.append('肢蹄問題(Leg)')
            if is_positive_flag(r.get(c_red)):    defects.append('肌肉紅點(RedSpot)')
            if is_positive_flag(r.get(c_stunt)):  defects.append('發育遲緩(Stunted)')

            def to_float(col):
                v = clean_num(r.get(col))
                return round(float(v), 1) if v != "-" else None

            wt_val = to_float(c_wt)
            dr_val = to_float(c_yield)
            ckg_val = round(wt_val * dr_val / 100.0, 1) if (wt_val and dr_val) else None

            carcass_list.append({
                'ear': ear,
                'sire': sire,
                'dam': dam,
                'g3_m': ear_to_line.get(sire, '-'),
                'g3_f': ear_to_line.get(dam, '-'),
                'wt': wt_val,
                'adg1': to_float(c_adg1),
                'adg2': to_float(c_adg2),
                'tw_adg': to_float(c_tw),
                'b_wk': None,
                's_wk': None,
                'dr': dr_val,
                'ckg': ckg_val,
                'defects': defects
            })
    print(f"   ✓ 成功收錄 {len(carcass_list)} 筆出欄屠體與遺傳缺陷記錄。")

    final_payload = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "pedigree": pedigree_list,
        "death_map": death_map,
        "us_index": us_dict,
        "bloodline_map": bloodline_map,
        "carcass_sales": carcass_list
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(final_payload, f, ensure_ascii=False)

    print(f"🎉 產出成功！共收錄 {len(pedigree_list)} 筆種豬真實胎次，{len(carcass_list)} 筆出欄肉豬。")


if __name__ == '__main__':
    main()
