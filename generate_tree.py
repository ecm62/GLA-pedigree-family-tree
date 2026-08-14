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
    print("🚀 [GLA Engine] 正在下載雲端數據庫並建立雙向索引...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(URL_TREE, headers=headers, timeout=25)
        res.encoding = "utf-8-sig"
        if res.status_code != 200:
            print(f"❌ 下載失敗: {res.status_code}")
            return
        df = pd.read_csv(io.StringIO(res.text))
        df.columns = [
            str(c).replace("\n", "").replace("\r", "").strip()
            for c in df.columns
        ]
        df = df.dropna(how="all")
        print(f"✅ 成功下載原始資料：{len(df)} 筆")
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

    # 欄位對齊
    col_ear = find_col(["Nombor Telinga 母豬耳號", "母豬耳號", "Nombor Telinga", "耳號", "Tag"]) or df.columns[2]
    col_sex = find_col(["Sex", "性別"])
    col_parity = find_col(["胎次Parity", "胎次", "Parity", "Pari"])
    col_mate = find_col(["配種公豬Boar mate", "當胎配種公", "Jantan 配種公", "Jantan", "Mate"])
    col_breed = find_col(["親代品系Sow's breed", "Breed", "品系", "Baka"])
    
    col_us_dob = find_col(["DOB出生日期", "DOB", "出生日期", "個體生日"])
    col_mating_date = find_col(["Tarikh Kahwin 配種日期", "Tarikh Kahwin", "配種日期", "Mating Date"])
    col_farrow_date = find_col(["分娩日Farrowing", "Tarikh Farrowing", "Tarikh beranak", "分娩日", "產房日期"])

    col_spi = find_col(["SPI"])
    col_mli = find_col(["MLI"])
    col_tsi = find_col(["TSI"])
    col_total_born = find_col(["Total born", "總生產", "總生", "Total"])
    col_born_alive = find_col(["Born alive", "活胎"])
    col_weaning = find_col(["Weaning", "離乳"])
    col_mother_wt = find_col(["Mother total Weight", "母豬生育重量", "生育重"])
    col_weaning_wt = find_col(["weaning weight", "離乳平均重", "均重"])
    col_tnb = find_col(["TNB"])
    col_nba = find_col(["NBA"])
    col_lteat = find_col(["Lteat", "左乳"])
    col_rteat = find_col(["Rteat", "右乳"])

    col_sire_sire = find_col(["Sire 美系第0代父親名", "Sire Name美系父親名", "Sire 美系父親名(祖父)", "祖父"])
    col_sire_dam  = find_col(["Dam Name美系第0代母親名", "Dam Name美系母親名", "Dam Name美系母親名(祖母)", "祖母"])
    col_dam_sire  = find_col(["Sire 美系第0代外公", "Sire 美系父親名(外公)", "外公"])
    col_dam_dam   = find_col(["Dam Name美系第0代外婆", "Dam Name美系母親名(外婆)", "外婆"])
    col_gen1_sire = find_col(["1代/2代公(父)", "第一代公", "Sire"])
    col_gen1_dam  = find_col(["1代/2代母(母)", "第一代母", "Dam"])

    col_retained_start = find_col(["Ear Notch Breeder (start)", "留種耳號區間"])
    col_retained_end   = find_col(["Ear Notch Breeder (end)"])

    # 1. 建立 4 位數美系原種庫 (固定 DOB 與美系祖先) 與 5 位數留種區間庫
    us_stock_map = {}
    farrow_ranges = []

    for _, row in df.iterrows():
        ear_val = clean_str(row.get(col_ear))
        if ear_val == "-":
            continue

        tag_match = re.search(r"([A-Za-z]+)(\d+)", ear_val)
        raw_dob_val = clean_str(row.get(col_us_dob))

        # 4 位數原種個體：鎖定真實 DOB (來自美國原始種源數據)
        if tag_match and len(tag_match.group(2)) == 4:
            if ear_val not in us_stock_map or (us_stock_map[ear_val]["dob"] == "-" and raw_dob_val != "-"):
                us_stock_map[ear_val] = {
                    "dob": raw_dob_val if raw_dob_val != "-" else us_stock_map.get(ear_val, {}).get("dob", "-"),
                    "sire_sire": clean_name(row.get(col_sire_sire)),
                    "sire_dam": clean_name(row.get(col_sire_dam)),
                    "dam_sire": clean_name(row.get(col_dam_sire)),
                    "dam_dam": clean_name(row.get(col_dam_dam)),
                }

        # 5 位數自繁個體：收集產房分娩留種區間 (來自 🧬GLA 遺傳育種資訊)
        start_val = clean_str(row.get(col_retained_start)) if col_retained_start else "-"
        end_val   = clean_str(row.get(col_retained_end)) if col_retained_end else "-"
        
        range_obj = None
        if start_val != "-" and end_val != "-":
            m1 = re.search(r"([A-Za-z]+)(\d+)", start_val)
            m2 = re.search(r"([A-Za-z]+)(\d+)", end_val)
            if m1 and m2:
                range_obj = {"prefix": m1.group(1).upper(), "start": int(m1.group(2)), "end": int(m2.group(2))}
        elif start_val != "-":
            range_obj = parse_tag_range(start_val)

        if range_obj:
            farrow_ranges.append({
                "dam_ear": ear_val,
                "sire_ear": clean_str(row.get(col_mate)),
                "farrow_date": clean_str(row.get(col_farrow_date)),
                "prefix": range_obj["prefix"],
                "start": range_obj["start"],
                "end": range_obj["end"]
            })

    print(f"📊 已鎖定 {len(us_stock_map)} 隻美系原種真實生日庫，{len(farrow_ranges)} 筆產房留種出生索引。")

    # 2. 正式組裝每一筆胎次數據
    pedigree_data = []
    for _, row in df.iterrows():
        ear = clean_str(row.get(col_ear))
        if not ear or ear in ["-", ""]:
            continue

        raw_breed = clean_str(row.get(col_breed)).upper()
        if "LY" in ear.upper() or "LY" in raw_breed:
            breed = "LY"
        elif "YY" in ear.upper() or ear.upper().startswith("Y"):
            breed = "Y"
        elif "LL" in ear.upper() or ear.upper().startswith("L"):
            breed = "L"
        else:
            breed = "D"

        farrow_date = clean_str(row.get(col_farrow_date))
        mating_date = clean_str(row.get(col_mating_date))

        tag_match = re.search(r"([A-Za-z]+)(\d+)", ear)
        real_birth_date = "-"
        inferred_sire = clean_name(row.get(col_gen1_sire))
        inferred_dam = clean_name(row.get(col_gen1_dam))
        s_sire = clean_name(row.get(col_sire_sire))
        s_dam  = clean_name(row.get(col_sire_dam))
        d_sire = clean_name(row.get(col_dam_sire))
        d_dam  = clean_name(row.get(col_dam_dam))
        is_5_digit = False

        if tag_match:
            prefix, num_str = tag_match.groups()
            # 4 位數（第 1 代原種）：直接從原種庫拿出生日，絕不拿當胎分娩日
            if len(num_str) == 4:
                if ear in us_stock_map and us_stock_map[ear]["dob"] != "-":
                    real_birth_date = us_stock_map[ear]["dob"]
                else:
                    real_birth_date = clean_str(row.get(col_us_dob))

            # 5 位數（第 2 代自繁）：從產房留種區間反查出生日的固定分娩日
            elif len(num_str) >= 5:
                is_5_digit = True
                int_tag = int(num_str)
                for f_item in farrow_ranges:
                    if f_item["prefix"] == prefix.upper() and f_item["start"] <= int_tag <= f_item["end"]:
                        inferred_dam = f_item["dam_ear"]
                        inferred_sire = f_item["sire_ear"]
                        real_birth_date = f_item["farrow_date"]
                        break

                if inferred_sire in us_stock_map:
                    s_sire = us_stock_map[inferred_sire]["sire_sire"] or s_sire
                    s_dam  = us_stock_map[inferred_sire]["sire_dam"]  or s_dam
                if inferred_dam in us_stock_map:
                    d_sire = us_stock_map[inferred_dam]["sire_sire"] or d_sire
                    d_dam  = us_stock_map[inferred_dam]["sire_dam"]  or d_dam

        entry = {
            "ear": ear,
            "breed": breed,
            "sex": clean_str(row.get(col_sex)),
            "parity": clean_str(row.get(col_parity)),
            "mate": clean_str(row.get(col_mate)),
            "birth_date": real_birth_date,     # 終身固定的真實生日 (如 D1061 固定為 2023-08-18)
            "mating_date": mating_date,        # 當胎配種日 (如 2024-12-31)
            "dob": farrow_date,                # 當胎分娩日 (如 2025-04-26)
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
            "details": {str(k).strip(): clean_str(v) for k, v in row.items()}
        }
        pedigree_data.append(entry)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(pedigree_data, f, ensure_ascii=False, indent=2)
    print(f"🎉 成功更新 data.json（共 {len(pedigree_data)} 筆紀錄，真實生日已全面校正對齊）！")


if __name__ == "__main__":
    fetch_and_parse()
