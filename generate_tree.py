import json
import pandas as pd
import requests
import io
import re

SPREADSHEET_ID = "1MlhcSXitL_jWYvXVfmo6bQfQqDPIDgUt0VGIZVaB5aw"

GID_US_ORIGIN = "1267648620"   # 美國原始種源數據
GID_COMBINED = "84920994"      # 合併報表(配種+產房)
GID_DEATH = "1606643507"       # Death sow and gilt (Import) 官方死亡分頁
GID_MAIN = "0"                 # 主表 / 育種家族階層清單

def fetch_sheet_csv(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        res.encoding = 'utf-8-sig'
        if res.status_code == 200:
            df = pd.read_csv(io.StringIO(res.text))
            df.columns = [str(c).replace('\n', ' ').replace('\r', '').strip() for c in df.columns]
            return df.dropna(how='all')
    except Exception as e:
        print(f"❌ 讀取 GID {gid} 失敗: {e}")
    return pd.DataFrame()

def fetch_and_parse():
    print("🚀 正在重新整理精準的死亡判定資料...")
    
    df_main = fetch_sheet_csv(GID_MAIN)
    if df_main.empty:
        print("❌ 主表資料為空！")
        return

    # 🌟 嚴格載入 Death sow and gilt (Import) 分頁的耳號清單
    df_death = fetch_sheet_csv(GID_DEATH)
    official_death_set = set()
    if not df_death.empty:
        #尋找包含 Ear Tag 或耳號的欄位
        ear_col_death = next((c for c in df_death.columns if 'Ear Tag' in c or '耳號' in c or 'Ear' in c), df_death.columns[2] if len(df_death.columns) > 2 else None)
        if ear_col_death:
            for _, r in df_death.iterrows():
                e = str(r.get(ear_col_death, '')).strip().upper()
                if e and e.lower() not in ['nan', 'none', '-', '']:
                    official_death_set.add(e)
    print(f"💀 官方真正死亡清單載入完成，共計 {len(official_death_set)} 筆")

    # (其他 DOB 與區間邏輯維持不變...)
    # 輸出資料時確保：
    # "is_dead": ear_upper in official_death_set (只有確實在此 Set 內的才是 True，其餘絕對是 False)
