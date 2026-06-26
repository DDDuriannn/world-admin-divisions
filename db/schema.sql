-- 中国行政区划数据库 schema（单表自引用，便于世界扩展）
-- 层级：1省 2市 3县 4乡（乡镇/街道）
-- 不同国家层级数不同，用 level + parent_code 表达任意深度，新增国家只加 country 值。

CREATE TABLE IF NOT EXISTS regions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT,                       -- 官方行政区划代码（省2位/市4位/县6位/乡9位）
    name        TEXT NOT NULL,              -- 名称（英文罗马化；中国为中文）
    name_zh     TEXT,                       -- 中文名（仅中国有，其余回退 name）
    name_local  TEXT,                       -- 本地语言名（GADM NL_NAME，约78国非拉丁文字国）
    short_name  TEXT,                       -- 简称（去后缀，便于显示）
    level       INTEGER NOT NULL,           -- 1省 2市 3县 4乡
    level_name  TEXT,                       -- '省'|'直辖市'|'自治区'|'特别行政区'|'市'|'县'|'区'|'乡'|'镇'|'街道'|...
    parent_code TEXT,                       -- 上级 code（省级为 NULL）
    country     TEXT NOT NULL DEFAULT 'CN', -- 国家代码
    source      TEXT,                       -- 数据来源：modood_github | stats_gov_cn
    scraped_at  TEXT,                       -- 抓取时间（ISO 8601）
    UNIQUE(country, code)
);

CREATE INDEX IF NOT EXISTS idx_parent ON regions(parent_code);
CREATE INDEX IF NOT EXISTS idx_level  ON regions(level);
CREATE INDEX IF NOT EXISTS idx_name   ON regions(name);
CREATE INDEX IF NOT EXISTS idx_country_level ON regions(country, level);

-- 国家元数据表（世界扩展用）：国家清单、抓取状态、各国最大层级
-- regions 表用 level=0 行表示国家本身（code=ISO3, parent_code=NULL）作为各国行政树根。
CREATE TABLE IF NOT EXISTS countries (
    iso2        TEXT PRIMARY KEY,        -- 如 CN
    iso3        TEXT UNIQUE,             -- 如 CHN（GADM 文件名用 ISO3）
    name_en     TEXT NOT NULL,           -- 英文名
    name_zh     TEXT,                    -- 中文名（mledoze translations.zho）
    name_local  TEXT,                    -- 本地语言名（mledoze name.native）
    max_level   INTEGER,                 -- 该国行政区划最深层级
    source      TEXT,                    -- gadm | geonames
    status      TEXT DEFAULT 'pending',  -- pending|done|failed|partial
    scraped_at  TEXT
);
