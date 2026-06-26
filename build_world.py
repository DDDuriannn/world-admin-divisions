# -*- coding: utf-8 -*-
"""世界行政区划数据库构建入口。

用法：
  python build_world.py --probe            # 探活 GeoNames + GADM
  python build_world.py --countries        # 抓取国家清单入库
  python build_world.py --country US       # 抓单国（测试）
  python build_world.py                    # 全量逐国抓取（最长 5 级）
  python build_world.py --resume           # 续抓，跳过已 done 的国家
  python build_world.py --max-level 2      # 全量但只到 2 级
  python build_world.py --status           # 查看各国抓取进度
"""

import argparse
import logging
import sys

# Windows 控制台 UTF-8
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import (WORLD_MAX_LEVEL, GEONAMES_COUNTRYINFO_URL, GADM_BASE,
                    GADM_SKIP_COUNTRIES)
from crawler.base import BaseFetcher
from crawler import db
from crawler.world import pipeline
from crawler.world import mledoze


def setup_logging(verbose=False):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_probe(args):
    fetcher = BaseFetcher()
    print("== 探活 GeoNames 国家清单 ==")
    text = fetcher.get(GEONAMES_COUNTRYINFO_URL, as_text=True, encoding="utf-8")
    if text:
        n = sum(1 for ln in text.splitlines()
                if ln.strip() and not ln.startswith("#"))
        print(f"  [OK] countryInfo.txt: {n} 个国家")
    else:
        print("  [X]  GeoNames 抓取失败")

    print("== 探活 GADM（小国测试 AND/LIE）==")
    import json
    for iso3 in ["AND", "LIE"]:
        url = f"{GADM_BASE}gadm41_{iso3}_1.json"
        data = fetcher.get(url, as_text=False)
        if data:
            try:
                feats = len(json.loads(data).get("features", []))
                print(f"  [OK] {iso3}_1: {feats} features")
            except Exception as e:
                print(f"  [X]  {iso3}_1: 解析失败 {e}")
        else:
            print(f"  [X]  {iso3}_1: 抓取失败")


def cmd_countries(args):
    n = pipeline.fetch_countries()
    if n:
        print(f"国家清单入库完成：{n} 个国家")
    else:
        print("国家清单抓取失败")
        sys.exit(1)


def cmd_country(args):
    count, reached = pipeline.run_country(args.country, max_level=args.max_level)
    print(f"{args.country}: 抓取 {count} 条，最深 level {reached}")


def cmd_names(args):
    """补全国家级三语名称（中/英/本地）+ 迁移 + 中国 name_zh 回填。"""
    db.init_db()  # 触发 migrate
    db.migrate()
    names = mledoze.collect()
    if not names:
        print("mledoze 抓取失败")
        sys.exit(1)
    db.upsert_country_names(names)
    # 中国 regions name_zh 回填（name 即中文）
    import sqlite3
    from config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    n = conn.execute(
        "UPDATE regions SET name_zh=name WHERE country='CN' AND name_zh IS NULL"
    ).rowcount
    conn.commit()
    conn.close()
    print(f"国家级三语名称更新 {len(names)} 国；中国 name_zh 回填 {n} 条")


def cmd_refill_local(args):
    """重抓 GADM 回填 name_local（命中磁盘缓存，快）。仅更新有缓存的层。"""
    db.init_db()
    pipeline.refill_name_local(max_level=args.max_level,
                               skip=GADM_SKIP_COUNTRIES)


def cmd_run(args):
    pipeline.run(countries=None, max_level=args.max_level, resume=args.resume,
                 workers=args.workers, skip=GADM_SKIP_COUNTRIES)
    cmd_status(args)


def cmd_status(args):
    try:
        countries = db.list_countries()
    except Exception as e:
        print(f"无法读取 countries 表（先运行 --countries）: {e}")
        return
    if not countries:
        print("countries 表为空，先运行: python build_world.py --countries")
        return
    from collections import Counter
    by_status = Counter(c.get("status") for c in countries)
    print(f"国家总数: {len(countries)}")
    for st, n in by_status.most_common():
        print(f"  {st}: {n}")
    # regions 总览
    try:
        counts, total = db.stats()
        print(f"\nregions 总记录: {total}")
        for lv in sorted(counts):
            print(f"  level {lv}: {counts[lv]}")
    except Exception:
        pass


def main():
    p = argparse.ArgumentParser(description="世界行政区划数据库构建器")
    p.add_argument("--probe", action="store_true", help="探活数据源")
    p.add_argument("--countries", action="store_true", help="仅抓取国家清单入库")
    p.add_argument("--country", help="抓取单国 ISO2（如 US/CN/FR）")
    p.add_argument("--names", action="store_true", help="补全国家级三语名称(中/英/本地)")
    p.add_argument("--refill-local", action="store_true", help="重抓 GADM 回填 name_local")
    p.add_argument("--max-level", type=int, default=WORLD_MAX_LEVEL,
                   help="最深下钻层级（默认 5）")
    p.add_argument("--resume", action="store_true", help="续抓，跳过已 done 的国家")
    p.add_argument("--workers", type=int, default=8, help="并发抓取国家数（默认 8）")
    p.add_argument("--status", action="store_true", help="查看抓取进度")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    setup_logging(args.verbose)

    if args.probe:
        cmd_probe(args)
    elif args.countries:
        cmd_countries(args)
    elif args.country:
        cmd_country(args)
    elif args.names:
        cmd_names(args)
    elif args.refill_local:
        cmd_refill_local(args)
    elif args.status:
        cmd_status(args)
    else:
        cmd_run(args)


if __name__ == "__main__":
    main()
