import pandas as pd
import json
import re

def clean_val(val):
    if pd.isna(val) or val is None:
        return "-"
    s = str(val).replace('\n', ' ').replace('\r', '').strip()
    return s if s.lower() not in ['nan', 'none', '', 'null'] else "-"

def clean_num(val):
    s = clean_val(val)
    if s == "-":
        return "-"
    m = re.search(r'^\d+(\.\d+)?$', s)
    return m.group(0) if m else "-"

def build_data_json():
    print("🚀 [Step 1/3] 解析《美國原始種源數據》建立基礎公母豬庫...")
    df_us = pd.read_csv('2_PY_族譜家族樹_GLA-pedigree-family_美國原始種源數據_轉.csv', low_memory=False)
    
    us_dict = {}
    for _, r in df_us.iterrows():
        pen = r.get('手寫卡號 (Pen No)')
        breed = clean_val(r.get('品種 (Breed)'))
        if pen is None or pd.isna(pen) or breed == "-":
            continue
        try:
            pen_num = int(float(pen))
        except:
            continue
        
        prefix = 'D' if 'duroc' in breed.lower() else ('L' if 'land' in breed.lower() else ('Y' if 'york' in breed.lower() else ''))
        ear_tag = f"{prefix}{pen_num}"
        sex_raw = clean_val(r.get('性別 (Sex)'))
        sex = "MALE" if 'boar' in sex_raw.lower() or '公' in sex_raw else "FEMALE"
        
        us_dict[ear_tag] = {
            "ear": ear_tag,
            "breed": breed.upper(),
            "sex": sex,
            "full_name": clean_val(r.get('G4_本代全名')),
            "family_line": clean_val(r.get('【G4_本代】品系家族名 (Family Line)')),
            "spi": clean_num(r.get('G4_SPI')),
            "mli": clean_num(r.get('G4_MLI')),
            "tsi": clean_num(r.get('G4_TSI')),
            "sire_full": clean_val(r.get('G3_父代Sire全名')),
            "sire_line": clean_val(r.get('【G3_父代Sire】品系家族名 (Family Line)')),
            "sire_spi": clean_num(r.get('G3_父代SPI')),
            "sire_mli": clean_num(r.get('G3_父代MLI')),
            "dam_full": clean_val(r.get('G3_母代Dam全名')),
            "dam_line": clean_val(r.get('【G3_母代Dam】品系家族名 (Family Line)')),
            "dam_spi": clean_num(r.get('G3_母代SPI')),
            "dam_mli": clean_num(r.get('G3_母代MLI')),
            "ss_full": clean_val(r.get('G2_祖父SS全名')),
            "ss_line": clean_val(r.get('【G2_祖父SS】品系家族名 (Family Line)')),
            "sd_full": clean_val(r.get('G2_祖母SD全名')),
            "sd_line": clean_val(r.get('【G2_祖母SD】品系家族名 (Family Line)')),
            "ds_full": clean_val(r.get('G2_外祖父DS全名')),
            "ds_line": clean_val(r.get('【G2_外祖父DS】品系家族名 (Family Line)')),
            "dd_full": clean_val(r.get('G2_外祖母DD全名')),
            "dd_line": clean_val(r.get('【G2_外祖母DD】品系家族名 (Family Line)')),
            "g1_nodes": {
                "sss": clean_val(r.get('【G1_曾祖父SSS】品系家族名 (Family Line)')),
                "ssd": clean_val(r.get('【G1_曾祖母SSD】品系家族名 (Family Line)')),
                "sds": clean_val(r.get('【G1_曾祖父SDS】品系家族名 (Family Line)')),
                "sdd": clean_val(r.get('【G1_曾祖母SDD】品系家族名 (Family Line)')),
                "dss": clean_val(r.get('【G1_曾外祖父DSS】品系家族名 (Family Line)')),
                "dsd": clean_val(r.get('【G1_曾外祖母DSD】品系家族名 (Family Line)')),
                "dds": clean_val(r.get('【G1_曾外祖父DDS】品系家族名 (Family Line)')),
                "ddd": clean_val(r.get('【G1_曾外祖母DDD】品系家族名 (Family Line)'))
            }
        }
    print(f"   ✓ 成功收錄 {len(us_dict)} 頭美系種公/母豬原原種四代檔案。")

    print("🚀 [Step 2/3] 解析《全期整合總表_配娩種》生產總表...")
    df_main = pd.read_csv('2_PY_族譜家族樹_GLA-pedigree-family_全期整合總表_配娩種_PY_轉.csv', low_memory=False)
    
    pedigree_list = []
    death_map = {}
    known_ears = set()

    for _, r in df_main.iterrows():
        ear = clean_val(r.get('耳號'))
        if ear == "-" or ear == "耳號":
            continue
        ear_upper = ear.upper()
        known_ears.add(ear_upper)
        
        # 淘汰/死亡偵測
        dod = clean_val(r.get('DOD/淘汰日期'))
        if dod != "-":
            death_map[ear_upper] = dod
            
        # 品種判斷
        breed = clean_val(r.get('Breed')).upper()
        if breed == "-":
            breed = "LY" if ear_upper.startswith("LY") else (
                "Y" if ear_upper.startswith("Y") else (
                "L" if ear_upper.startswith("L") else (
                "D" if ear_upper.startswith("D") else "UNKNOWN")))
        else:
            if "YORK" in breed: breed = "Y"
            elif "LAND" in breed: breed = "L"
            elif "DUROC" in breed: breed = "D"
            elif "LY" in breed: breed = "LY"

        # 血統四代欄位直接提取
        sire_full = clean_val(r.get('G3_美系父親Sire(全名)'))
        sire_line = clean_val(r.get('G3_父品系家族名'))
        dam_full  = clean_val(r.get('G3_美系母親Dam(全名)'))
        dam_line  = clean_val(r.get('G3_母品系家族名'))
        
        # 若該個體直接存在於美系原種庫中，資訊不足時互補
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
            "sex": "FEMALE" if clean_val(r.get('Sex')).upper() == "FEMALE" or ear_upper.startswith("LY") else "MALE",
            "parity": clean_num(r.get('胎次(Parity)')),
            "mate": clean_val(r.get('當胎配種公豬')),
            "mating_date": clean_val(r.get('配種日期(Mating Date)')),
            "farrow_date": clean_val(r.get('當胎分娩日')),
            "dob": clean_val(r.get('DOB出生日期')),
            "dod": dod,
            "total_born": clean_num(r.get('Total born同胎總生產數')),
            "born_alive": clean_num(r.get('Born alive同胎次活胎數量')),
            "weaning": clean_num(r.get('Weaning同胎次離乳數量')),
            "spi": clean_num(r.get('計算 SPI')),
            "mli": clean_num(r.get('母系指數 (MLI)')),
            "tsi": clean_num(r.get('終端公豬指數 (TSI)')),
            # G3 (父母)
            "g3_sire_full": sire_full,
            "g3_sire_line": sire_line,
            "g3_sire_spi": clean_num(r.get('G3_父SPI')),
            "g3_sire_mli": clean_num(r.get('G3_父MLI')),
            "g3_dam_full": dam_full,
            "g3_dam_line": dam_line,
            "g3_dam_spi": clean_num(r.get('G3_母SPI')),
            "g3_dam_mli": clean_num(r.get('G3_母MLI')),
            # G2 (祖父母)
            "ss_full": clean_val(r.get('G2_祖父SS(全名)')),
            "ss_line": clean_val(r.get('G2_祖父SS(品系名)')),
            "sd_full": clean_val(r.get('G2_祖母SD(全名)')),
            "sd_line": clean_val(r.get('G2_祖母SD(品系名)')),
            "ds_full": clean_val(r.get('G2_外祖父DS(全名)')),
            "ds_line": clean_val(r.get('G2_外祖父DS(品系名)')),
            "dd_full": clean_val(r.get('G2_外祖母DD(全名)')),
            "dd_line": clean_val(r.get('G2_外祖母DD(品系名)')),
            # G1 (曾祖輩品系名)
            "g1_nodes": {
                "sss": clean_val(r.get('G1_曾祖父SSS(品系名)')),
                "ssd": clean_val(r.get('G1_曾祖母SSD(品系名)')),
                "sds": clean_val(r.get('G1_曾祖父SDS(品系名)')),
                "sdd": clean_val(r.get('G1_曾祖母SDD(品系名)')),
                "dss": clean_val(r.get('G1_曾外祖父DSS(品系名)')),
                "dsd": clean_val(r.get('G1_曾外祖母DSD(品系名)')),
                "dds": clean_val(r.get('G1_曾外祖父DDS(品系名)')),
                "ddd": clean_val(r.get('G1_曾外祖母DDD(品系名)'))
            }
        }
        pedigree_list.append(entry)

    print("🚀 [Step 3/3] 補齊美系配種公豬獨立卡片至總名冊...")
    boar_added_count = 0
    for boar_ear, bdata in us_dict.items():
        if boar_ear not in known_ears:
            pedigree_list.append({
                "ear": boar_ear,
                "breed": bdata["breed"][0] if bdata["breed"] in ['LANDRACE', 'YORKSHIRE', 'DUROC'] else bdata["breed"],
                "sex": bdata["sex"],
                "parity": "0",
                "mate": "-",
                "mating_date": "-",
                "farrow_date": "-",
                "dob": "-",
                "dod": "-",
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
                "g1_nodes": bdata["g1_nodes"]
            })
            boar_added_count += 1

    final_payload = {
        "pedigree": pedigree_list,
        "death_map": death_map,
        "us_index": us_dict
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(final_payload, f, ensure_ascii=False, indent=2)

    print(f"🎉 完成！共收錄 {len(pedigree_list)} 筆記錄 (含獨立導入美系公豬 {boar_added_count} 頭)。data.json 輸出完畢！")

if __name__ == '__main__':
    build_data_json()
