# -*- coding: utf-8 -*-
"""抓取编排：探活 stats HTML 爬虫 → 命中则用之，否则回退 modood 结构化源 → 入库。"""

import logging

from config import MAX_LEVEL
from crawler.base import BaseFetcher
from crawler.sources import stats_gov_cn, modood_github
from crawler import db

log = logging.getLogger("crawler.pipeline")


def run(max_level=MAX_LEVEL, force_source=None, include_hk_mo_tw=True):
    """执行抓取并入库。

    force_source: 'stats' | 'modood' | None（自动：优先 stats 爬虫，回退 modood）
    返回 (regions, source_name)。
    """
    fetcher = BaseFetcher(cache_dir="logs/cache")
    regions = []

    if force_source == "modood":
        regions = modood_github.collect(fetcher, max_level=max_level,
                                        include_hk_mo_tw=include_hk_mo_tw)
        source = "modood_github"
    elif force_source == "stats":
        regions = stats_gov_cn.collect(fetcher, max_level=max_level)
        source = "stats_gov_cn"
    else:
        # 自动：先试 stats HTML 爬虫（探活）
        hit = stats_gov_cn.probe(fetcher)
        if hit:
            regions = stats_gov_cn.collect(fetcher, max_level=max_level)
            source = "stats_gov_cn"
        else:
            log.info("stats HTML 源不可用，回退 modood 结构化源")
            regions = modood_github.collect(fetcher, max_level=max_level,
                                            include_hk_mo_tw=include_hk_mo_tw)
            source = "modood_github"

    if not regions:
        log.error("未抓取到任何数据")
        return [], source

    log.info("共抓取 %d 条记录（来源: %s）", len(regions), source)
    db.init_db()
    db.upsert_regions(regions)
    return regions, source
