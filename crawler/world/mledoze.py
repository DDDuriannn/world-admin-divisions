# -*- coding: utf-8 -*-
"""mledoze/countries 国家级三语名称抓取器。

数据源：https://raw.githubusercontent.com/mledoze/countries/master/countries.json
一次抓取 250 国，同时提供：
  name.common          英文名
  translations.zho     中文名
  name.native          本地语言名（取首个语言变体）

更新 countries 表的 name_en/name_zh/name_local，并同步 regions 表 level=0 国家根。
"""

import logging

from crawler.base import BaseFetcher

log = logging.getLogger("crawler.mledoze")

MLEDOZE_URL = (
    "https://raw.githubusercontent.com/mledoze/countries/master/countries.json"
)


def collect(fetcher=None):
    """抓取并返回 [(iso2, name_en, name_zh, name_local), ...]。"""
    fetcher = fetcher or BaseFetcher()
    data = fetcher.get(MLEDOZE_URL, as_text=False)
    if not data:
        log.error("无法抓取 mledoze: %s", MLEDOZE_URL)
        return []
    import json
    try:
        countries = json.loads(data)
    except json.JSONDecodeError as e:
        log.error("mledoze JSON 解析失败: %s", e)
        return []

    names = []
    for c in countries:
        iso2 = c.get("cca2")
        if not iso2:
            continue
        name_en = (c.get("name") or {}).get("common") or ""
        # 中文名
        zh = ((c.get("translations") or {}).get("zho") or {}).get("common")
        # 本地语言名：取 native 的首个变体
        native = c.get("name", {}).get("native") or {}
        name_local = None
        if native:
            first = list(native.values())[0]
            name_local = first.get("common") or first.get("official")
        names.append((iso2, name_en, zh, name_local))

    log.info("mledoze 国家级三语名称 %d 条", len(names))
    return names
