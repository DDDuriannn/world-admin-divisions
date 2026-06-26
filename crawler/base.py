# -*- coding: utf-8 -*-
"""基础抓取层：重试、限速、编码探测、磁盘缓存、失败记录。

所有数据源适配器都基于 BaseFetcher，统一抓取行为，便于世界扩展时复用。
"""

import time
import random
import logging
from pathlib import Path
from urllib.parse import urljoin

import requests

from config import HEADERS, REQUEST_DELAY, MAX_RETRIES, REQUEST_TIMEOUT, LOG_DIR

log = logging.getLogger("crawler")

# 失败 URL 记录文件，支持断点续抓 / 事后排查
FAILED_LOG = LOG_DIR / "failed.txt"


class BaseFetcher:
    """带重试、限速、缓存的 HTTP 抓取器。"""

    def __init__(self, cache_dir=None, headers=None, delay=None):
        self.session = requests.Session()
        # 禁用环境代理读取：GADM 等源在系统代理存在时会出现 SSL EOF，
        # 直接连接更稳定（本机直连外网正常）。
        self.session.trust_env = False
        self.session.headers.update(headers or HEADERS)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        # 可覆盖请求间隔（默认 config.REQUEST_DELAY）
        self.delay = delay or REQUEST_DELAY

    # ---- 限速 ----
    def _sleep(self):
        lo, hi = self.delay
        time.sleep(random.uniform(lo, hi))

    # ---- 缓存键 ----
    def _cache_path(self, url):
        # 用 URL 末段作缓存文件名，避免特殊字符
        safe = url.replace("://", "_").replace("/", "_").replace("?", "_")
        return self.cache_dir / safe

    def get(self, url, *, as_text=True, encoding=None, use_cache=True):
        """发起 GET，返回文本或字节。失败重试并记录到 failed.txt。"""
        cache_path = self._cache_path(url) if self.cache_dir else None
        if use_cache and cache_path and cache_path.exists():
            data = cache_path.read_bytes()
            if as_text:
                return self._decode(data, encoding)
            return data

        last_err = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                self._sleep()
                resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.content
                    if cache_path:
                        cache_path.write_bytes(data)
                    if as_text:
                        return self._decode(data, encoding or resp.encoding)
                    return data
                # 4xx 客户端错误（除 429 限流）不重试，立即失败
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    log.info("HTTP %s on %s（不重试）", resp.status_code, url)
                    self._record_failure(url, f"HTTP {resp.status_code}")
                    return None
                log.warning("HTTP %s on %s (attempt %d/%d)",
                            resp.status_code, url, attempt, MAX_RETRIES)
            except requests.RequestException as e:
                last_err = e
                log.warning("ERR %s on %s (attempt %d/%d): %s",
                            type(e).__name__, url, attempt, MAX_RETRIES, e)
            # 指数退避
            time.sleep(1.2 ** attempt)

        # 全部失败，记录
        self._record_failure(url, last_err)
        return None

    @staticmethod
    def _decode(data, encoding):
        """自动探测编码：优先给定 > meta charset > utf-8 > gb18030。"""
        if encoding:
            try:
                return data.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                pass
        # 探测 meta charset
        head = data[:2048].decode("ascii", errors="ignore").lower()
        meta_enc = None
        if "charset=" in head:
            try:
                meta_enc = head.split("charset=", 1)[1].split('"')[0].split("'")[0].split(";")[0].strip()
            except Exception:
                meta_enc = None
        for enc in [meta_enc, "utf-8", "gb18030"]:
            if not enc:
                continue
            try:
                return data.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return data.decode("utf-8", errors="ignore")

    @staticmethod
    def _record_failure(url, err):
        with open(FAILED_LOG, "a", encoding="utf-8") as f:
            f.write(f"{url}\t{err}\n")

    @staticmethod
    def urljoin(base, href):
        return urljoin(base, href)
