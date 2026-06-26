# -*- coding: utf-8 -*-
"""行政区划检索网页后端。

基于 Python 标准库 http.server，无额外依赖。
提供 JSON API + 静态文件服务。支持中/英/本地三种语言模式。

API：
  GET /api/i18n?lang=zh|en|local   界面文案字典 + 名称列选择规则
  GET /api/countries?lang=zh       国家列表（按语言显示名称）
  GET /api/levels?country=XX       某国层级数
  GET /api/children?country=XX&parent=<code>&lang=zh   某父级下的子区域
  GET /api/region?country=XX&code=<code>&lang=zh       某条记录详情+路径
  GET /api/search?country=XX&q=关键字&lang=zh          名称搜索（多列）
"""

import argparse
import json
import sqlite3
import sys
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

WEB_DIR = os.path.dirname(os.path.abspath(__file__))

# 语言 → 显示名优先列顺序（回退到 name / name_en）
LANG_COLS = {
    "zh": ["name_zh", "name", "name_en"],
    "en": ["name_en", "name"],
    "local": ["name_local", "name", "name_en"],
}

# 界面文案 i18n 字典
I18N = {
    "zh": {
        "title": "世界行政区划检索", "subtitle": "选择国家，逐级筛选行政区划",
        "select_country": "请选择国家", "loading": "加载中", "please_select": "请选择",
        "select_parent": "请选择上级", "level": "第 {n} 级", "search_placeholder": "名称搜索（所选国家内，未选国家则全球）",
        "search_btn": "搜索", "no_result": "无匹配结果", "found_n": "找到 {n} 条（最多显示100）",
        "no_subdiv": "该国无下级行政区划数据。", "n_countries": "共 {n} 个国家/地区",
        "f_path": "完整路径", "f_level": "层级", "f_code": "代码", "f_parent": "上级代码",
        "f_country": "国家", "f_source": "数据来源", "country_root": "(国家根)",
        "lang_label": "语言", "lang_zh": "中文", "lang_en": "English", "lang_local": "本地",
        "lang_hint": "中=中文 / EN=英文 / 本地=各国本地语言",
    },
    "en": {
        "title": "World Administrative Divisions", "subtitle": "Pick a country, drill down by level",
        "select_country": "Select country", "loading": "Loading", "please_select": "Select",
        "select_parent": "Select parent first", "level": "Level {n}", "search_placeholder": "Search by name (in selected country, or global)",
        "search_btn": "Search", "no_result": "No matches", "found_n": "Found {n} (max 100)",
        "no_subdiv": "No subdivisions for this country.", "n_countries": "{n} countries/regions",
        "f_path": "Path", "f_level": "Level", "f_code": "Code", "f_parent": "Parent code",
        "f_country": "Country", "f_source": "Source", "country_root": "(country root)",
        "lang_label": "Language", "lang_zh": "中文", "lang_en": "English", "lang_local": "Local",
        "lang_hint": "ZH=Chinese / EN=English / Local=native language",
    },
}
# local 模式复用 en 文案（仅名称列不同）
I18N["local"] = dict(I18N["en"])


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def display_name(row, lang):
    """按语言取显示名，回退 name/name_en。row 为 dict 或 sqlite3.Row。"""
    d = row if isinstance(row, dict) else dict(row)
    for col in LANG_COLS.get(lang, ["name"]):
        v = d.get(col)
        if v:
            return v
    return d.get("name") or d.get("name_en") or ""


def order_col(lang, table="regions"):
    """排序所用列。regions 统一按 name 排序（多数 name_zh/name_local 为空）；
    countries 按 name_en。"""
    if table == "countries":
        return "name_en"
    return "name"


def api_i18n(lang):
    lang = lang if lang in I18N else "zh"
    return {"lang": lang, "texts": I18N[lang]}


def api_countries(lang):
    lang = lang if lang in LANG_COLS else "zh"
    conn = db_conn()
    rows = conn.execute(
        "SELECT iso2, iso3, name_en, name_zh, name_local, max_level, status "
        "FROM countries ORDER BY name_en"
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["display"] = display_name(r, lang)
        out.append(d)
    return out


def api_levels(country):
    conn = db_conn()
    row = conn.execute(
        "SELECT MAX(level) AS ml FROM regions WHERE country=?", (country,)
    ).fetchone()
    conn.close()
    return {"country": country, "max_level": row["ml"] or 0}


def api_children(country, parent, lang):
    lang = lang if lang in LANG_COLS else "zh"
    conn = db_conn()
    if parent in (None, "", "root"):
        rows = conn.execute(
            f"SELECT code, name, name_zh, name_local, short_name, level, level_name, "
            f"parent_code, source FROM regions WHERE country=? AND level=1 "
            f"ORDER BY {order_col(lang)}",
            (country,),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT code, name, name_zh, name_local, short_name, level, level_name, "
            f"parent_code, source FROM regions WHERE country=? AND parent_code=? "
            f"ORDER BY {order_col(lang)}",
            (country, parent),
        ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["display"] = display_name(r, lang)
        out.append(d)
    return out


def api_region(country, code, lang):
    lang = lang if lang in LANG_COLS else "zh"
    conn = db_conn()
    row = conn.execute(
        "SELECT code, name, name_zh, name_local, short_name, level, level_name, "
        "parent_code, country, source FROM regions WHERE country=? AND code=?",
        (country, code)
    ).fetchone()
    if not row:
        return None
    chain = [dict(row)]
    pc = row["parent_code"]
    while pc:
        p = conn.execute(
            "SELECT code, name, name_zh, name_local, level, level_name, parent_code "
            "FROM regions WHERE country=? AND code=?", (country, pc)
        ).fetchone()
        if not p:
            break
        chain.append(dict(p))
        pc = p["parent_code"]
    chain.reverse()
    # 给每个 chain 项加 display（按当前语言）
    for c in chain:
        c["display"] = display_name(c, lang)
    # 国名
    crow = conn.execute(
        "SELECT name_en, name_zh, name_local FROM countries WHERE iso2=?",
        (country,)
    ).fetchone()
    conn.close()
    country_name = display_name(crow, lang) if crow else country
    return {"region": dict(row), "chain": chain,
            "country_name": country_name, "display": display_name(row, lang)}


def api_search(country, q, lang):
    lang = lang if lang in LANG_COLS else "zh"
    conn = db_conn()
    like = f"%{q}%"
    base = ("SELECT code, name, name_zh, name_local, short_name, level, level_name, "
            "parent_code, country, source FROM regions WHERE "
            "(name LIKE ? OR name_zh LIKE ? OR name_local LIKE ? OR short_name LIKE ?) ")
    params = [like, like, like, like]
    if country and country != "ALL":
        base += "AND country=? "
        params.append(country)
    base += f"ORDER BY country, level, {order_col(lang)} LIMIT 100"
    rows = conn.execute(base, params).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["display"] = display_name(r, lang)
        out.append(d)
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _static(self, path):
        if not path:
            path = "index.html"
        path = path.replace("\\", "/").lstrip("/")
        full = os.path.join(WEB_DIR, path)
        if not os.path.isfile(full) or ".." in path:
            self.send_error(404)
            return
        ext = os.path.splitext(path)[1].lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".png": "image/png", ".svg": "image/svg+xml",
        }.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        path = parsed.path
        lang = qs.get("lang", ["zh"])[0]

        if path.startswith("/api/"):
            try:
                if path == "/api/i18n":
                    return self._json(api_i18n(lang))
                if path == "/api/countries":
                    return self._json(api_countries(lang))
                if path == "/api/levels":
                    return self._json(api_levels(qs.get("country", [""])[0]))
                if path == "/api/children":
                    return self._json(api_children(
                        qs.get("country", [""])[0],
                        qs.get("parent", ["root"])[0], lang))
                if path == "/api/region":
                    r = api_region(qs.get("country", [""])[0],
                                   qs.get("code", [""])[0], lang)
                    return self._json(r if r else {"error": "not found"},
                                      200 if r else 404)
                if path == "/api/search":
                    return self._json(api_search(
                        qs.get("country", ["ALL"])[0],
                        qs.get("q", [""])[0], lang))
                return self._json({"error": "unknown api"}, 404)
            except Exception as e:
                return self._json({"error": str(e)}, 500)

        if path == "/" or path == "":
            return self._static("index.html")
        return self._static(path.lstrip("/"))


def main():
    p = argparse.ArgumentParser(description="行政区划检索网页")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--host", default="127.0.0.1")
    args = p.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"检索网页运行中: http://{args.host}:{args.port}")
    print(f"数据库: {DB_PATH}")
    print("Ctrl+C 退出")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
