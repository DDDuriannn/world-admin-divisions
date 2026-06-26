# -*- coding: utf-8 -*-
"""世界行政区划抓取模块。

国家清单来自 GeoNames dump；各国行政区划来自 GADM。
统一映射到 regions 表（level 0=国家根，1..N=各国层级）与 countries 元数据表。
"""
