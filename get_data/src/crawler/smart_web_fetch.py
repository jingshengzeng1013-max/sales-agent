# -*- coding: utf-8 -*-
"""Smart Web Fetch 采集栈。

基于虾评 Skill「Smart Web Fetch」公开描述实现 5 层降级：
markdown.new -> defuddle.md -> r.jina.ai -> Scrapling -> Playwright。
第三方 Reader 服务会接收目标 URL；仅用于公开网页采集。
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import asdict, dataclass
from typing import Any, Iterable

import requests


READER_METHODS = ("markdown.new", "defuddle.md", "r.jina.ai")
FALLBACK_METHODS = ("scrapling", "playwright")
DEFAULT_METHODS = READER_METHODS + FALLBACK_METHODS


@dataclass
class SmartFetchResult:
    success: bool
    method: str
    url: str
    final_url: str
    status_code: int | None
    content_type: str
    content: str
    elapsed_ms: int
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_reader_url(method: str, target_url: str) -> str:
    """构造第三方 Reader URL。"""
    target = str(target_url or "").strip()
    if not target:
        raise ValueError("target_url 不能为空")
    if not target.startswith(("http://", "https://")):
        raise ValueError("target_url 必须是 http(s) URL")

    if method == "markdown.new":
        return f"https://markdown.new/{target}"
    if method == "defuddle.md":
        return f"https://defuddle.md/{target}"
    if method == "r.jina.ai":
        return f"https://r.jina.ai/{target}"
    raise ValueError(f"未知 Reader 方法：{method}")


def iter_fetch_plan(target_url: str, include_browser: bool = False) -> Iterable[dict[str, str]]:
    """按 Smart Web Fetch 技能顺序产出抓取计划。"""
    for method in READER_METHODS:
        yield {
            "method": method,
            "url": build_reader_url(method, target_url),
        }

    yield {
        "method": "scrapling",
        "url": target_url,
    }

    if include_browser:
        yield {
            "method": "playwright",
            "url": target_url,
        }


def fetch_url(
    target_url: str,
    *,
    timeout: int = 20,
    include_browser: bool = False,
    methods: Iterable[str] | None = None,
) -> SmartFetchResult:
    """按降级链抓取 URL，返回第一个成功结果。"""
    selected_methods = list(methods) if methods is not None else [
        step["method"] for step in iter_fetch_plan(target_url, include_browser=include_browser)
    ]

    failures: list[str] = []
    for method in selected_methods:
        started = time.monotonic()
        try:
            if method in READER_METHODS:
                result = _fetch_requests(
                    method=method,
                    url=build_reader_url(method, target_url),
                    timeout=timeout,
                    accept="text/markdown,text/plain,text/html,*/*",
                )
            elif method == "scrapling":
                result = _fetch_scrapling(target_url, timeout=timeout)
            elif method == "playwright":
                result = _fetch_playwright(target_url, timeout=timeout)
            else:
                raise ValueError(f"未知抓取方法：{method}")

            if result.success and result.content.strip():
                return result
            failures.append(f"{method}: empty content")
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            failures.append(f"{method}: {type(exc).__name__}: {str(exc)[:160]} ({elapsed_ms}ms)")

    return SmartFetchResult(
        success=False,
        method="none",
        url=target_url,
        final_url=target_url,
        status_code=None,
        content_type="",
        content="",
        elapsed_ms=0,
        error="; ".join(failures),
    )


def _fetch_requests(method: str, url: str, timeout: int, accept: str) -> SmartFetchResult:
    started = time.monotonic()
    response = requests.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": accept,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    content = response.text or ""
    return SmartFetchResult(
        success=response.ok and bool(content.strip()),
        method=method,
        url=url,
        final_url=response.url,
        status_code=response.status_code,
        content_type=response.headers.get("content-type", ""),
        content=content,
        elapsed_ms=elapsed_ms,
        error="" if response.ok else f"HTTP {response.status_code}",
    )


def _fetch_scrapling(target_url: str, timeout: int) -> SmartFetchResult:
    started = time.monotonic()
    try:
        from scrapling import Fetcher  # type: ignore
    except ImportError as exc:
        raise RuntimeError("scrapling 未安装，无法使用 Scrapling 降级层") from exc

    page = Fetcher.get(target_url, timeout=timeout)
    content = getattr(page, "html", None) or str(page)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return SmartFetchResult(
        success=bool(content.strip()),
        method="scrapling",
        url=target_url,
        final_url=getattr(page, "url", target_url),
        status_code=getattr(page, "status", None),
        content_type="text/html",
        content=content,
        elapsed_ms=elapsed_ms,
    )


def _fetch_playwright(target_url: str, timeout: int) -> SmartFetchResult:
    """使用 Playwright + 系统 Chromium 渲染 JS 动态页面。"""
    import shutil as _shutil
    started = time.monotonic()

    # 优先使用系统 Chromium
    chromium_path = (
        _shutil.which("chromium-browser")
        or _shutil.which("chromium")
        or _shutil.which("google-chrome")
        or _shutil.which("/snap/bin/chromium")
    )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("playwright 未安装") from exc

    browser = None
    try:
        with sync_playwright() as p:
            launch_kwargs = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            }
            if chromium_path:
                launch_kwargs["executable_path"] = chromium_path

            browser = p.chromium.launch(**launch_kwargs)
            page = browser.new_page()
            page.set_default_timeout(timeout * 1000)

            response = page.goto(target_url, wait_until="domcontentloaded", timeout=timeout * 1000)
            # 等待JS渲染
            page.wait_for_timeout(3000)

            content = page.content()
            final_url = page.url

            browser.close()
            browser = None

            elapsed_ms = int((time.monotonic() - started) * 1000)
            return SmartFetchResult(
                success=bool(content.strip()),
                method="playwright",
                url=target_url,
                final_url=final_url,
                status_code=response.status if response else None,
                content_type="text/html",
                content=content,
                elapsed_ms=elapsed_ms,
            )
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        raise RuntimeError(f"playwright 渲染失败: {exc}") from exc
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
