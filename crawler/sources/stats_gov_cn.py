# -*- coding: utf-8 -*-
"""国家统计局 4 级 HTML 爬虫适配器（备用 / 探活式）。

按 stats.gov.cn 标准页面结构递归下钻：index.html → 省 → 市 → 县 → 乡。
启动时对 STATS_CANDIDATE_BASES 逐个探活，取首个返回 200 且含 provincetr 的源。

注意：国家统计局自 2024-10 起永久下线该数据，官方候选当前均不可达。
若日后官方恢复或出现复刻该结构的镜像，加入 STATS_CANDIDATE_BASES 即可启用，
无需改动解析逻辑。当前主力数据由 modood_github 提供。
"""

import logging

from config import STATS_CANDIDATE_BASES, MAX_LEVEL, COUNTRY
from crawler.base import BaseFetcher
from crawler.parser import parse_level_html
from crawler.models import Region

log = logging.getLogger("crawler.stats")


def probe(fetcher=None):
    """探活候选源，返回 (base_url, index_html) 或 None。"""
    fetcher = fetcher or BaseFetcher()
    for base in STATS_CANDIDATE_BASES:
        index_url = base.rstrip("/") + "/index.html"
        html = fetcher.get(index_url, as_text=True)
        if html and ("provincetr" in html or "citytr" in html):
            log.info("探活命中: %s", index_url)
            return base, html
        log.info("探活未命中: %s", index_url)
    return None


def collect(fetcher=None, max_level=MAX_LEVEL):
    """从探活命中的源递归抓取 4 级数据。源不可用时返回空列表。"""
    fetcher = fetcher or BaseFetcher()
    hit = probe(fetcher)
    if not hit:
        log.warning("无可用 stats HTML 源，跳过（使用 modood 主源）")
        return []

    base, index_html = hit
    regions = []

    # 省
    provs, prov_links = parse_level_html(index_html, base, parent_code=None)
    regions.extend(_with_country(provs))
    log.info("省级 %d 条", len(provs))
    if max_level < 2:
        return regions

    # 市
    for child_url, parent_code in prov_links:
        html = fetcher.get(child_url, as_text=True)
        if not html:
            continue
        items, child_links = parse_level_html(html, base, parent_code=parent_code)
        regions.extend(_with_country(items))
        if max_level < 3:
            continue
        # 县
        for cu, cparent in child_links:
            chtml = fetcher.get(cu, as_text=True)
            if not chtml:
                continue
            citems, cclinks = parse_level_html(chtml, base, parent_code=cparent)
            regions.extend(_with_country(citems))
            if max_level < 4:
                continue
            # 乡
            for tu, tparent in cclinks:
                thtml = fetcher.get(tu, as_text=True)
                if not thtml:
                    continue
                titems, _ = parse_level_html(thtml, base, parent_code=tparent)
                regions.extend(_with_country(titems))
                log.debug("乡级 +%d (%s)", len(titems), tparent)

    return regions


def _with_country(regions):
    for r in regions:
        r.country = COUNTRY
    return regions
