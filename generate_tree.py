import io
import json
import re
import pandas as pd
import requests

SPREADSHEET_ID = "17TEL9lgV_3PzWUW0xj63LEiipyl5j_0W5BJjSVi89kA"
GID_TREE = "0"
URL_TREE = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID_TREE}"


def clean_str(val):
    if pd.isna(val) or val is None:
        return "-"
    s = str(val).strip().replace("\n", " ").replace("\r", "")
    return s if s.lower() not in ["nan", "none", "null", "undefined", ""] else "-"


def clean_name(name_str):
    if not name_str or name_str in ["-", "未記載", ""]:
        return "-"
    s = str(name_str).strip()
    s = re.sub(
        r"\b(1CR1|1CR2|CR1|CR2|CR-1|CR-2)\b", "", s, flags=re.IGNORECASE
    ).strip()
    parts = s.split()
    keywords = [
        p
        for p in parts
        if not re.match(r"^\d+[\-\d]*$", p)
        and p.upper() not in ["1CR1", "1CR2", "CR1", "CR2"]
    ]
    if keywords:
        if bool(re.search(r"\d", keywords[-1])) and len(keywords) > 1:
            keywords.pop()
        return " ".join(keywords).strip()
    return s


def parse_tag_range(range_str):
    if not range_str or range_str == "-":
        return None
    matches = re.findall(r"([A-Za-z]+)(\d+)", str(range_str))
    if len(matches) >= 2:
        p1, n1 = matches[0]
        p2, n2 = matches[1]
        if p1.upper() == p2.upper():
            return {"prefix": p1.upper(), "start": int(n1), "end": int(n2)}
    elif len(matches) == 1:
        p, n = matches[0]
        return {"prefix": p.upper(), "start": int(n), "end": int(n)}
    return None


def fetch_and_parse():
    print("🚀 [GLA Pedigree Engine] 開始提取數據庫...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        res = requests.get(URL_TREE, headers=headers, timeout=25)
        res.encoding = "utf-8-sig"
        if res.status_code != 200:
            print(f"❌ 雲端下載失敗，狀態碼: {res.status_code}")
            return
        df = pd.read_csv(io.StringIO(res.text))
        df.columns = [
            str(c).replace("\n", "").replace("\r", "").strip()
            for c in df.columns
        ]
        df = df.dropna(how="all")
        print(f"✅ 成功下載！原始筆數：{len(df)}")
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        return

    if df.empty:
        return

    def find_col(keywords):
        for kw in keywords:
            for col in df.columns:
                if kw.lower() in col.lower():
                    return col
        return None

    col_ear = find_col(["耳號", "Tag", "Ear"]) or df.columns[2]
    col_sex = find_col(["Sex", "性別"])
    col_parity = find_col(["胎次", "Parity"])
    col_mate = find_col(["當胎", "配種公", "Mate"])
    col_breed = find_col(["Breed", "品"])
    col_birth_date = find_col(["DOB", "出生日期", "生日", "個體生日"])
    col_farrow_date = find_col(["farrowing date", "分娩日期", "產房日期"])
    col_mating_date = find_col(["配種日期", "Mating Date"])

    col_spi = find_col(["SPI"])
    col_mli = find_col(["MLI"])
    col_tsi = find_col(["TSI"])
    col_total_born = find_col(["Total", "總生產", "總生"])
    col_born_alive = find_col(["Born", "活胎"])
    col_weaning = find_col(["Weaning", "離乳"])
    col_mother_wt = find_col(["mother total", "生育重", "窩重"])
    col_weaning_wt = find_col(["均重", "weight", "離乳均重"])
    col_tnb = find_col(["TNB"])
    col_nba = find_col(["NBA"])
    col_lteat = find_col(["lteat", "左乳"])
    col_rteat = find_col(["rteat", "右乳"])

    col_sire_sire = find_col(
        ["Sire 美系父親名(祖父)", "Sire 美系父親名", "祖父"]
    )
    col_sire_dam = find_col(
        ["Dam Name美系母親名(祖母)", "Dam Name美系母親名", "祖母"]
    )
    col_dam_sire = find_col(["Sire 美系父親名(外公)", "外公"])
    col_dam_dam = find_col(["Dam Name美系母親名(外婆)", "外婆"])
    col_gen1_sire = find_col(["第一代公", "Sire", "1代/2代公(父)"])
    col_gen1_dam = find_col(["第一代母", "Dam", "1代/2代母(母)"])
    col_gen2_sire = find_col(["第二代公", "2代-Sire祖父"])
    col_gen2_dam = find_col(["第二代母", "2代-Dam祖母"])

    col_retained_start = find_col(["Ear Notch Breeder (start)", "留種耳號區間"])
    col_retained_end = find_col(["Ear Notch Breeder (end)"])

    # 1. 建立產房留種區間索引庫 (對應 5 位數個體出生與父母)
    farrow_ranges = []
    us_boar_map = {}

    for _, row in df.iterrows():
        ear_val = clean_str(row.get(col_ear))
        if ear_val == "-":
            continue

        # 收集 4 位數美系原種資料
        tag_match = re.search(r"([A-Za-z]+)(\d+)", ear_val)
        if tag_match and len(tag_match.group(2)) == 4:
            us_boar_map[ear_val] = {
                "sire": clean_name(row.get(col_sire_sire)),
                "dam": clean_name(row.get(col_sire_dam)),
                "mgs": clean_name(row.get(col_dam_sire)),
                "dob": clean_str(row.get(col_birth_date)),
            }

        start_val = (
            clean_str(row.get(col_retained_start))
            if col_retained_start
            else "-"
        )
        end_val = (
            clean_str(row.get(col_retained_end)) if col_retained_end else "-"
        )

        range_obj = None
        if start_val != "-" and end_val != "-":
            m1 = re.search(r"([A-Za-z]+)(\d+)", start_val)
            m2 = re.search(r"([A-Za-z]+)(\d+)", end_val)
            if m1 and m2:
                range_obj = {
                    "prefix": m1.group(1).upper(),
                    "start": int(m1.group(2)),
                    "end": int(m2.group(2)),
                }
        elif start_val != "-":
            range_obj = parse_tag_range(start_val)

        if range_obj:
            farrow_ranges.append(
                {
                    "dam_ear": clean_str(
                        row.get(find_col(["母豬耳號", "Nombor Telinga"]))
                    )
                    or ear_val,
                    "sire_ear": clean_str(row.get(col_mate)),
                    "farrow_date": clean_str(row.get(col_farrow_date)),
                    "prefix": range_obj["prefix"],
                    "start": range_obj["start"],
                    "end": range_obj["end"],
                }
            )

    print(
        f"📊 已構建 {len(farrow_ranges)} 筆產房留種區間，{len(us_boar_map)} 筆美系原種庫存。"
    )

    # 2. 解析完整數據
    pedigree_data = []
    for _, row in df.iterrows():
        ear = clean_str(row.get(col_ear))
        if not ear or ear in ["-", ""]:
            continue

        raw_breed = clean_str(row.get(col_breed)).upper()
        if "LY" in ear.upper() or raw_breed == "LY":
            breed = "LY"
        elif "YY" in ear.upper() or ear.upper().startswith("Y"):
            breed = "Y"
        elif "LL" in ear.upper() or ear.upper().startswith("L"):
            breed = "L"
        else:
            breed = "D"

        raw_dob = clean_str(row.get(col_birth_date))
        farrow_date = clean_str(row.get(col_farrow_date))

        tag_match = re.search(r"([A-Za-z]+)(\d+)", ear)
        is_5_digit = False
        inferred_sire = clean_name(row.get(col_gen1_sire))
        inferred_dam = clean_name(row.get(col_gen1_dam))
        inferred_dob = raw_dob

        if tag_match:
            prefix, num_str = tag_match.groups()
            if len(num_str) >= 5:
                is_5_digit = True
                int_tag = int(num_str)
                for f_item in farrow_ranges:
                    if (
                        f_item["prefix"] == prefix.upper()
                        and f_item["start"] <= int_tag <= f_item["end"]
                    ):
                        inferred_dam = f_item["dam_ear"]
                        inferred_sire = f_item["sire_ear"]
                        if inferred_dob == "-":
                            inferred_dob = f_item["farrow_date"]
                        break

        # 向上追溯祖代
        s_sire = clean_name(row.get(col_sire_sire))
        s_dam = clean_name(row.get(col_sire_dam))
        d_sire = clean_name(row.get(col_dam_sire))
        d_dam = clean_name(row.get(col_dam_dam))

        if is_5_digit:
            if inferred_sire in us_boar_map:
                s_sire = us_boar_map[inferred_sire]["sire"] or s_sire
                s_dam = us_boar_map[inferred_sire]["dam"] or s_dam
            if inferred_dam in us_boar_map:
                d_sire = us_boar_map[inferred_dam]["sire"] or d_sire
                d_dam = (
                    us_boar_map[inferred_dam]["dam"]
                    or us_boar_map[inferred_dam]["mgs"]
                    or d_dam
                )

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": clean_str(row.get(col_sex)),
            "parity": clean_str(row.get(col_parity)),
            "mate": clean_str(row.get(col_mate)),
            "birth_date": inferred_dob,
            "dob": farrow_date,
            "mating_date": clean_str(row.get(col_mating_date)),
            "spi": clean_str(row.get(col_spi)),
            "mli": clean_str(row.get(col_mli)),
            "tsi": clean_str(row.get(col_tsi)),
            "total_born": clean_str(row.get(col_total_born)),
            "born_alive": clean_str(row.get(col_born_alive)),
            "weaning": clean_str(row.get(col_weaning)),
            "mother_wt": clean_str(row.get(col_mother_wt)),
            "weaning_wt": clean_str(row.get(col_weaning_wt)),
            "tnb": clean_str(row.get(col_tnb)),
            "nba": clean_str(row.get(col_nba)),
            "lteat": clean_str(row.get(col_lteat)),
            "rteat": clean_str(row.get(col_rteat)),
            "sire_sire": s_sire,
            "sire_dam": s_dam,
            "dam_sire": d_sire,
            "dam_dam": d_dam,
            "gen1_sire": inferred_sire,
            "gen1_dam": inferred_dam,
            "is_5_digit": is_5_digit,
            "details": {
                str(k).strip(): clean_str(v) for k, v in row.items()
            },
        }
        pedigree_data.append(entry)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)
    print(f"🎉 成功輸出 data.json（共 {len(pedigree_data)} 筆資料）！")


if __name__ == "__main__":
    fetch_and_parse()
