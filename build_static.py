# -*- coding: utf-8 -*-
"""把 SQLite 数据库导出为静态 JSON，供 GitHub Pages 纯前端检索使用。

输出到 docs/data/：
  countries.json      — 252 国清单（含 max_level / 三语名）
  {ISO2}.json         — 每国全部区划扁平数组（含 level 0 国家根，供路径回溯）
前端选中某国后一次性 fetch 该国文件，在内存建树完成级联/详情/搜索，无后端。
"""

import json
import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DB_PATH

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "data")


def main():
    os.makedirs(OUT, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # countries.json
    countries = []
    for r in conn.execute(
        "SELECT iso2, iso3, name_en, name_zh, name_local, max_level, status "
        "FROM countries ORDER BY name_en"
    ):
        d = dict(r)
        countries.append({
            "iso2": d["iso2"], "iso3": d["iso3"],
            "name_en": d["name_en"], "name_zh": d["name_zh"],
            "name_local": d["name_local"],
            "max_level": d["max_level"] or 0, "status": d["status"],
        })
    with open(os.path.join(OUT, "countries.json"), "w", encoding="utf-8") as f:
        json.dump(countries, f, ensure_ascii=False, separators=(",", ":"))
    print(f"countries.json: {len(countries)} 国")

    # per-country {ISO2}.json
    total = 0
    for c in countries:
        iso2 = c["iso2"]
        rows = conn.execute(
            "SELECT code, name, name_zh, name_local, short_name, level, level_name, "
            "parent_code, source FROM regions WHERE country=? ORDER BY level, name",
            (iso2,),
        ).fetchall()
        arr = []
        for r in rows:
            d = dict(r)
            arr.append({
                "code": d["code"], "name": d["name"],
                "name_zh": d["name_zh"], "name_local": d["name_local"],
                "short_name": d["short_name"], "level": d["level"],
                "level_name": d["level_name"], "parent_code": d["parent_code"],
                "source": d["source"],
            })
        with open(os.path.join(OUT, f"{iso2}.json"), "w", encoding="utf-8") as f:
            json.dump(arr, f, ensure_ascii=False, separators=(",", ":"))
        total += len(arr)
    conn.close()
    print(f"per-country: 252 files, {total} 条区划")

    # size summary
    sz = sum(os.path.getsize(os.path.join(OUT, fn))
             for fn in os.listdir(OUT))
    print(f"docs/data 总大小: {sz/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
