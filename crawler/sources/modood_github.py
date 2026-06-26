# -*- coding: utf-8 -*-
"""modood/Administrative-divisions-of-China 结构化数据源适配器（主力）。

通过 HTTP 抓取 GitHub raw 上的分级别 JSON 文件，覆盖省/市/县/乡全 4 级，且每条
带官方行政区划代码与父级代码，可直接映射到统一 schema。

数据来源说明：
  该数据集源自国家统计局《统计用区划代码和城乡划分代码》（截止 2023-06-30 数据）。
  国家统计局自 2024-10 起不再发布该数据，官方可浏览 HTML 已永久失效，故本数据集
  是当前最完整、可靠、含代码的 4 级数据来源。

JSON 字段：
  provinces: [{code, name}]
  cities:    [{code, name, provinceCode}]
  areas:     [{code, name, cityCode, provinceCode}]
  streets:   [{code, name, areaCode, cityCode, provinceCode}]
"""

import json
import logging

from config import MODOOD_BASE, MODOOD_FILES, MAX_LEVEL, COUNTRY
from crawler.base import BaseFetcher
from crawler.models import (
    Region, province_level_name, short_name_of, town_level_name, now_iso,
)

log = logging.getLogger("crawler.modood")

# 港澳台：统计局区划代码体系未含，按 GB/T 2260 习惯补充为省级（无下级）
HK_MO_TW = [
    ("71", "台湾省"),
    ("81", "香港特别行政区"),
    ("82", "澳门特别行政区"),
]


def collect(fetcher=None, max_level=MAX_LEVEL, include_hk_mo_tw=True):
    """抓取并返回 Region 列表（省/市/县/乡，按 max_level 截断）。"""
    fetcher = fetcher or BaseFetcher()
    regions = []
    stamp = now_iso()

    # ---- 省 ----
    provs = _fetch_json(fetcher, MODOOD_FILES[1])
    if not provs:
        raise RuntimeError("无法抓取省级数据，主源不可用")
    for p in provs:
        name = p["name"]
        regions.append(Region(
            code=p["code"], name=name, level=1,
            level_name=province_level_name(name),
            parent_code=None,
            short_name=short_name_of(name, 1),
            country=COUNTRY, source="modood_github", scraped_at=stamp,
        ))
    log.info("省级 %d 条", len(regions))

    if include_hk_mo_tw:
        for code, name in HK_MO_TW:
            regions.append(Region(
                code=code, name=name, level=1,
                level_name=province_level_name(name),
                parent_code=None,
                short_name=short_name_of(name, 1),
                country=COUNTRY, source="supplemented", scraped_at=stamp,
            ))
        log.info("补充港澳台省级 3 条")

    if max_level < 2:
        return regions

    # ---- 市 ----
    cities = _fetch_json(fetcher, MODOOD_FILES[2]) or []
    for c in cities:
        name = c["name"]
        regions.append(Region(
            code=c["code"], name=name, level=2,
            level_name=_city_level_name(name),
            parent_code=c.get("provinceCode"),
            short_name=short_name_of(name, 2),
            country=COUNTRY, source="modood_github", scraped_at=stamp,
        ))
    log.info("市级 %d 条", len(cities))

    if max_level < 3:
        return regions

    # ---- 县 ----
    areas = _fetch_json(fetcher, MODOOD_FILES[3]) or []
    for a in areas:
        name = a["name"]
        regions.append(Region(
            code=a["code"], name=name, level=3,
            level_name=_county_level_name(name),
            parent_code=a.get("cityCode"),
            short_name=short_name_of(name, 3),
            country=COUNTRY, source="modood_github", scraped_at=stamp,
        ))
    log.info("县级 %d 条", len(areas))

    if max_level < 4:
        return regions

    # ---- 乡 ----
    streets = _fetch_json(fetcher, MODOOD_FILES[4]) or []
    for s in streets:
        name = s["name"]
        regions.append(Region(
            code=s["code"], name=name, level=4,
            level_name=town_level_name(name),
            parent_code=s.get("areaCode"),
            short_name=short_name_of(name, 4),
            country=COUNTRY, source="modood_github", scraped_at=stamp,
        ))
    log.info("乡级 %d 条", len(streets))

    return regions


def _fetch_json(fetcher, filename):
    url = MODOOD_BASE + filename
    text = fetcher.get(url, as_text=True, encoding="utf-8")
    if not text:
        log.error("抓取失败: %s", url)
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        log.error("JSON 解析失败 %s: %s", url, e)
        return None


def _city_level_name(name):
    for s in ["自治州", "地区", "盟"]:
        if name.endswith(s):
            return s
    return "市"


def _county_level_name(name):
    for s in ["自治县", "林区", "旗", "自治旗"]:
        if name.endswith(s):
            return s
    for s in ["区", "县", "市"]:
        if name.endswith(s):
            return s
    return "县"
