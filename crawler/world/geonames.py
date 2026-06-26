# -*- coding: utf-8 -*-
"""GeoNames 国家清单抓取器。

数据源：https://download.geonames.org/export/dump/countryInfo.txt
格式：tab 分隔，行首 # 为注释。字段顺序：
  ISO2 ISO3 ISO_numeric FIPS name capital area population continent ...
本模块只取 ISO2/ISO3/name（英文名），写入 countries 表，并为每国生成
regions 表 level=0 的国家根记录（code=ISO3, parent_code=NULL）。
"""

import logging

from config import GEONAMES_COUNTRYINFO_URL
from crawler.base import BaseFetcher
from crawler.models import Country, Region, now_iso

log = logging.getLogger("crawler.geonames")

# countryInfo.txt 列顺序（前 5 列我们用）
# 0 ISO  1 ISO3  2 ISO_Numeric  3 FIPS  4 Country  5 Capital ...
_COL_ISO2 = 0
_COL_ISO3 = 1
_COL_NAME = 4


def collect(fetcher=None):
    """抓取国家清单，返回 (countries, root_regions)。

    countries: Country 列表（写入 countries 表）
    root_regions: Region 列表（level=0 国家根，写入 regions 表）
    """
    fetcher = fetcher or BaseFetcher()
    text = fetcher.get(GEONAMES_COUNTRYINFO_URL, as_text=True, encoding="utf-8")
    if not text:
        log.error("无法抓取国家清单: %s", GEONAMES_COUNTRYINFO_URL)
        return [], []

    countries = []
    root_regions = []
    stamp = now_iso()

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) <= _COL_NAME:
            continue
        iso2 = parts[_COL_ISO2].strip()
        iso3 = parts[_COL_ISO3].strip()
        name = parts[_COL_NAME].strip()
        if not iso2 or not iso3 or not name:
            continue
        # 跳过纯数字/异常代码
        if not iso2.isalpha() or not iso3.isalpha():
            continue

        countries.append(Country(
            iso2=iso2, iso3=iso3, name_en=name,
            name_local=None, max_level=None,
            source="geonames", status="pending", scraped_at=stamp,
        ))
        # regions 表 level=0 国家根
        root_regions.append(Region(
            code=iso3, name=name, level=0,
            level_name="Country",
            parent_code=None,
            short_name=name,
            country=iso2,
            source="geonames",
            scraped_at=stamp,
        ))

    log.info("国家清单 %d 个国家", len(countries))
    return countries, root_regions
