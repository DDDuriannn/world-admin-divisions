# -*- coding: utf-8 -*-
"""世界抓取编排：国家清单 → 逐国 GADM 下钻 → 入库。

支持断点续抓：每国完成即更新 countries.status，--resume 跳过已 done 的国家。
"""

import logging

from config import WORLD_MAX_LEVEL, LOG_DIR, GADM_CACHE_DIR
from crawler.base import BaseFetcher
from crawler import db
from crawler.models import now_iso
from crawler.world import geonames, gadm

log = logging.getLogger("crawler.world.pipeline")

PROGRESS_LOG = LOG_DIR / "world_progress.log"


def _log_progress(msg):
    with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
        f.write(f"{now_iso()}\t{msg}\n")


def fetch_countries(fetcher=None):
    """抓取国家清单入库（countries 表 + regions level=0 根）。"""
    fetcher = fetcher or BaseFetcher()
    countries, roots = geonames.collect(fetcher)
    if not countries:
        log.error("国家清单抓取失败")
        return 0
    db.init_db()
    db.upsert_countries(countries)
    db.upsert_regions(roots)
    _log_progress(f"国家清单 {len(countries)} 个入库")
    return len(countries)


def run_country(iso2, max_level=WORLD_MAX_LEVEL, fetcher=None):
    """抓取单国 GADM 行政区划入库，返回 (count, max_level_reached)。"""
    fetcher = fetcher or BaseFetcher(cache_dir=str(GADM_CACHE_DIR))

    countries = db.list_countries(only=[iso2])
    if not countries:
        log.error("国家 %s 不在清单中，先运行 --countries", iso2)
        return 0, 0
    c = countries[0]
    iso3 = c["iso3"]
    if not iso3:
        log.error("国家 %s 无 ISO3，跳过", iso2)
        db.set_country_status(iso2, "failed")
        return 0, 0

    log.info("抓取 %s (%s / %s)", c["name_en"], iso2, iso3)
    try:
        regions, reached = gadm.download_country(iso2, iso3, max_level, fetcher)
    except Exception as e:
        log.exception("抓取 %s 异常: %s", iso2, e)
        db.set_country_status(iso2, "failed")
        _log_progress(f"{iso2} FAILED {e}")
        return 0, 0

    if not regions:
        # 无下级行政区（如梵蒂冈/摩纳哥，level1 即 404）视为 done
        if reached == 0:
            db.set_country_status(iso2, "done", max_level=0)
            _log_progress(f"{iso2} DONE level=0 (no subdivisions)")
            return 0, 0
        db.set_country_status(iso2, "failed")
        _log_progress(f"{iso2} FAILED no regions")
        return 0, 0

    db.upsert_regions(regions)
    db.set_country_status(iso2, "done", max_level=reached)
    _log_progress(f"{iso2} DONE level={reached} count={len(regions)}")
    return len(regions), reached


def run(countries=None, max_level=WORLD_MAX_LEVEL, resume=True, fetcher=None,
        workers=8, skip=None):
    """全量逐国抓取（多国并发）。

    countries: 指定 ISO2 列表；None=全部。
    resume: True 时跳过 countries.status='done' 的国家。
    workers: 并发抓取的国家数（GADM 单连接带宽低，并发显著提速）。
    skip: 跳过的 ISO2 集合（如 CN 用 modood 精确数据，不抓 GADM）。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    skip = set(skip or [])
    db.init_db()
    all_countries = db.list_countries()
    if not all_countries:
        log.error("countries 表为空，先运行 --countries")
        return

    if countries:
        target = [c for c in all_countries if c["iso2"] in set(countries)]
    else:
        target = all_countries

    # 跳过 skip 集合（如 CN）与已完成国家
    todo = [c for c in target
            if c["iso2"] not in skip
            and not (resume and c.get("status") == "done")]
    skipped = len(target) - len(todo)
    total = len(target)
    log.info("待抓 %d 国（跳过已完成 %d），并发 %d", len(todo), skipped, workers)

    done = skipped
    failed = []
    completed = 0

    def _work(c):
        # 每线程独立 fetcher（独立 session，避免并发共享）
        f = BaseFetcher(cache_dir=str(GADM_CACHE_DIR), delay=(0.05, 0.15))
        return c, _scrape_only(c["iso2"], max_level, f)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_work, c): c for c in todo}
        for fut in as_completed(futures):
            c, (regions, reached) = fut.result()
            iso2 = c["iso2"]
            completed += 1
            if regions:
                # 串行入库（SQLite 写需串行）
                db.upsert_regions(regions)
                db.set_country_status(iso2, "done", max_level=reached)
                done += 1
                log.info("[%d/%d] %s OK level=%d count=%d",
                         completed, len(todo), iso2, reached, len(regions))
                _log_progress(f"{iso2} DONE level={reached} count={len(regions)}")
            elif reached == 0:
                # 无 4xx 触发的失败也可能是"该国无下级行政区"(如梵蒂冈/摩纳哥)
                # download_country 在 level1 即 EMPTY 时返回 ([], 0)，视为 done
                db.set_country_status(iso2, "done", max_level=0)
                done += 1
                log.info("[%d/%d] %s OK 无下级行政区", completed, len(todo), iso2)
                _log_progress(f"{iso2} DONE level=0 (no subdivisions)")
            else:
                db.set_country_status(iso2, "failed")
                failed.append(iso2)
                log.info("[%d/%d] %s FAILED", completed, len(todo), iso2)
                _log_progress(f"{iso2} FAILED")

    log.info("=" * 60)
    log.info("完成 %d/%d，失败 %d: %s", done, total, len(failed), failed)
    _log_progress(f"BATCH done={done}/{total} failed={failed}")


def _scrape_only(iso2, max_level, fetcher):
    """只抓取解析（不入库），返回 (regions, reached)。线程安全。"""
    countries = db.list_countries(only=[iso2])
    if not countries:
        return [], 0
    c = countries[0]
    iso3 = c["iso3"]
    if not iso3:
        return [], 0
    try:
        regions, reached = gadm.download_country(iso2, iso3, max_level, fetcher)
        return regions, reached
    except Exception as e:
        log.warning("%s 抓取异常: %s", iso2, e)
        return [], 0


def refill_name_local(max_level=WORLD_MAX_LEVEL, skip=None, workers=8):
    """重抓 GADM（命中磁盘缓存），仅回填 name_local 列。

    对已抓取的国家，用缓存重新解析拿到 name_local，UPDATE 到 regions 表。
    short_name 也一并修正（旧的 "English (Local)" 拼接回归为纯名）。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import sqlite3
    from config import DB_PATH

    skip = set(skip or [])
    all_countries = db.list_countries()
    todo = [c for c in all_countries
            if c["iso2"] not in skip and c.get("iso3")]
    log.info("回填 name_local: %d 国（命中 GADM 缓存）", len(todo))

    def _work(c):
        f = BaseFetcher(cache_dir=str(GADM_CACHE_DIR), delay=(0.02, 0.08))
        regions, _ = _scrape_only(c["iso2"], max_level, f)
        return c["iso2"], regions

    updated = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_work, c): c for c in todo}
        for fut in as_completed(futs):
            iso2, regions = fut.result()
            if not regions:
                continue
            conn = sqlite3.connect(DB_PATH)
            for r in regions:
                conn.execute(
                    "UPDATE regions SET name_local=?, short_name=? "
                    "WHERE country=? AND code=?",
                    (r.name_local, r.short_name, r.country, r.code),
                )
            conn.commit()
            conn.close()
            updated += 1
            log.info("回填 %s: %d 条", iso2, len(regions))
    log.info("name_local 回填完成，%d 国", updated)

