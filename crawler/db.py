# -*- coding: utf-8 -*-
"""SQLite 写入与 CSV/JSON 导出。"""

import csv
import json
import sqlite3
import logging
from pathlib import Path

from config import DB_PATH, SCHEMA_PATH, DATA_DIR, COUNTRY
from crawler.models import Region

log = logging.getLogger("crawler.db")

COLUMNS = [
    "code", "name", "name_zh", "name_local", "short_name", "level", "level_name",
    "parent_code", "country", "source", "scraped_at",
]

COUNTRY_COLUMNS = [
    "iso2", "iso3", "name_en", "name_zh", "name_local", "max_level",
    "source", "status", "scraped_at",
]


def _existing_columns(conn, table):
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def migrate(db_path=DB_PATH):
    """为旧库补充新列（幂等）。新增 name_zh / name_local。"""
    conn = sqlite3.connect(db_path)
    for table, cols in [
        ("regions", ["name_zh TEXT", "name_local TEXT"]),
        ("countries", ["name_zh TEXT"]),
    ]:
        existing = _existing_columns(conn, table)
        if not existing:
            continue  # 表不存在，由 init_db 创建
        for col_def in cols:
            col_name = col_def.split()[0]
            if col_name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
                log.info("迁移: %s 加列 %s", table, col_name)
    # 中国 regions 的 name（中文）回填到 name_zh
    conn.execute(
        "UPDATE regions SET name_zh=name WHERE country='CN' AND name_zh IS NULL"
    )
    # countries level=0 根记录同步
    conn.commit()
    conn.close()


def init_db(db_path=DB_PATH):
    """（重新）创建表结构 + 迁移旧库新列。"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = sqlite3.connect(db_path)
    conn.executescript(schema)
    conn.commit()
    conn.close()
    migrate(db_path)
    log.info("数据库初始化: %s", db_path)


def upsert_regions(regions, db_path=DB_PATH):
    """批量 upsert Region 列表（按 country+code 去重）。"""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    cur = conn.cursor()
    sql = """
        INSERT INTO regions (code, name, name_zh, name_local, short_name,
                             level, level_name, parent_code, country, source, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(country, code) DO UPDATE SET
            name=excluded.name,
            name_zh=COALESCE(excluded.name_zh, regions.name_zh),
            name_local=COALESCE(excluded.name_local, regions.name_local),
            short_name=excluded.short_name,
            level=excluded.level,
            level_name=excluded.level_name,
            parent_code=excluded.parent_code,
            source=excluded.source,
            scraped_at=excluded.scraped_at
    """
    rows = []
    for r in regions:
        rows.append((
            r.code, r.name, getattr(r, "name_zh", None),
            getattr(r, "name_local", None), r.short_name,
            r.level, r.level_name, r.parent_code, r.country or COUNTRY,
            r.source, r.scraped_at,
        ))
    cur.executemany(sql, rows)
    conn.commit()
    conn.close()
    log.info("写入/更新 %d 条记录", len(rows))


def upsert_country_names(names, db_path=DB_PATH):
    """更新国家级三语名称。names: [(iso2, name_en, name_zh, name_local), ...]"""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    cur = conn.cursor()
    cur.executemany(
        """UPDATE countries SET name_en=?, name_zh=?, name_local=?
           WHERE iso2=?""",
        [(en, zh, loc, iso2) for (iso2, en, zh, loc) in names],
    )
    # 同步 regions 表 level=0 国家根记录的三语名
    cur.executemany(
        """UPDATE regions SET name=?, name_zh=?, name_local=?
           WHERE country=? AND level=0""",
        [(en, zh, loc, iso2) for (iso2, en, zh, loc) in names],
    )
    conn.commit()
    conn.close()
    log.info("更新 %d 国三语名称", len(names))


def upsert_countries(countries, db_path=DB_PATH):
    """批量 upsert Country 列表到 countries 表。"""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    cur = conn.cursor()
    sql = """
        INSERT INTO countries (iso2, iso3, name_en, name_zh, name_local, max_level,
                               source, status, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(iso2) DO UPDATE SET
            iso3=excluded.iso3,
            name_en=excluded.name_en,
            name_zh=COALESCE(excluded.name_zh, countries.name_zh),
            name_local=COALESCE(excluded.name_local, countries.name_local),
            max_level=COALESCE(excluded.max_level, countries.max_level),
            source=excluded.source,
            status=excluded.status,
            scraped_at=excluded.scraped_at
    """
    rows = [
        (c.iso2, c.iso3, c.name_en, getattr(c, "name_zh", None),
         getattr(c, "name_local", None), c.max_level,
         c.source, c.status, c.scraped_at)
        for c in countries
    ]
    cur.executemany(sql, rows)
    conn.commit()
    conn.close()
    log.info("写入/更新 %d 个国家", len(rows))


def set_country_status(iso2, status, max_level=None, db_path=DB_PATH):
    """更新单国抓取状态。"""
    conn = sqlite3.connect(db_path)
    if max_level is not None:
        conn.execute(
            "UPDATE countries SET status=?, max_level=?, scraped_at=? WHERE iso2=?",
            (status, max_level, now_iso_for_db(), iso2),
        )
    else:
        conn.execute(
            "UPDATE countries SET status=?, scraped_at=? WHERE iso2=?",
            (status, now_iso_for_db(), iso2),
        )
    conn.commit()
    conn.close()


def now_iso_for_db():
    from crawler.models import now_iso
    return now_iso()


def list_countries(db_path=DB_PATH, only=None):
    """返回国家列表。only: 可选 ISO2 集合过滤。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    if only:
        qs = ",".join("?" * len(only))
        rows = conn.execute(
            f"SELECT * FROM countries WHERE iso2 IN ({qs}) ORDER BY name_en",
            list(only),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM countries ORDER BY name_en"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def country_max_level(iso2, db_path=DB_PATH):
    """返回某国当前 regions 表中最大层级（用于网页渲染下拉数）。"""
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT MAX(level) FROM regions WHERE country=?", (iso2,)
    ).fetchone()
    conn.close()
    return row[0] or 0


def export(db_path=DB_PATH):
    """导出全表为 CSV 与 JSON，便于检查与迁移。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT code, name, short_name, level, level_name, parent_code, "
        "country, source, scraped_at FROM regions ORDER BY level, code"
    ).fetchall()
    conn.close()

    # CSV
    csv_path = DATA_DIR / "regions.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([r[c] for c in COLUMNS])

    # JSON
    json_path = DATA_DIR / "regions.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([dict(r) for r in rows], f, ensure_ascii=False, indent=2)

    log.info("导出 CSV: %s (%d 行)", csv_path, len(rows))
    log.info("导出 JSON: %s", json_path)


def stats(db_path=DB_PATH):
    """返回各级数量统计。"""
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "SELECT level, COUNT(*) FROM regions GROUP BY level ORDER BY level"
    )
    counts = {lv: n for lv, n in cur.fetchall()}
    total = sum(counts.values())
    conn.close()
    return counts, total


def integrity_check(db_path=DB_PATH):
    """完整性校验：返回 (孤儿数, 问题列表)。"""
    conn = sqlite3.connect(db_path)
    # 孤儿：parent_code 非空但父记录不存在
    orphans = conn.execute("""
        SELECT COUNT(*) FROM regions a
        WHERE a.parent_code IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM regions b
                          WHERE b.country=a.country AND b.code=a.parent_code)
    """).fetchone()[0]
    # 各级 parent_code 为空应为省级(level=1)
    bad_root = conn.execute("""
        SELECT COUNT(*) FROM regions
        WHERE parent_code IS NULL AND level != 1
    """).fetchone()[0]
    conn.close()
    issues = []
    if orphans:
        issues.append(f"孤儿节点 {orphans} 条（parent_code 指向不存在的记录）")
    if bad_root:
        issues.append(f"非省级但 parent_code 为空 {bad_root} 条")
    return orphans + bad_root, issues
