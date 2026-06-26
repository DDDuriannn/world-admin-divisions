# -*- coding: utf-8 -*-
"""国家统计局标准 4 级 HTML 表格解析器（备用爬虫）。

页面结构（统计用区划代码和城乡划分代码）：
  index.html        <tr class="provincetr"><td><a href="11.html">北京市</a>...
  {省码}.html        <tr class="citytr"><td><a href="11/1101.html">110100<br>市辖区</a>...
  {省码}/{市码}.html <tr class="countytr">...<a href="11/1101/110101.html">110101<br>东城区</a>
  .../{县码}.html    <tr class="towntr">...<a href="...">110101001<br>东华门街道</a>

每行 class 末尾为 tr：provincetr / citytr / countytr / towntr。
单元格里 <a> 的文本形如 "代码<br>名称"，或代码与名称分属两个 <td>/<a>。
无下级时该行无 <a>，代码与名称直接在 <td> 文本中。

官方源自 2024-10 起永久下线，本解析器用于仍复刻该结构的镜像源。
"""

import re
from bs4 import BeautifulSoup

from .models import (
    Region, province_level_name, short_name_of, town_level_name, now_iso,
)

# 各级 class 名 → (level, 子页面是否可继续下钻)
LEVEL_CLASS = {
    "provincetr": (1, True),
    "citytr": (2, True),
    "countytr": (3, True),
    "towntr": (4, False),
}

_BR = re.compile(r"<br\s*/?>", re.I)


def _clean(text: str) -> str:
    return re.sub(r"\s+", "", text or "").replace("　", "")


def parse_level_html(html: str, base_url: str, parent_code=None,
                     source="stats_gov_cn"):
    """解析某一级页面，返回 (regions, child_links)。

    regions: 该页面的 Region 列表。
    child_links: [(child_url, code), ...] 下一级待抓取链接（仅对非叶子级）。
    """
    soup = BeautifulSoup(html, "lxml")
    # 找出本页使用的级别 class（一页只有一种）
    level = None
    drillable = False
    for cls, (lv, drill) in LEVEL_CLASS.items():
        if soup.find("tr", class_=cls):
            level, drillable = lv, drill
            break
    if level is None:
        return [], []

    rows = soup.find_all("tr", class_=lambda c: c and c.endswith("tr")
                         and c in LEVEL_CLASS)
    regions = []
    child_links = []
    stamp = now_iso()

    for tr in rows:
        anchors = tr.find_all("a")
        if anchors:
            # 第一个 <a> 含代码（与名称同行用 <br> 分隔，或代码单独）
            first = anchors[0]
            href = first.get("href", "")
            # 把 <br> 换成换行再取文本
            raw = _BR.sub("\n", first.decode_contents())
            parts = [p for p in (s.strip() for s in re.split(r"[\n]+", raw)) if p]
            if len(parts) >= 2:
                code, name = parts[0], parts[1]
            else:
                # 代码与名称在不同 <a>：provincetr 只有名称，代码从 href 推
                code = parts[0] if parts else ""
                name = anchors[1].get_text(strip=True) if len(anchors) > 1 else code
            if level == 1:
                # provincetr 的 <a> 文本就是省名，无代码；从 href 文件名取
                name = first.get_text(strip=True)
                code = re.sub(r"\.html?$", "", href.split("/")[-1])
        else:
            # 叶子行：代码/名称在 <td> 文本
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            code = _clean(tds[0].get_text())
            name = _clean(tds[1].get_text())
            href = None

        if not code or not name:
            continue

        level_name = _level_name(level, name)
        regions.append(Region(
            code=code,
            name=name,
            level=level,
            level_name=level_name,
            parent_code=parent_code,
            short_name=short_name_of(name, level),
            source=source,
            scraped_at=stamp,
        ))
        if drillable and href:
            child_url = base_url.rstrip("/") + "/" + href.lstrip("/")
            # 子页面父级 code = 当前 code
            child_links.append((child_url, code))

    return regions, child_links


def _level_name(level: int, name: str) -> str:
    if level == 1:
        return province_level_name(name)
    if level == 4:
        return town_level_name(name)
    if level == 2:
        for s in ["自治州"]:
            if name.endswith(s):
                return s
        for s in ["地区", "盟"]:
            if name.endswith(s):
                return s
        return "市"
    if level == 3:
        for s in ["自治县", "林区", "旗"]:
            if name.endswith(s):
                return s
        for s in ["区", "县", "市"]:
            if name.endswith(s):
                return s
        return "县"
    return ""
