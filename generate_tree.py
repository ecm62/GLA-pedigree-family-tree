import io
import json
import re
import pandas as pd
import requests

SPREADSHEET_ID = "1uWXfIMrRidpoZTq_BYYTy9ho_0a194pMMSS_EQpJoeA"

# 🌟 分頁 GID 定位
GID_US_ORIGIN = "1866228473"  # 美國原始種源數據
GID_MAIN = "1807731938"  # 📊 主生產表 (含 目前年齡、已使用年限)
GID_BLOOD = "60312190"  # 📊 育種_血統比例(轉)
GID_SALES = "84920994"  # 全生命週期銷售與血統分析 (若 GID 不同，腳本會自動讀取備份)


def fetch_sheet_csv(gid):
  url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
  try:
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=40)
    res.encoding = "utf-8-sig"
    if res.status_code == 200:
      return res.text
  except Exception as e:
    print(f"❌ 連線 GID {gid} 異常: {e}")
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

  print("🚀 [2/4] 抓取《主生產清單 (GID: 1807731938)》...")
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

  def find_c(kws, df):
    for kw in kws:
      for c in df.columns:
        if kw.lower() in c.lower():
          return c
    return None

  c_ear = find_c(["耳號"], df_main) or "耳號"
  c_sex = find_c(["Sex", "性別"], df_main) or "Sex"
  c_p = find_c(["胎次(Parity)", "胎次", "Parity"], df_main) or "胎次"
  c_mate = find_c(["當胎配種公豬", "配種公", "Mate"], df_main) or "當胎配種公豬"
  c_md = find_c(["配種日期(Mating Date)", "配種日期"], df_main) or "配種日期"
  c_fd = find_c(["當胎分娩日", "分娩日"], df_main) or "當胎分娩日"
  c_dob = find_c(["DOB出生日期", "DOB", "出生日期"], df_main) or "DOB"
  c_dod = find_c(["DOD/淘汰日期", "淘汰日期", "DOD"], df_main) or "DOD/淘汰日期"
  c_breed = find_c(["Breed", "品種"], df_main) or "Breed"
  c_age = (
      find_c(["目前年齡(歲)", "目前年齡", "年齡(歲)", "年齡"], df_main)
      or "目前年齡(歲)"
  )
  c_used = (
      find_c(["已使用年限(年)", "已使用年限", "使用年限"], df_main)
      or "已使用年限(年)"
  )

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
            find_c(["G3_美系父親Sire(全名)", "G3_父代Sire全名", "第一代公"], df_main)
        )
    )
    sire_line = clean_val(
        r.get(find_c(["G3_父品系家族名", "【G3_父代Sire】品系家族名"], df_main))
    )
    dam_full = clean_val(
        r.get(
            find_c(["G3_美系母親Dam(全名)", "G3_母代Dam全名", "第一代母"], df_main)
        )
    )
    dam_line = clean_val(
        r.get(find_c(["G3_母品系家族名", "【G3_母代Dam】品系家族名"], df_main))
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
            r.get(find_c(["Total born同胎總生產數", "Total born", "總產"], df_main))
        ),
        "born_alive": clean_num(
            r.get(find_c(["Born alive同胎次活胎數量", "Born alive", "活胎"], df_main))
        ),
        "weaning": clean_num(
            r.get(find_c(["Weaning同胎次離乳數量", "Weaning", "離乳"], df_main))
        ),
        "spi": clean_num(r.get(find_c(["計算 SPI", "SPI"], df_main))),
        "mli": clean_num(r.get(find_c(["母系指數 (MLI)", "MLI"], df_main))),
        "tsi": clean_num(
            r.get(find_c(["終端公豬指數 (TSI)", "TSI", "PSI"], df_main))
        ),
        "g3_sire_full": sire_full,
        "g3_sire_line": sire_line,
        "g3_sire_spi": clean_num(
            r.get(find_c(["G3_父SPI", "G3_父代SPI"], df_main))
        ),
        "g3_sire_mli": clean_num(
            r.get(find_c(["G3_父MLI", "G3_父代MLI"], df_main))
        ),
        "g3_dam_full": dam_full,
        "g3_dam_line": dam_line,
        "g3_dam_spi": clean_num(
            r.get(find_c(["G3_母SPI", "G3_母代SPI"], df_main))
        ),
        "g3_dam_mli": clean_num(
            r.get(find_c(["G3_母MLI", "G3_母代MLI"], df_main))
        ),
        "ss_full": clean_val(
            r.get(find_c(["G2_祖父SS(全名)", "G2_祖父SS全名"], df_main))
        ),
        "ss_line": clean_val(
            r.get(find_c(["G2_祖父SS(品系名)", "【G2_祖父SS】品系家族名"], df_main))
        ),
        "sd_full": clean_val(
            r.get(find_c(["G2_祖母SD(全名)", "G2_祖母SD全名"], df_main))
        ),
        "sd_line": clean_val(
            r.get(find_c(["G2_祖母SD(品系名)", "【G2_祖母SD】品系家族名"], df_main))
        ),
        "ds_full": clean_val(
            r.get(find_c(["G2_外祖父DS(全名)", "G2_外祖父DS全名"], df_main))
        ),
        "ds_line": clean_val(
            r.get(
                find_c(
                    ["G2_外祖父DS(品系名)", "【G2_外祖父DS】品系家族名"], df_main
                )
            )
        ),
        "dd_full": clean_val(
            r.get(find_c(["G2_外祖母DD(全名)", "G2_外祖母DD全名"], df_main))
        ),
        "dd_line": clean_val(
            r.get(
                find_c(
                    ["G2_外祖母DD(品系名)", "【G2_外祖母DD】品系家族名"], df_main
                )
            )
        ),
        "g1_nodes": {
            "sss": clean_val(
                r.get(
                    find_c(
                        [
                            "G1_曾祖父SSS(品系名)",
                            "【G1_曾祖父SSS】品系家族名",
                        ],
                        df_main,
                    )
                )
            ),
            "ssd": clean_val(
                r.get(
                    find_c(
                        [
                            "G1_曾祖母SSD(品系名)",
                            "【G1_曾祖母SSD】品系家族名",
                        ],
                        df_main,
                    )
                )
            ),
            "sds": clean_val(
                r.get(
                    find_c(
                        [
                            "G1_曾祖父SDS(品系名)",
                            "【G1_曾祖父SDS】品系家族名",
                        ],
                        df_main,
                    )
                )
            ),
            "sdd": clean_val(
                r.get(
                    find_c(
                        [
                            "G1_曾祖母SDD(品系名)",
                            "【G1_曾祖母SDD】品系家族名",
                        ],
                        df_main,
                    )
                )
            ),
            "dss": clean_val(
                r.get(
                    find_c(
                        [
                            "G1_曾外祖父DSS(品系名)",
                            "【G1_曾外祖父DSS】品系家族名",
                        ],
                        df_main,
                    )
                )
            ),
            "dsd": clean_val(
                r.get(
                    find_c(
                        [
                            "G1_曾外祖母DSD(品系名)",
                            "【G1_曾外祖母DSD】品系家族名",
                        ],
                        df_main,
                    )
                )
            ),
            "dds": clean_val(
                r.get(
                    find_c(
                        [
                            "G1_曾外祖父DDS(品系名)",
                            "【G1_曾外祖父DDS】品系家族名",
                        ],
                        df_main,
                    )
                )
            ),
            "ddd": clean_val(
                r.get(
                    find_c(
                        [
                            "G1_曾外祖母DDD(品系名)",
                            "【G1_曾外祖母DDD】品系家族名",
                        ],
                        df_main,
                    )
                )
            ),
        },
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
      })

  print("🚀 [3/4] 抽取《全生命週期銷售與血統分析》屠體與遺傳缺陷庫...")
  raw_sales = fetch_sheet_csv(GID_SALES)
  if raw_sales:
    df_sales = pd.read_csv(io.StringIO(raw_sales), low_memory=False)
  else:
    # 嘗試由本地快照抽取
    try:
      df_sales = pd.read_csv(
          "2_PY_族譜家族樹_GLA-pedigree-family_全生命週期銷售與血統分析_PY_轉.csv",
          low_memory=False,
      )
    except:
      df_sales = pd.DataFrame()

  carcass_list = []
  if not df_sales.empty:
    for _, r in df_sales.iterrows():
      sire = str(r["G4-m"]).strip() if pd.notna(r.get("G4-m")) else "-"
      dam = str(r["G4-f"]).strip() if pd.notna(r.get("G4-f")) else "-"
      ear = str(r["Ear Notch"]).strip() if pd.notna(r.get("Ear Notch")) else "-"
      if ear == "-" or (sire == "-" and dam == "-"):
        continue

      defects = []
      if pd.notna(r.get("Hernia")) and str(r.get("Hernia")).strip() not in [
          "0",
          "0.0",
          "-",
      ]:
        defects.append("疝氣(Hernia)")
      if pd.notna(r.get("Cryptorchidism")) and str(
          r.get("Cryptorchidism")
      ).strip() not in ["0", "0.0", "-"]:
        defects.append("隱睪(Crypt)")
      if pd.notna(r.get("Rectal prolapse")) and str(
          r.get("Rectal prolapse")
      ).strip() not in ["0", "0.0", "-"]:
        defects.append("脫肛(Prolapse)")
      if pd.notna(r.get("Leg Problem")) and str(
          r.get("Leg Problem")
      ).strip() not in ["0", "0.0", "-"]:
        defects.append("肢蹄問題(Leg)")
      if pd.notna(r.get("Stunted")) and str(r.get("Stunted")).strip() not in [
          "0",
          "0.0",
          "-",
      ]:
        defects.append("僵豬(Stunted)")
      if pd.notna(r.get("Abnormal")) and str(r.get("Abnormal")).strip() not in [
          "0",
          "0.0",
          "-",
      ]:
        defects.append("畸形(Abnormal)")
      if pd.notna(r.get("reject")) and str(r.get("reject")).strip() not in [
          "0",
          "0.0",
          "-",
      ]:
        defects.append("淘汰(Reject)")

      carcass_list.append({
          "ear": ear,
          "sire": sire,
          "dam": dam,
          "g3_m": str(r["G3-m"]).strip() if pd.notna(r.get("G3-m")) else "-",
          "g3_f": str(r["G3-f"]).strip() if pd.notna(r.get("G3-f")) else "-",
          "wt": (
              round(float(r["Weight(kg)的AVERAGE"]), 1)
              if pd.notna(r.get("Weight(kg)的AVERAGE"))
              else None
          ),
          "adg1": (
              round(float(r["ADG1的AVERAGE"]), 1)
              if pd.notna(r.get("ADG1的AVERAGE"))
              else None
          ),
          "adg2": (
              round(float(r["ADG2的AVERAGE"]), 1)
              if pd.notna(r.get("ADG2的AVERAGE"))
              else None
          ),
          "b_wk": (
              int(float(r["Birth Week num"]))
              if pd.notna(r.get("Birth Week num"))
              else None
          ),
          "s_wk": (
              int(float(r["Sold week num"]))
              if pd.notna(r.get("Sold week num"))
              else None
          ),
          "dr": (
              round(float(r["出肉率/屠體率 (Dressing Rate %)"]), 1)
              if pd.notna(r.get("出肉率/屠體率 (Dressing Rate %)"))
              else None
          ),
          "ckg": (
              round(float(r["Carcass kg的AVERAGE"]), 1)
              if pd.notna(r.get("Carcass kg的AVERAGE"))
              else None
          ),
          "defects": defects,
      })
  print(f"   ✓ 成功收錄 {len(carcass_list)} 筆屠體與遺傳缺陷檢定記錄。")

  final_payload = {
      "pedigree": pedigree_list,
      "death_map": death_map,
      "us_index": us_dict,
      "carcass_sales": carcass_list,
  }

  with open("data.json", "w", encoding="utf-8") as f:
    json.dump(final_payload, f, ensure_ascii=False)

  print(f"🎉 產出完成！收錄 {len(pedigree_list)} 頭種豬，data.json 輸出成功。")


if __name__ == "__main__":
  main()
