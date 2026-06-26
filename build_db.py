# -*- coding: utf-8 -*-
"""中国行政区划数据库构建入口。

用法：
  python build_db.py                 # 自动选源，抓全 4 级，入库 + 导出
  python build_db.py --probe         # 仅探活数据源，不写库
  python build_db.py --max-level 3   # 只抓省/市/县（快速验证）
  python build_db.py --source modood # 指定源：stats | modood
  python build_db.py --no-hk-mo-tw   # 不补充港澳台省级
  python build_db.py --export-only   # 仅从已有 DB 导出 CSV/JSON
"""

import argparse
import logging
import sys

# Windows 控制台默认 GBK，强制 UTF-8 以正确显示中文与符号
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import MAX_LEVEL
from crawler.base import BaseFetcher
from crawler.sources import stats_gov_cn, modood_github
from crawler import db, pipeline


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_probe(args):
    """探活 stats HTML 候选源 + 验证 modood 源可达。"""
    fetcher = BaseFetcher()
    print("== 探活 stats HTML 候选源 ==")
    hit = stats_gov_cn.probe(fetcher)
    if hit:
        print(f"  [OK] stats HTML 源可用: {hit[0]}")
    else:
        print("  [X]  stats HTML 源均不可用（官方自 2024-10 永久下线）")

    print("== 探活 modood 结构化源 ==")
    import json
    from config import MODOOD_BASE, MODOOD_FILES
    ok = True
    for lv, fn in MODOOD_FILES.items():
        text = fetcher.get(MODOOD_BASE + fn, as_text=True, encoding="utf-8")
        if text:
            try:
                n = len(json.loads(text))
                print(f"  [OK] {fn}: {n} 条 (level {lv})")
            except Exception as e:
                ok = False
                print(f"  [X]  {fn}: 解析失败 {e}")
        else:
            ok = False
            print(f"  [X]  {fn}: 抓取失败")
    if ok:
        print("  => 推荐源: modood_github（含省/市/县/乡全 4 级）")


def cmd_build(args):
    regions, source = pipeline.run(
        max_level=args.max_level,
        force_source=args.source,
        include_hk_mo_tw=not args.no_hk_mo_tw,
    )
    if not regions:
        print("构建失败：未抓取到数据。")
        sys.exit(1)

    db.export()
    print("\n========== 构建完成 ==========")
    print(f"数据来源: {source}")
    print(f"抓取层级: 1..{args.max_level}")
    counts, total = db.stats()
    level_cn = {1: "省", 2: "市", 3: "县", 4: "乡"}
    for lv in sorted(counts):
        print(f"  {level_cn.get(lv, lv)}级: {counts[lv]:>6} 条")
    print(f"  合计:   {total:>6} 条")

    bad, issues = db.integrity_check()
    if bad:
        print("\n⚠ 完整性问题:")
        for i in issues:
            print(f"  - {i}")
    else:
        print("\n✓ 完整性校验通过：无孤儿节点，层级关系自洽")


def cmd_export(args):
    db.export()
    counts, total = db.stats()
    print(f"导出完成，合计 {total} 条")


def main():
    p = argparse.ArgumentParser(description="中国行政区划数据库构建器")
    p.add_argument("--probe", action="store_true", help="仅探活数据源，不写库")
    p.add_argument("--max-level", type=int, default=MAX_LEVEL,
                   help="抓取到哪一级：1省 2市 3县 4乡（默认 4）")
    p.add_argument("--source", choices=["stats", "modood"], default=None,
                   help="指定数据源；默认自动（优先 stats 爬虫，回退 modood）")
    p.add_argument("--no-hk-mo-tw", action="store_true",
                   help="不补充港澳台省级记录")
    p.add_argument("--export-only", action="store_true",
                   help="仅从已有数据库导出 CSV/JSON")
    p.add_argument("-v", "--verbose", action="store_true", help="调试日志")
    args = p.parse_args()

    setup_logging(args.verbose)

    if args.probe:
        cmd_probe(args)
    elif args.export_only:
        cmd_export(args)
    else:
        cmd_build(args)


if __name__ == "__main__":
    main()
