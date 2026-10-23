import io
import json
import re
import pandas as pd
import requests

SPREADSHEET_ID = "1uWXfIMrRidpoZTq_BYYTy9ho_0a194pMMSS_EQpJoeA"

# 🌟 分頁 GID 定位
GID_US_ORIGIN = "1866228473"  # 美國原始種源數據
GID_MAIN = "0"  # 全期整合總表
GID_BLOOD = "60312190"  # 📊 育種_血統比例(轉)


def fetch_sheet_csv(gid):
  url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
  try:
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=40)
    res.encoding = "utf-8-sig"
    if res.status_code == 200:
      return res.text
    print(f"❌ 抓取 GID {gid} 失敗: HTTP {res.status_code}")
  except Exception as e:
    print(f"❌ 連線異常 GID {gid}: {e}")
  return ""


def clean_val(val):
  if pd.isna(val) or val is None:
    return "-"
  s = str(val).replace("\n", " ").replace("\r", "").strip()
  return s if s.lower() not in ["nan", "none", "", "null"] else "-"


def clean_num(val):
  s = clean_val(val)
  if s == "-":
    return "-"
  m = re.search(r"^\d+(\.\d+)?$", s)
  return m.group(0) if m else "-"


def main():
  print("🚀 [1/4] 抓取《美國原始種源數據》...")
  raw_us = fetch_sheet_csv(GID_US_ORIGIN)
  df_us = (
      pd.read_csv(io.StringIO(raw_us), low_memory=False)
      if raw_us
      else pd.DataFrame()
  )
  df_us.columns = [
      str(c).replace("\n", " ").replace("\r", "").strip() for c in df_us.columns
  ]

  us_dict = {}
  for _, r in df_us.iterrows():
    pen = r.get("手寫卡號 (Pen No)") or r.get("Pen No") or r.get("手寫卡號")
    breed = clean_val(r.get("品種 (Breed)") or r.get("Breed") or r.get("品種"))
    if pen is None or pd.isna(pen) or breed == "-":
      continue
    try:
      pen_num = int(float(pen))
    except:
      continue

    prefix = (
        "D"
        if "duroc" in breed.lower()
        else (
            "L"
            if "land" in breed.lower()
            else ("Y" if "york" in breed.lower() else "")
        )
    )
    ear_tag = f"{prefix}{pen_num}"
    sex_raw = clean_val(r.get("性別 (Sex)") or r.get("Sex") or r.get("性別"))
    sex = "MALE" if "boar" in sex_raw.lower() or "公" in sex_raw else "FEMALE"

    us_dict[ear_tag] = {
        "ear": ear_tag,
        "breed": breed.upper(),
        "sex": sex,
        "full_name": clean_val(r.get("G4_本代全名") or r.get("全名")),
        "family_line": clean_val(
            r.get("【G4_本代】品系家族名 (Family Line)")
            or r.get("品系家族名")
        ),
        "spi": clean_num(r.get("G4_SPI") or r.get("SPI")),
        "mli": clean_num(r.get("G4_MLI") or r.get("MLI")),
        "tsi": clean_num(r.get("G4_TSI") or r.get("TSI")),
        "sire_full": clean_val(
            r.get("G3_父代Sire全名") or r.get("G3_美系父親Sire(全名)")
        ),
        "sire_line": clean_val(
            r.get("【G3_父代Sire】品系家族名 (Family Line)")
            or r.get("G3_父品系家族名")
        ),
        "sire_spi": clean_num(r.get("G3_父代SPI") or r.get("G3_父SPI")),
        "sire_mli": clean_num(r.get("G3_父代MLI") or r.get("G3_父MLI")),
        "dam_full": clean_val(
            r.get("G3_母代Dam全名") or r.get("G3_美系母親Dam(全名)")
        ),
        "dam_line": clean_val(
            r.get("【G3_母代Dam】品系家族名 (Family Line)")
            or r.get("G3_母品系家族名")
        ),
        "dam_spi": clean_num(r.get("G3_母代SPI") or r.get("G3_母SPI")),
        "dam_mli": clean_num(r.get("G3_母代MLI") or r.get("G3_母MLI")),
        "ss_full": clean_val(
            r.get("G2_祖父SS全名") or r.get("G2_祖父SS(全名)")
        ),
        "ss_line": clean_val(
            r.get("【G2_祖父SS】品系家族名 (Family Line)")
            or r.get("G2_祖父SS(品系名)")
        ),
        "sd_full": clean_val(
            r.get("G2_祖母SD全名") or r.get("G2_祖母SD(全名)")
        ),
        "sd_line": clean_val(
            r.get("【G2_祖母SD】品系家族名 (Family Line)")
            or r.get("G2_祖母SD(品系名)")
        ),
        "ds_full": clean_val(
            r.get("G2_外祖父DS全名") or r.get("G2_外祖父DS(全名)")
        ),
        "ds_line": clean_val(
            r.get("【G2_外祖父DS】品系家族名 (Family Line)")
            or r.get("G2_外祖父DS(品系名)")
        ),
        "dd_full": clean_val(
            r.get("G2_外祖母DD全名") or r.get("G2_外祖母DD(全名)")
        ),
        "dd_line": clean_val(
            r.get("【G2_外祖母DD】品系家族名 (Family Line)")
            or r.get("G2_外祖母DD(品系名)")
        ),
        "g1_nodes": {
            "sss": clean_val(
                r.get("【G1_曾祖父SSS】品系家族名 (Family Line)")
                or r.get("G1_曾祖父SSS(品系名)")
            ),
            "ssd": clean_val(
                r.get("【G1_曾祖母SSD】品系家族名 (Family Line)")
                or r.get("G1_曾祖母SSD(品系名)")
            ),
            "sds": clean_val(
                r.get("【G1_曾祖父SDS】品系家族名 (Family Line)")
                or r.get("G1_曾祖父SDS(品系名)")
            ),
            "sdd": clean_val(
                r.get("【G1_曾祖母SDD】品系家族名 (Family Line)")
                or r.get("G1_曾祖母SDD(品系名)")
            ),
            "dss": clean_val(
                r.get("【G1_曾外祖父DSS】品系家族名 (Family Line)")
                or r.get("G1_曾外祖父DSS(品系名)")
            ),
            "dsd": clean_val(
                r.get("【G1_曾外祖母DSD】品系家族名 (Family Line)")
                or r.get("G1_曾外祖母DSD(品系名)")
            ),
            "dds": clean_val(
                r.get("【G1_曾外祖父DDS】品系家族名 (Family Line)")
                or r.get("G1_曾外祖父DDS(品系名)")
            ),
            "ddd": clean_val(
                r.get("【G1_曾外祖母DDD】品系家族名 (Family Line)")
                or r.get("G1_曾外祖母DDD(品系名)")
            ),
        },
    }

  print("🚀 [2/4] 抓取《📊 育種_血統比例(轉)》...")
  raw_blood = fetch_sheet_csv(GID_BLOOD)
  df_blood = (
      pd.read_csv(io.StringIO(raw_blood), low_memory=False)
      if raw_blood
      else pd.DataFrame()
  )
  df_blood.columns = [
      str(c).replace("\n", " ").replace("\r", "").strip()
      for c in df_blood.columns
  ]

  blood_map = {}
  if not df_blood.empty:
    c_b_ear = next(
        (c for c in df_blood.columns if "耳號" in c or "Ear" in c),
        df_blood.columns[0],
    )
    for _, br in df_blood.iterrows():
      b_ear = clean_val(br.get(c_b_ear)).upper()
      if b_ear == "-" or b_ear == "耳號":
        continue
      # 收集該豬隻的所有血統比例欄位
      details = {}
      for col in df_blood.columns:
        val = clean_val(br.get(col))
        if val != "-" and col != c_b_ear:
          details[col] = val
      blood_map[b_ear] = details
  print(f"   ✓ 成功收錄 {len(blood_map)} 頭豬隻之血統比例明細。")

  print("🚀 [3/4] 抓取主生產清單...")
  raw_main = fetch_sheet_csv(GID_MAIN)
  df_main = (
      pd.read_csv(io.StringIO(raw_main), low_memory=False)
      if raw_main
      else pd.DataFrame()
  )
  df_main.columns = [
      str(c).replace("\n", " ").replace("\r", "").strip()
      for c in df_main.columns
  ]

  def find_c(kws):
    for kw in kws:
      for c in df_main.columns:
        if kw.lower() in c.lower():
          return c
    return None

  c_ear = find_c(["耳號"]) or "耳號"
  c_sex = find_c(["Sex", "性別"]) or "Sex"
  c_p = find_c(["胎次(Parity)", "胎次", "Parity"]) or "胎次"
  c_mate = find_c(["當胎配種公豬", "配種公", "Mate"]) or "當胎配種公豬"
  c_md = find_c(["配種日期(Mating Date)", "配種日期"]) or "配種日期"
  c_fd = find_c(["當胎分娩日", "分娩日"]) or "當胎分娩日"
  c_dob = find_c(["DOB出生日期", "DOB", "出生日期"]) or "DOB"
  c_dod = find_c(["DOD/淘汰日期", "淘汰日期", "DOD"]) or "DOD/淘汰日期"
  c_breed = find_c(["Breed", "品種"]) or "Breed"
  c_age = find_c(["目前年齡(歲)", "年齡(歲)", "年齡"]) or "目前年齡(歲)"
  c_used = find_c(["已使用年限(年)", "使用年限"]) or "已使用年限(年)"

  pedigree_list = []
  death_map = {}
  known_ears = set()

  for _, r in df_main.iterrows():
    ear = clean_val(r.get(c_ear))
    if ear == "-" or ear == "耳號":
      continue
    ear_upper = ear.upper()
    known_ears.add(ear_upper)

    dod = clean_val(r.get(c_dod))
    if dod != "-":
      death_map[ear_upper] = dod

    breed = clean_val(r.get(c_breed)).upper()
    if breed == "-":
      breed = (
          "LY"
          if ear_upper.startswith("LY")
          else (
              "Y"
              if ear_upper.startswith("Y")
              else (
                  "L"
                  if ear_upper.startswith("L")
                  else ("D" if ear_upper.startswith("D") else "UNKNOWN")
              )
          )
      )
    else:
      if "YORK" in breed:
        breed = "Y"
      elif "LAND" in breed:
        breed = "L"
      elif "DUROC" in breed:
        breed = "D"
      elif "LY" in breed:
        breed = "LY"

    sire_full = clean_val(
        r.get(
            find_c(["G3_美系父親Sire(全名)", "G3_父代Sire全名", "第一代公"])
        )
    )
    sire_line = clean_val(
        r.get(find_c(["G3_父品系家族名", "【G3_父代Sire】品系家族名"]))
    )
    dam_full = clean_val(
        r.get(
            find_c(["G3_美系母親Dam(全名)", "G3_母代Dam全名", "第一代母"])
        )
    )
    dam_line = clean_val(
        r.get(find_c(["G3_母品系家族名", "【G3_母代Dam】品系家族名"]))
    )

    us_meta = us_dict.get(ear_upper, {})
    if sire_full == "-" and us_meta:
      sire_full = us_meta.get("sire_full", "-")
      sire_line = us_meta.get("sire_line", "-")
    if dam_full == "-" and us_meta:
      dam_full = us_meta.get("dam_full", "-")
      dam_line = us_meta.get("dam_line", "-")

    entry = {
        "ear": ear_upper,
        "breed": breed,
        "sex": (
            "FEMALE"
            if clean_val(r.get(c_sex)).upper() == "FEMALE"
            or ear_upper.startswith("LY")
            else "MALE"
        ),
        "parity": clean_num(r.get(c_p)),
        "mate": clean_val(r.get(c_mate)),
        "mating_date": clean_val(r.get(c_md)),
        "farrow_date": clean_val(r.get(c_fd)),
        "dob": clean_val(r.get(c_dob)),
        "dod": dod,
        "current_age": clean_num(r.get(c_age)),
        "used_years": clean_num(r.get(c_used)),
        "total_born": clean_num(
            r.get(find_c(["Total born同胎總生產數", "Total born", "總產"]))
        ),
        "born_alive": clean_num(
            r.get(find_c(["Born alive同胎次活胎數量", "Born alive", "活胎"]))
        ),
        "weaning": clean_num(
            r.get(find_c(["Weaning同胎次離乳數量", "Weaning", "離乳"]))
        ),
        "spi": clean_num(r.get(find_c(["計算 SPI", "SPI"]))),
        "mli": clean_num(r.get(find_c(["母系指數 (MLI)", "MLI"]))),
        "tsi": clean_num(r.get(find_c(["終端公豬指數 (TSI)", "TSI", "PSI"]))),
        "g3_sire_full": sire_full,
        "g3_sire_line": sire_line,
        "g3_sire_spi": clean_num(r.get(find_c(["G3_父SPI", "G3_父代SPI"]))),
        "g3_sire_mli": clean_num(r.get(find_c(["G3_父MLI", "G3_父代MLI"]))),
        "g3_dam_full": dam_full,
        "g3_dam_line": dam_line,
        "g3_dam_spi": clean_num(r.get(find_c(["G3_母SPI", "G3_母代SPI"]))),
        "g3_dam_mli": clean_num(r.get(find_c(["G3_母MLI", "G3_母代MLI"]))),
        "ss_full": clean_val(
            r.get(find_c(["G2_祖父SS(全名)", "G2_祖父SS全名"]))
        ),
        "ss_line": clean_val(
            r.get(find_c(["G2_祖父SS(品系名)", "【G2_祖父SS】品系家族名"]))
        ),
        "sd_full": clean_val(
            r.get(find_c(["G2_祖母SD(全名)", "G2_祖母SD全名"]))
        ),
        "sd_line": clean_val(
            r.get(find_c(["G2_祖母SD(品系名)", "【G2_祖母SD】品系家族名"]))
        ),
        "ds_full": clean_val(
            r.get(find_c(["G2_外祖父DS(全名)", "G2_外祖父DS全名"]))
        ),
        "ds_line": clean_val(
            r.get(
                find_c(["G2_外祖父DS(品系名)", "【G2_外祖父DS】品系家族名"])
            )
        ),
        "dd_full": clean_val(
            r.get(find_c(["G2_外祖母DD(全名)", "G2_外祖母DD全名"]))
        ),
        "dd_line": clean_val(
            r.get(
                find_c(["G2_外祖母DD(品系名)", "【G2_外祖母DD】品系家族名"])
            )
        ),
        "g1_nodes": {
            "sss": clean_val(
                r.get(
                    find_c([
                        "G1_曾祖父SSS(品系名)",
                        "【G1_曾祖父SSS】品系家族名",
                    ])
                )
            ),
            "ssd": clean_val(
                r.get(
                    find_c([
                        "G1_曾祖母SSD(品系名)",
                        "【G1_曾祖母SSD】品系家族名",
                    ])
                )
            ),
            "sds": clean_val(
                r.get(
                    find_c([
                        "G1_曾祖父SDS(品系名)",
                        "【G1_曾祖父SDS】品系家族名",
                    ])
                )
            ),
            "sdd": clean_val(
                r.get(
                    find_c([
                        "G1_曾祖母SDD(品系名)",
                        "【G1_曾祖母SDD】品系家族名",
                    ])
                )
            ),
            "dss": clean_val(
                r.get(
                    find_c([
                        "G1_曾外祖父DSS(品系名)",
                        "【G1_曾外祖父DSS】品系家族名",
                    ])
                )
            ),
            "dsd": clean_val(
                r.get(
                    find_c([
                        "G1_曾外祖母DSD(品系名)",
                        "【G1_曾外祖母DSD】品系家族名",
                    ])
                )
            ),
            "dds": clean_val(
                r.get(
                    find_c([
                        "G1_曾外祖父DDS(品系名)",
                        "【G1_曾外祖父DDS】品系家族名",
                    ])
                )
            ),
            "ddd": clean_val(
                r.get(
                    find_c([
                        "G1_曾外祖母DDD(品系名)",
                        "【G1_曾外祖母DDD】品系家族名",
                    ])
                )
            ),
        },
        "blood": blood_map.get(ear_upper, {}),
    }
    pedigree_list.append(entry)

  # 補齊美系種公豬
  for boar_ear, bdata in us_dict.items():
    if boar_ear not in known_ears:
      pedigree_list.append({
          "ear": boar_ear,
          "breed": (
              bdata["breed"][0]
              if bdata["breed"] in ["LANDRACE", "YORKSHIRE", "DUROC"]
              else bdata["breed"]
          ),
          "sex": bdata["sex"],
          "parity": "0",
          "mate": "-",
          "mating_date": "-",
          "farrow_date": "-",
          "dob": "-",
          "dod": "-",
          "current_age": "-",
          "used_years": "-",
          "total_born": "-",
          "born_alive": "-",
          "weaning": "-",
          "spi": bdata["spi"],
          "mli": bdata["mli"],
          "tsi": bdata["tsi"],
          "g3_sire_full": bdata["sire_full"],
          "g3_sire_line": bdata["sire_line"],
          "g3_sire_spi": bdata["sire_spi"],
          "g3_sire_mli": bdata["sire_mli"],
          "g3_dam_full": bdata["dam_full"],
          "g3_dam_line": bdata["dam_line"],
          "g3_dam_spi": bdata["dam_spi"],
          "g3_dam_mli": bdata["dam_mli"],
          "ss_full": bdata["ss_full"],
          "ss_line": bdata["ss_line"],
          "sd_full": bdata["sd_full"],
          "sd_line": bdata["sd_line"],
          "ds_full": bdata["ds_full"],
          "ds_line": bdata["ds_line"],
          "dd_full": bdata["dd_full"],
          "dd_line": bdata["dd_line"],
          "g1_nodes": bdata["g1_nodes"],
          "blood": blood_map.get(boar_ear, {}),
      })

  final_payload = {
      "pedigree": pedigree_list,
      "death_map": death_map,
      "us_index": us_dict,
      "blood_map": blood_map,
  }

  with open("data.json", "w", encoding="utf-8") as f:
    json.dump(final_payload, f, ensure_ascii=False)

  print(f"🎉 產出完成！收錄 {len(pedigree_list)} 頭個體。")


if __name__ == "__main__":
  main()
