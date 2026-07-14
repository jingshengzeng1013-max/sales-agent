# -*- coding: utf-8 -*-
"""基于 Smart Web Fetch 技术栈采集中国政府采购网首页。"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

# 允许 `python src/crawler/ccgp_smart_fetch.py` 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import CRAWLER_OUTPUT_DIR
from crawler.smart_web_fetch import fetch_url, iter_fetch_plan
from utils.jsonl_helper import save_jsonl


CCGP_HOME_URL = "https://www.ccgp.gov.cn/"


def extract_ccgp_home_items(content: str, source_url: str = CCGP_HOME_URL) -> list[dict[str, str]]:
    """从 HTML 或 Markdown 中抽取 ccgp.gov.cn 链接。"""
    text = content or ""
    items = []
    seen: set[str] = set()

    for title, href in _iter_html_links(text):
        _append_item(items, seen, title, href, source_url)

    for title, href in _iter_markdown_links(text):
        _append_item(items, seen, title, href, source_url)

    return items


def crawl_ccgp_home(
    *,
    url: str = CCGP_HOME_URL,
    output_path: str | None = None,
    max_items: int = 80,
    timeout: int = 20,
    include_browser: bool = False,
) -> dict[str, Any]:
    """抓取 CCGP 首页并保存链接数据。"""
    captured_at = datetime.now().isoformat(timespec="seconds")
    attempts = []
    result = None
    items: list[dict[str, str]] = []

    for step in iter_fetch_plan(url, include_browser=include_browser):
        result = fetch_url(url, timeout=timeout, include_browser=False, methods=[step["method"]])
        parsed_items = extract_ccgp_home_items(result.content, source_url=url)[:max_items] if result.success else []
        attempts.append({
            "method": step["method"],
            "success": result.success,
            "status_code": result.status_code,
            "item_count": len(parsed_items),
            "error": result.error,
        })
        if parsed_items:
            items = parsed_items
            break

    if result is None:
        result = fetch_url(url, timeout=timeout, include_browser=include_browser)

    rows = [
        {
            **item,
            "source_url": url,
            "fetch_method": result.method,
            "captured_at": captured_at,
        }
        for item in items
    ]

    if output_path and rows:
        save_jsonl(rows, output_path, append=False)

    return {
        "success": result.success,
        "method": result.method,
        "status_code": result.status_code,
        "content_type": result.content_type,
        "elapsed_ms": result.elapsed_ms,
        "items": rows,
        "item_count": len(rows),
        "attempts": attempts,
        "output_path": output_path,
        "error": result.error,
    }


def _iter_html_links(content: str):
    pattern = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
    for href, raw_title in pattern.findall(content):
        title = _clean_text(re.sub(r"<[^>]+>", " ", raw_title))
        yield title, href


def _iter_markdown_links(content: str):
    pattern = re.compile(r"\[([^\]]{2,160})\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
    for title, href in pattern.findall(content):
        yield _clean_text(title), href


def _append_item(items: list[dict[str, str]], seen: set[str], title: str, href: str, source_url: str) -> None:
    title = _clean_text(title)
    if len(title) < 2:
        return
    if re.fullmatch(r"[》\"')\s]+", title):
        return

    href = (href or "").strip()
    if not href or href.startswith(("javascript:", "mailto:", "#")):
        return

    full_url = urljoin(source_url, href)
    parsed = urlparse(full_url)
    if not parsed.netloc.endswith("ccgp.gov.cn"):
        return

    normalized_url = parsed._replace(fragment="").geturl()
    if normalized_url in seen:
        return

    seen.add(normalized_url)
    items.append({
        "title": title,
        "url": normalized_url,
    })


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def main() -> None:
    parser = argparse.ArgumentParser(description="Smart Web Fetch 采集 CCGP 首页")
    parser.add_argument("--url", default=CCGP_HOME_URL, help=f"目标 URL（默认：{CCGP_HOME_URL}）")
    parser.add_argument(
        "--output",
        default=str(CRAWLER_OUTPUT_DIR / "ccgp_home_smart_fetch.jsonl"),
        help="输出 JSONL 路径",
    )
    parser.add_argument("--max-items", type=int, default=80, help="最多保存链接数")
    parser.add_argument("--timeout", type=int, default=20, help="单层抓取超时秒数")
    parser.add_argument("--include-browser", action="store_true", help="启用 Playwright 动态渲染兜底")
    parser.add_argument("--print-items", action="store_true", help="打印抽取结果")
    args = parser.parse_args()

    report = crawl_ccgp_home(
        url=args.url,
        output_path=args.output,
        max_items=args.max_items,
        timeout=args.timeout,
        include_browser=args.include_browser,
    )
    print(
        f"[SMART_FETCH] success={report['success']} method={report['method']} "
        f"items={report['item_count']} output={report['output_path']}"
    )
    if report["error"]:
        print(f"[SMART_FETCH] error={report['error']}")
    if args.print_items:
        for idx, item in enumerate(report["items"], 1):
            print(f"{idx}. {item['title']} -> {item['url']}")


if __name__ == "__main__":
    main()
