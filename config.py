# -*- coding: utf-8 -*-
"""全局配置：数据源 URL、抓取参数、数据库与导出路径。"""

from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parent

# ---- 输出路径 ----
DB_PATH = ROOT / "db" / "china_regions.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"

# ---- 国家 ----
COUNTRY = "CN"

# ---- 世界数据源 ----
# GeoNames 预打包 dump（无 API 限额）：国家清单
GEONAMES_COUNTRYINFO_URL = (
    "https://download.geonames.org/export/dump/countryInfo.txt"
)
# GADM 行政区划（按国家、按层级分文件，GeoJSON）
GADM_BASE = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/"
# GADM 最深下钻层级（1..5）
WORLD_MAX_LEVEL = 5
# GADM 缓存目录
GADM_CACHE_DIR = LOG_DIR / "cache" / "gadm"
# 跳过 GADM 抓取的国家（已有更精确的专属数据源）
# CN：使用 modood_github 4 级中文数据，不抓 GADM 避免冗余
GADM_SKIP_COUNTRIES = {"CN"}

# ---- 抓取参数 ----
# 请求间隔（秒），带抖动以礼貌抓取
REQUEST_DELAY = (0.2, 0.6)
# 最大重试次数
MAX_RETRIES = 4
# 单请求超时（秒）
REQUEST_TIMEOUT = 30
# 并发上限（乡镇级数据量大，默认串行+小延迟）
MAX_WORKERS = 4
# 抓取到哪一级：1省 2市 3县 4乡
MAX_LEVEL = 4

# 浏览器请求头
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}

# ---- 数据源：modood 结构化 JSON（主力，含省/市/县/乡全 4 级 + 代码）----
# 该数据集源自国家统计局《统计用区划代码和城乡划分代码》下线前数据。
# 注：国家统计局自 2024-10 起不再发布该数据，官方可浏览 HTML 已永久失效。
MODOOD_BASE = (
    "https://raw.githubusercontent.com/modood/"
    "Administrative-divisions-of-China/master/dist/"
)
MODOOD_FILES = {
    1: "provinces.json",  # 省
    2: "cities.json",     # 市
    3: "areas.json",      # 县
    4: "streets.json",    # 乡/镇/街道
}

# ---- 数据源：国家统计局 4 级 HTML（备用爬虫，探活式；官方源当前已下线）----
# 探活时按顺序尝试以下候选 BASE（含官方历史路径与可能的镜像），取首个
# 返回 200 且含 provincetr 结构者。
STATS_CANDIDATE_BASES = [
    "https://www.stats.gov.cn/sj/tjbz/tjyqhdmhcxhfdm/2023/",
    "https://www.stats.gov.cn/sj/tjbz/tjyqhdmhcxhfdm/2022/",
    "http://www.stats.gov.cn/sj/tjbz/tjyqhdmhcxhfdm/2023/",
]
