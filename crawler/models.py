# -*- coding: utf-8 -*-
"""统一的行政区划数据模型。所有数据源适配器输出 Region 列表。"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone


def now_iso() -> str:
    """当前 UTC 时间，ISO 8601。脚本环境无时区依赖。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Region:
    code: str              # 官方行政区划代码
    name: str              # 名称（英文罗马化；中国为中文）
    level: int             # 1省 2市 3县 4乡（世界：1..5 各国层级）
    level_name: str        # 层级名称（省/市/县/乡/镇/街道/State/County...）
    parent_code: str = None  # 上级 code，省级为 None
    short_name: str = None   # 简称
    name_zh: str = None      # 中文名（仅中国）
    name_local: str = None   # 本地语言名（GADM NL_NAME）
    country: str = "CN"
    source: str = None
    scraped_at: str = None

    def to_row(self):
        d = asdict(self)
        d.pop("country", None)  # country 由入库层统一注入
        return d


@dataclass
class Country:
    iso2: str              # ISO 2 位代码，主键（如 CN）
    iso3: str              # ISO 3 位代码（如 CHN，GADM 文件名用此）
    name_en: str           # 英文名
    name_zh: str = None     # 中文名（mledoze translations.zho）
    name_local: str = None  # 本地名（mledoze name.native）
    max_level: int = None   # 该国行政区划最深层级
    source: str = None
    status: str = "pending"
    scraped_at: str = None


# ---- 层级名称与简称规范化 ----

# 省级后缀 → 层级名
PROVINCE_SUFFIXES = [
    ("自治区", "自治区"),
    ("特别行政区", "特别行政区"),
    ("直辖市", "直辖市"),
    ("省", "省"),
    ("市", "直辖市"),  # 直辖市名称以"市"结尾，如北京市
]


def province_level_name(name: str) -> str:
    for suffix, lname in PROVINCE_SUFFIXES:
        if name.endswith(suffix):
            # "北京市"判定为直辖市
            if suffix == "市" and name.endswith("市"):
                return "直辖市"
            return lname
    return "省"


def short_name_of(name: str, level: int) -> str:
    """去掉常见后缀得到简称。"""
    if not name:
        return name
    suffixes = {
        1: ["自治区", "特别行政区", "直辖市", "省", "市"],
        2: ["自治州", "地区", "盟", "市"],
        3: ["自治县", "林区", "旗", "区", "县", "市"],
        4: ["民族乡", "民族苏木", "苏木", "街道办事处", "街道", "镇", "乡", "区"],
    }.get(level, [])
    for s in suffixes:
        if name.endswith(s) and len(name) > len(s):
            return name[: -len(s)]
    return name


# 乡级 level_name 细分
def town_level_name(name: str) -> str:
    for s in ["街道办事处", "街道"]:
        if name.endswith(s):
            return "街道"
    for s in ["民族苏木"]:
        if name.endswith(s):
            return "民族苏木"
    for s in ["苏木"]:
        if name.endswith(s):
            return "苏木"
    for s in ["民族乡"]:
        if name.endswith(s):
            return "民族乡"
    for s in ["镇"]:
        if name.endswith(s):
            return "镇"
    for s in ["乡"]:
        if name.endswith(s):
            return "乡"
    return "乡级"
