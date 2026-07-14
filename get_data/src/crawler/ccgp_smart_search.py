# -*- coding: utf-8 -*-
"""Smart Web Fetch 搜索中国政府采购网采购公告并可继续抓详情。"""

from __future__ import annotations

import argparse
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

# 允许 `python src/crawler/ccgp_smart_search.py` 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import CRAWLER_OUTPUT_DIR
from crawler.smart_web_fetch import fetch_url, iter_fetch_plan
from utils.jsonl_helper import save_jsonl


SEARCH_BASE_URL = "https://search.ccgp.gov.cn/bxsearch"
DEFAULT_LIST_OUTPUT = CRAWLER_OUTPUT_DIR / "tenders_list_smart_fetch.jsonl"
DEFAULT_DETAIL_OUTPUT = CRAWLER_OUTPUT_DIR / "tenders_detail_smart_fetch.jsonl"


def build_ccgp_search_url(
    *,
    keyword: str,
    page: int = 1,
    searchtype: str = "2",
    dbselect: str = "bidx",
    bid_sort: str = "0",
    time_type: str = "4",
    start_time: str = "2025:10:14",
    end_time: str | None = None,
) -> str:
    """构造"采购公告 + 搜标题"搜索 URL。"""
    if not keyword or not keyword.strip():
        raise ValueError("keyword 不能为空")
    if page < 1:
        raise ValueError("page 必须 >= 1")

    params = [
        ("searchtype", str(searchtype)),
        ("page_index", str(page)),
        ("bidSort", str(bid_sort)),
        ("buyerName", ""),
        ("projectId", ""),
        ("pinMu", "0"),
        ("bidType", "0"),
        ("dbselect", str(dbselect)),
        ("kw", keyword.strip()),
        ("start_time", start_time or ""),
        ("end_time", end_time or datetime.now().strftime("%Y:%m:%d")),
        ("timeType", str(time_type)),
        ("displayZone", ""),
        ("zoneId", ""),
        ("pppStatus", "0"),
        ("agentName", ""),
    ]
    return SEARCH_BASE_URL + "?" + urlencode(params)


def extract_search_results(content: str, source_url: str = SEARCH_BASE_URL) -> list[dict[str, Any]]:
    """从 Reader 返回的 Markdown/HTML 中抽取公告列表。"""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for title, href in _iter_links(content or ""):
        title = _clean_text(title)
        if len(title) < 2:
            continue
        full_url = _normalize_url(href, source_url)
        if not _is_ccgp_notice_url(full_url) or full_url in seen:
            continue
        seen.add(full_url)
        rows.append({
            "project_name": title,
            "detail_url": full_url,
            "content": "",
        })
    return rows


def parse_smart_detail(content: str, url: str, *, fetch_method: str = "") -> dict[str, Any]:
    """解析 Smart Web Fetch 返回的详情 Markdown/HTML，输出兼容 tenders_detail 的字段。"""
    text = _reader_body(content or "")
    title = _extract_title(content or "", text)
    publish_date = _extract_publish_date(text)
    budget = _extract_budget(text)
    now = datetime.now().isoformat(timespec="seconds")

    return {
        "url": _canonical_ccgp_url(url),
        "detail_url": _canonical_ccgp_url(url),
        "title": title,
        "publish_date": publish_date,
        "announce_type": _infer_announce_type(title),
        "budget": budget,
        "content": _clean_detail_content(text),
        "attachments": [],
        "crawl_time": now,
        "fetch_method": fetch_method,
    }


def run_smart_search(
    *,
    keyword: str = "通信",
    search_url: str | None = None,
    pages: int = 1,
    crawl_details: bool = False,
    detail_limit: int | None = None,
    list_output: str | None = None,
    detail_output: str | None = None,
    timeout: int = 20,
    include_browser: bool = False,
    searchtype: str = "2",
    bid_sort: str = "0",
    time_type: str = "4",
    start_time: str = "2025:10:14",
    end_time: str | None = None,
    page_delay_min: float = 0.0,
    page_delay_max: float = 0.0,
    detail_delay_min: float = 0.0,
    detail_delay_max: float = 0.0,
    fetcher: Callable[..., Any] = fetch_url,
) -> dict[str, Any]:
    """执行 Smart Web Fetch 搜索列表，并可继续抓详情。"""
    list_path = Path(list_output) if list_output else DEFAULT_LIST_OUTPUT
    detail_path = Path(detail_output) if detail_output else DEFAULT_DETAIL_OUTPUT

    all_rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []

    for page in range(1, max(1, pages) + 1):
        page_url = _search_url_for_page(
            search_url,
            keyword=keyword,
            page=page,
            searchtype=searchtype,
            bid_sort=bid_sort,
            time_type=time_type,
            start_time=start_time,
            end_time=end_time,
        )
        page_rows, page_attempts = _fetch_search_page(
            page_url,
            timeout=timeout,
            include_browser=include_browser,
            fetcher=fetcher,
        )
        attempts.extend({"page": page, **attempt} for attempt in page_attempts)
        all_rows.extend(page_rows)
        if page < max(1, pages):
            _sleep_between(page_delay_min, page_delay_max)

    all_rows = _dedupe_list_rows(all_rows)
    if all_rows:
        save_jsonl(all_rows, str(list_path), append=False)

    detail_rows: list[dict[str, Any]] = []
    if crawl_details and all_rows:
        rows_to_detail = all_rows[: detail_limit or len(all_rows)]
        for idx, row in enumerate(rows_to_detail):
            detail_result = _fetch_first_useful(
                row["detail_url"],
                timeout=timeout,
                include_browser=include_browser,
                fetcher=fetcher,
                parser=lambda content: bool(_reader_body(content).strip()),
            )
            attempts.append({
                "page": None,
                "method": detail_result.method,
                "url": row["detail_url"],
                "success": detail_result.success,
                "status_code": detail_result.status_code,
                "item_count": 1 if detail_result.success else 0,
                "error": detail_result.error,
            })
            if detail_result.success:
                detail_rows.append(
                    parse_smart_detail(
                        detail_result.content,
                        row["detail_url"],
                        fetch_method=detail_result.method,
                    )
                )
            if idx < len(rows_to_detail) - 1:
                _sleep_between(detail_delay_min, detail_delay_max)
        if detail_rows:
            save_jsonl(detail_rows, str(detail_path), append=False)

    return {
        "success": bool(all_rows),
        "keyword": keyword,
        "search_url": search_url,
        "pages": pages,
        "list_count": len(all_rows),
        "detail_count": len(detail_rows),
        "list_output": str(list_path),
        "detail_output": str(detail_path) if crawl_details else None,
        "attempts": attempts,
    }


def _fetch_search_page(
    url: str,
    *,
    timeout: int,
    include_browser: bool,
    fetcher: Callable[..., Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    result = _fetch_first_useful(
        url,
        timeout=timeout,
        include_browser=include_browser,
        fetcher=fetcher,
        parser=lambda content: extract_search_results(content, source_url=url),
    )
    rows = extract_search_results(result.content, source_url=url) if result.success else []
    stamped = []
    captured_at = datetime.now().isoformat(timespec="seconds")
    for row in rows:
        stamped.append({
            **row,
            "source_url": url,
            "fetch_method": result.method,
            "captured_at": captured_at,
        })
    return stamped, [{
        "method": result.method,
        "url": url,
        "success": result.success,
        "status_code": result.status_code,
        "item_count": len(stamped),
        "error": result.error,
    }]


def _search_url_for_page(
    search_url: str | None,
    *,
    keyword: str,
    page: int,
    searchtype: str = "2",
    bid_sort: str = "0",
    time_type: str = "4",
    start_time: str = "2025:10:14",
    end_time: str | None = None,
) -> str:
    if not search_url:
        return build_ccgp_search_url(
            keyword=keyword,
            page=page,
            searchtype=searchtype,
            bid_sort=bid_sort,
            time_type=time_type,
            start_time=start_time,
            end_time=end_time,
        )
    if page == 1:
        return search_url

    parsed = urlparse(search_url)
    params = parse_qsl(parsed.query, keep_blank_values=True)
    replaced = False
    updated = []
    for key, value in params:
        if key == "page_index":
            updated.append((key, str(page)))
            replaced = True
        else:
            updated.append((key, value))
    if not replaced:
        updated.append(("page_index", str(page)))
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urlencode(updated), ""))


def _sleep_between(delay_min: float, delay_max: float) -> None:
    lo = max(0.0, float(delay_min or 0.0))
    hi = max(lo, float(delay_max or 0.0))
    if hi > 0:
        time.sleep(random.uniform(lo, hi))


def _fetch_first_useful(
    url: str,
    *,
    timeout: int,
    include_browser: bool,
    fetcher: Callable[..., Any],
    parser: Callable[[str], Any],
):
    last_result = None
    for step in iter_fetch_plan(url, include_browser=include_browser):
        result = fetcher(url, timeout=timeout, include_browser=False, methods=[step["method"]])
        last_result = result
        parsed = parser(result.content) if result.success else None
        if parsed:
            return result
    return last_result if last_result is not None else fetcher(url, timeout=timeout)


def _iter_links(content: str):
    md_pattern = re.compile(r"\[([^\]]{2,240})\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
    for title, href in md_pattern.findall(content):
        yield title, href

    html_pattern = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
    for href, raw_title in html_pattern.findall(content):
        yield re.sub(r"<[^>]+>", " ", raw_title), href


def _reader_body(content: str) -> str:
    marker = "Markdown Content:"
    if marker in content:
        return content.split(marker, 1)[1].strip()
    return content.strip()


def _extract_title(raw: str, body: str) -> str:
    title_match = re.search(r"^\s*Title:\s*(.+)$", raw, re.M)
    if title_match:
        title = _clean_text(title_match.group(1))
        if title and title.lower() not in {"converted content", "markdown content"}:
            return title
    h1_match = re.search(r"^\s*#\s+(.+)$", body, re.M)
    if h1_match:
        return _clean_text(h1_match.group(1))
    for line in body.splitlines():
        clean = _clean_text(line.strip().lstrip("#").strip())
        if _looks_like_notice_title(clean):
            return clean
    first = next((_clean_text(line.strip()) for line in body.splitlines() if _clean_text(line.strip())), "")
    return _clean_text(first.lstrip("#").strip())


def _extract_publish_date(text: str) -> str:
    patterns = [
        r"发布时间[:：]\s*(\d{4})年(\d{1,2})月(\d{1,2})日(?:\s*(\d{1,2}):(\d{1,2}))?",
        r"发布日期[:：]\s*(\d{4})年(\d{1,2})月(\d{1,2})日(?:\s*(\d{1,2}):(\d{1,2}))?",
        r"(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{1,2})",
        r"(\d{4})-(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}):(\d{1,2}))?",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if not m:
            continue
        year, month, day, hour, minute = m.groups(default="")
        date = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        if hour and minute:
            return f"{date} {int(hour):02d}:{int(minute):02d}"
        return date
    return ""


def _extract_budget(text: str) -> str:
    m = re.search(r"预算金额[:：]\s*([^\n\r]+?万元)", text)
    if m:
        return _clean_text(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?\s*万元)", text)
    return _clean_text(m.group(1)) if m else ""


def _infer_announce_type(title: str) -> str:
    if "中标" in title:
        return "中标公告"
    if "成交" in title:
        return "成交公告"
    if "更正" in title or "变更" in title:
        return "更正公告"
    if "磋商" in title:
        return "竞争性磋商"
    if "谈判" in title:
        return "竞争性谈判"
    if "招标" in title:
        return "招标公告"
    return ""


def _clean_detail_content(text: str) -> str:
    lines = []
    for line in text.splitlines():
        clean = _clean_text(line.strip().lstrip("#").strip())
        if clean:
            lines.append(clean)
    return "\n".join(lines)


def _looks_like_notice_title(value: str) -> bool:
    if not value:
        return False
    if value.startswith(("当前位置", "服务热线", "公告概要", "相关公告")):
        return False
    if value.startswith(("*", "|", "[", "©")):
        return False
    if "公告信息" in value or "政府采购信息网络发布媒体" in value:
        return False
    title_words = (
        "招标公告",
        "中标公告",
        "中标公示",
        "成交公告",
        "成交结果",
        "采购公告",
        "更正公告",
        "结果公告",
        "终止公告",
        "废标公告",
        "流标公告",
        "竞争性磋商公告",
        "竞争性谈判公告",
        "询价公告",
        "资格预审公告",
    )
    return any(word in value for word in title_words)


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def _normalize_url(href: str, source_url: str) -> str:
    href = (href or "").strip()
    if href.startswith(("javascript:", "mailto:", "#")):
        return ""
    return urljoin(source_url, href)


def _is_ccgp_notice_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.netloc.endswith("ccgp.gov.cn") and "/cggg/" in parsed.path


def _canonical_ccgp_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    scheme = parsed.scheme or "http"
    if host in ("ccgp.gov.cn", "www.ccgp.gov.cn"):
        host = "www.ccgp.gov.cn"
        scheme = "http"
    netloc = host or parsed.netloc
    path = parsed.path.rstrip("/") if parsed.path != "/" else parsed.path
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def _dedupe_list_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    out = []
    for row in rows:
        key = _canonical_ccgp_url(row.get("detail_url", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Smart Web Fetch 搜索 CCGP 采购公告并抓取详情")
    parser.add_argument("--keyword", default="通信", help="搜索关键词，默认：通信")
    parser.add_argument("--search-url", default=None, help="直接使用已构造好的 CCGP 搜索 URL")
    parser.add_argument("--pages", type=int, default=1, help="抓取搜索结果页数")
    parser.add_argument("--timeout", type=int, default=20, help="单层抓取超时秒数")
    parser.add_argument("--crawl-details", action="store_true", help="继续抓取详情页")
    parser.add_argument("--detail-limit", type=int, default=None, help="最多抓取详情数")
    parser.add_argument("--include-browser", action="store_true", help="启用 Playwright 兜底层")
    parser.add_argument("--list-output", default=str(DEFAULT_LIST_OUTPUT), help="列表输出 JSONL")
    parser.add_argument("--detail-output", default=str(DEFAULT_DETAIL_OUTPUT), help="详情输出 JSONL")
    parser.add_argument("--print-items", action="store_true", help="打印列表结果")
    args = parser.parse_args()

    report = run_smart_search(
        keyword=args.keyword,
        search_url=args.search_url,
        pages=args.pages,
        crawl_details=args.crawl_details,
        detail_limit=args.detail_limit,
        list_output=args.list_output,
        detail_output=args.detail_output,
        timeout=args.timeout,
        include_browser=args.include_browser,
    )
    print(
        f"[SMART_SEARCH] keyword={report['keyword']} pages={report['pages']} "
        f"list={report['list_count']} detail={report['detail_count']} "
        f"list_output={report['list_output']} detail_output={report['detail_output']}"
    )
    if args.print_items:
        for attempt in report["attempts"]:
            print(
                f"[ATTEMPT] page={attempt['page']} method={attempt['method']} "
                f"success={attempt['success']} items={attempt['item_count']} url={attempt['url']}"
            )


if __name__ == "__main__":
    main()
