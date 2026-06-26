# 🌐 世界行政区划数据库 · World Administrative Divisions

> 全球 252 国行政区划数据库（最多 **5 级**，**441,871 条**），含中国省/市/县/乡精确数据，支持中/英/本地三语级联检索。爬虫可复跑重建。

[![License: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](./LICENSE)
[![Data: GADM non-commercial](https://img.shields.io/badge/data-GADM%20non--commercial-orange.svg)](./DATA_LICENSES.md)
[![Countries](https://img.shields.io/badge/countries-252-green.svg)](#)
[![Records](https://img.shields.io/badge/records-441%2C871-green.svg)](#)

**在线演示 / Live Demo**：<https://ddduriannn.github.io/world-admin-divisions/>

---

## 与同类项目对比

| 项目 | 深度 | 中国 | 多语言 | Web UI | 可复现 | 许可 |
|---|---|---|---|---|---|---|
| **本项目** | **最多 5 级** | 省/市/县/乡 4 级 | **中/英/本地三语内置** | 级联检索 + 跨语搜索 | 爬虫可重建 | MIT(代码) / GADM 非商业(数据) |
| [dr5hn/countries-states-cities-database](https://github.com/dr5hn/countries-states-cities-database) (9.7k★) | 3 级 | 浅 | 独立 translations 包 | 导出工具 | 只发成品 | ODbL |
| [modood/Administrative-divisions-of-China](https://github.com/modood/Administrative-divisions-of-China) (20.8k★) | 5 级 | ✅ 精确 | 仅中文 | 无 | — | WTFPL |

> 本项目 = 全球 5 级深度 + 中国 4 级精确整合 + 三语内置 + 可浏览检索网页 + 可复跑爬虫。dr5hn 是"数据分发"，modood 是"中国单点"，本项目是"全球深层级 + 可交互 + 可重建"。

---

## 两大功能

### 1. 检索网页（GitHub Pages 在线版 + 本地 Python 版）

**在线版**（纯静态，无需后端）：<https://ddduriannn.github.io/world-admin-divisions/>

本地运行（Python 后端版，支持完整 API + 全球搜索）：
```bash
python web/app.py              # http://127.0.0.1:8000
```

- 第一个下拉选**国家**（全球 252 个，带国旗 emoji）。
- 选定后按该国层级数动态生成**级联下拉框**：中国=省→市→县→乡；美国=州→县；安道尔=教区…
- 末级显示完整路径（如 中国 › 河北省 › 石家庄市 › 井陉县）与代码、层级名、来源。
- 支持名称搜索（所选国家内或全球，跨中/英/本地多列匹配）。
- **三种语言模式**（右上角切换，记忆选择）：中文 / English / 本地（各国本地语言：日本=愛知県、德国=Deutschland、俄罗斯=Россия…）。
- 主题色板移植自 [Pico.css v2](https://github.com/picocss/pico) 深色主题。

### 2. 数据库

覆盖全球所有国家行政区划，统一存于 SQLite 单表 `regions`（`country`+`level`+`parent_code` 表达任意深度）。

| level | 含义 |
|---|---|
| 0 | 国家根 |
| 1..5 | 各国行政区划（省/州/县/乡…，因国而异） |

## 数据来源

| 数据 | 源 | 说明 |
|---|---|---|
| 国家清单 | GeoNames `countryInfo.txt`（dump，无 API 限额） | 252 国，ISO2/ISO3/名称 |
| 世界行政区划 | GADM `geodata.ucdavis.edu`（GeoJSON） | 全球最权威，最多 5 级，类型规范 |
| 中国行政区划 | modood_github（GitHub 结构化 JSON） | 4 级中文名 + 官方代码，比 GADM 更精确 |
| 国家级三语名称 | mledoze/countries（GitHub JSON） | 中/英/本地语言名，一次抓取 250 国 |
| 区划级本地名 | GADM `NL_NAME_N` | 约 78 国非拉丁文字国（日/俄/希腊/阿拉伯/韩等） |

## 关于 Google / 高德 / 百度地图的开放数据

这些平台的行政区划数据**确实有且更权威**，但**条款上禁止离线存储**，不能用来建本地数据库：

| 平台 | 行政区划能力 | 免费额度 | 关键限制 |
|---|---|---|---|
| **Google Maps** | Administrative Area Levels（最多 5 级）+ Geocoding | 每月 $200 免费额度（需绑卡 + API key） | **禁止批量下载/离线缓存**，仅限实时 API 展示 |
| **高德地图** | 行政区域查询 API（adcode 三级） | 个人每日数千次，需 key | **仅覆盖中国**，禁止缓存存储 |
| **百度地图** | 行政区划区域检索（district） | 免费配额有限，需 key | **仅覆盖中国**，禁止缓存 |

**结论**：它们是"服务"不是"数据库下载"——这正是本项目用 GADM（学术许可，可离线）+ GeoNames（CC BY 开放许可）+ mledoze（MIT）的价值：开放许可、可构建本地库、无 API 调用限制、无地域限制（全球而非仅中国）。

**关键技术点**：
- 国家统计局旧版 4 级 HTML 已 2024-10 永久下线，中国数据改用 modood 结构化源（`crawler/sources/modood_github.py`）。
- GADM 直连 `gadm.org` 失败，改用 `geodata.ucdavis.edu`；requests 默认 `trust_env=True` 受系统代理干扰致 SSL EOF，**设置 `session.trust_env=False` 后稳定**。
- GADM 单连接带宽低（~30KB/s），采用**多国并发抓取**（默认 8 线程）+ 磁盘缓存 + 断点续抓。
- 中国（CN）跳过 GADM，保留 modood 精确中文数据（`config.GADM_SKIP_COUNTRIES`）。

## 中国数据规模

| 级别 | 数量 |
|---|---|
| 省级 | 34 |
| 市级 | 342 |
| 县级 | 2,978 |
| 乡级 | 41,352 |
| **合计** | **44,706** |

## 数据库结构

SQLite 单库 `db/china_regions.db`，两表：

```sql
regions(code, name, short_name, level, level_name, parent_code, country, source, scraped_at)
-- level: 0=国家根 1..5=各国行政区划（因国而异）
-- parent_code: 上级 code，国家根为 NULL
-- UNIQUE(country, code): 多国天然隔离
countries(iso2, iso3, name_en, name_local, max_level, source, status, scraped_at)
-- 国家元数据 + 抓取进度追踪
```

## 使用

### 中国数据库
```bash
python build_db.py                 # 抓全 4 级，入库 + 导出 CSV/JSON
python build_db.py --probe         # 探活数据源
python build_db.py --max-level 3   # 只抓省/市/县
```

### 世界数据库
```bash
python build_world.py --probe      # 探活 GeoNames + GADM
python build_world.py --countries  # 抓国家清单入库（252 国）
python build_world.py              # 全量逐国抓取（最长 5 级，并发 8）
python build_world.py --resume     # 续抓，跳过已 done 的国家
python build_world.py --country US # 抓单国（测试）
python build_world.py --status     # 查看抓取进度
python build_world.py --workers 12 # 调整并发数
```

### 检索网页
```bash
python web/app.py                  # http://127.0.0.1:8000
python web/app.py --port 8080
```

> Windows 控制台建议设 `PYTHONUTF8=1` 以正确显示中文日志。

## 项目结构

```
build_db.py              中国数据库 CLI
build_world.py           世界数据库 CLI
config.py                数据源 URL、抓取参数、路径
db/schema.sql            建表 SQL（regions + countries）
crawler/
  base.py                BaseFetcher：重试/限速/编码探测/缓存/trust_env=False
  models.py              Region + Country 模型
  db.py                  SQLite 读写 + 导出 + 完整性校验 + 国家操作
  pipeline.py            中国编排（stats→modood）
  parser.py              国家统计局 4 级 HTML 解析器（备用）
  sources/               中国数据源
    modood_github.py       结构化 JSON 4 级
    stats_gov_cn.py        HTML 爬虫（探活式，官方已下线）
  world/                 世界数据源
    geonames.py            国家清单（GeoNames dump）
    gadm.py                各国行政区划（GADM GeoJSON）
    pipeline.py            并发编排 + 断点续抓
web/
  app.py                 检索网页后端（标准库 http.server，JSON API）
  index.html             级联下拉前端
  style.css
```

## 依赖

Python 3.10+，`requests`、`beautifulsoup4`、`lxml`。网页后端仅用 Python 标准库，无额外依赖。
