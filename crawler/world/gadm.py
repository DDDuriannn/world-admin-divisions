# -*- coding: utf-8 -*-
"""GADM 行政区划抓取器（世界主力源）。

数据源：https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_{ISO3}_{N}.json
  N=1..5 为该国第 N 级行政区。某级 404 表示该国无该级，停止下钻。

GeoJSON feature.properties 直接包含各级字段：
  GID_0(ISO3) COUNTRY GID_1..GID_N NAME_1..NAME_N TYPE_1..TYPE_N
  NL_NAME_1..N(本地名，常 "NA") ENGTYPE_1..N
每个 level N 的 feature 同时带 GID_{N-1}，可直接取作 parent_code，无需推导。

映射到 regions 表：
  code=GID_N, name=NAME_N, level=N, level_name=TYPE_N,
  parent_code=GID_{N-1}（level1 的 parent=GID_0=ISO3 国家根 code）,
  country=ISO2, source='gadm'
"""

import json
import logging

from config import GADM_BASE, GADM_CACHE_DIR, WORLD_MAX_LEVEL
from crawler.base import BaseFetcher
from crawler.models import Region, now_iso

log = logging.getLogger("crawler.gadm")

_NA = "NA"

# fetch_level 返回标记：国家无该级行政区（404，正常现象，非失败）
EMPTY = "EMPTY"


def _gadm_url(iso3, level):
    return f"{GADM_BASE}gadm41_{iso3}_{level}.json"


def fetch_level(fetcher, iso3, level):
    """下载并解析某国某级。

    返回：
      list[Region] — 该级有数据
      EMPTY        — 该级 404（国家无此级行政区，正常）
      None         — 网络/解析错误（真失败）
    """
    url = _gadm_url(iso3, level)
    data = fetcher.get(url, as_text=False)  # 字节
    if data is None:
        # BaseFetcher 对 4xx(非429) 不重试直接返回 None，需区分 404 vs 网络错误。
        # 通过 failed.txt 判断：404 会被记录为 "HTTP 404"。
        # 简化：直接探测状态码。
        try:
            r = fetcher.session.get(url, timeout=20)
            if r.status_code == 404:
                return EMPTY
        except Exception:
            pass
        return None
    try:
        gj = json.loads(data)
    except json.JSONDecodeError as e:
        log.error("JSON 解析失败 %s: %s", url, e)
        return None
    if gj.get("type") != "FeatureCollection":
        log.warning("%s 非 FeatureCollection", url)
        return None

    feats = gj.get("features", [])
    regions = []
    stamp = now_iso()
    iso3_actual = iso3
    for f in feats:
        p = f.get("properties") or {}
        gid_n = p.get(f"GID_{level}")
        name_n = p.get(f"NAME_{level}")
        if not gid_n or not name_n:
            continue
        gid_0 = p.get("GID_0") or iso3
        iso3_actual = gid_0
        # parent: level1 -> GID_0(国家根 ISO3); levelN>=2 -> GID_{N-1}
        if level == 1:
            parent = gid_0
        else:
            parent = p.get(f"GID_{level - 1}") or gid_0
        type_n = p.get(f"TYPE_{level}") or ""
        # 本地语言名：取该级 NL_NAME_N（非 NA），独立存 name_local 列
        nl = p.get(f"NL_NAME_{level}")
        name_local = None
        if nl and nl != _NA and nl != name_n:
            name_local = nl

        regions.append(Region(
            code=gid_n,
            name=name_n,
            level=level,
            level_name=type_n,
            parent_code=parent,
            short_name=name_n,          # 简称回归名称语义（GADM 无后缀可去）
            name_local=name_local,      # 本地语言名独立列
            country="",  # 由 pipeline 按 ISO2 注入
            source="gadm",
            scraped_at=stamp,
        ))
    return regions


def download_country(iso2, iso3, max_level=WORLD_MAX_LEVEL, fetcher=None):
    """下载某国 1..max_level 全部层级，返回 (regions, max_level_reached)。

    遇到某级不存在(返回 None)即停止更深层级。
    """
    # GADM 服务器带宽是瓶颈，无需大礼貌延迟；并发抓取时用小延迟
    fetcher = fetcher or BaseFetcher(cache_dir=str(GADM_CACHE_DIR),
                                     delay=(0.05, 0.15))
    all_regions = []
    reached = 0
    for level in range(1, max_level + 1):
        log.info("  %s level %d ...", iso3, level)
        regions = fetch_level(fetcher, iso3, level)
        if regions is EMPTY:
            log.info("  %s level %d 不存在(404)，停止下钻", iso3, level)
            break
        if regions is None:
            log.warning("  %s level %d 抓取失败，停止下钻", iso3, level)
            break
        if not regions:
            log.info("  %s level %d 无数据", iso3, level)
            break
        # 注入 country=ISO2
        for r in regions:
            r.country = iso2
        all_regions.extend(regions)
        reached = level
        log.info("  %s level %d: %d 条", iso3, level, len(regions))
    return all_regions, reached
