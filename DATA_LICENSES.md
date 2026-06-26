# 数据来源与许可

本项目的**代码**采用 MIT 许可（见 [LICENSE](./LICENSE)）。

但**数据**来自多个来源，各受不同许可约束。使用数据时请遵守下表，**尤其是 GADM 的非商业限制**。

| 数据 | 来源 | 许可 | 商用? | 说明 |
|---|---|---|---|---|
| 世界行政区划（非中国） | [GADM](https://gadm.org) (`geodata.ucdavis.edu`) | [GADM License](https://gadm.org/license.html) — 仅限学术/非商业用途，禁止商业再分发 | ❌ 否 | 全球最权威、最多 5 级。本项目约 39.7 万条区划来自 GADM |
| 国家清单 + 元数据 | [GeoNames](https://www.geonames.org) (`countryInfo.txt`) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)（需署名） | ✅ 是 | 252 国 ISO2/ISO3/名称 |
| 中国行政区划 | [modood/Administrative-divisions-of-China](https://github.com/modood/Administrative-divisions-of-China) | WTFPL | ✅ 是 | 省/市/县/乡 4 级 44,706 条精确中文数据 + 官方代码 |
| 国家级三语名称 | [mledoze/countries](https://github.com/mledoze/countries) | MIT | ✅ 是 | 中/英/本地语言国名 |
| 区划级本地语言名 | GADM `NL_NAME_N` | 同 GADM（非商业） | ❌ 否 | 约 78 国非拉丁文字名 |

## 关键约束

- ⚠️ **GADM 数据非商业**：`docs/data/` 中除中国（`CN.json`）外的各国区划数据派生自 GADM，**不得用于商业用途**。若需商用，请改用 GeoNames（CC BY）等开放许可数据源重新抓取。
- **署名要求**：使用 GeoNames 数据需署名 GeoNames；使用本项目需署名各原始数据源。
- 中国数据（`CN.json`，源自 modood，WTFPL）与国家级名称（mledoze，MIT）可自由商用。

## 重新生成数据

如需规避 GADM 非商业限制或更新数据，可运行爬虫从各源重新抓取：

```bash
python build_world.py --countries   # 抓国家清单（GeoNames）
python build_world.py               # 逐国抓取（GADM，并发 8）
python build_db.py                  # 中国 4 级（modood）
python build_static.py              # 导出 docs/data/ 静态 JSON
```
