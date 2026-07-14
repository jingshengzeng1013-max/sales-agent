# -*- coding: utf-8 -*-
"""Crawler workflow orchestration for Web UI and scripts.

The workflow supports three backends:
- traditional: curl_cffi + optional proxy pool
- smart: Smart Web Fetch readers/Scrapling/optional Playwright
- auto: traditional first, Smart Fetch fallback when the list stage returns no rows
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config import CRAWLER_CONFIG, CRAWLER_OUTPUT_DIR


VALID_BACKENDS = {"traditional", "smart", "auto"}


def run_crawl_list(max_pages: int = 3) -> dict[str, Any]:
    """Wrapper kept patchable for tests and import-light at module load time."""
    from src.crawler.ccgp_crawler import run_crawl_list as _run_crawl_list

    return _run_crawl_list(max_pages=max_pages)


def run_crawl_detail(
    *,
    limit: int | None = None,
    concurrent: bool = True,
    max_workers: int = 2,
    source_json: str | None = None,
) -> dict[str, Any]:
    """Wrapper kept patchable for tests and import-light at module load time."""
    from src.crawler.crawl_detail import run_crawl_detail as _run_crawl_detail

    return _run_crawl_detail(
        limit=limit,
        concurrent=concurrent,
        max_workers=max_workers,
        source_json=source_json,
    )


def run_smart_search(**kwargs: Any) -> dict[str, Any]:
    """Wrapper kept patchable for tests and import-light at module load time."""
    from src.crawler.ccgp_smart_search import run_smart_search as _run_smart_search

    return _run_smart_search(**kwargs)


def import_tenders_from_jsonl(jsonl_path: str | None = None) -> dict[str, Any]:
    """Wrapper kept patchable for tests."""
    from src.storage.import_tenders import import_tenders_from_jsonl as _import_list

    return _import_list(jsonl_path)


def update_tender_details_from_jsonl(jsonl_path: str | None = None) -> dict[str, Any]:
    """Wrapper kept patchable for tests."""
    from src.storage.import_tenders import update_tender_details_from_jsonl as _update_detail

    return _update_detail(jsonl_path)


def crawler_workflow_defaults() -> dict[str, Any]:
    """Return Web UI defaults derived from CRAWLER_CONFIG."""
    return {
        "fetch_backend": "auto",
        "include_browser": False,
        "keyword": CRAWLER_CONFIG.get("keyword", "通信"),
        "base_url": CRAWLER_CONFIG.get("base_url", ""),
        "delay_min": float(CRAWLER_CONFIG.get("delay_min", 2.0)),
        "delay_max": float(CRAWLER_CONFIG.get("delay_max", 5.0)),
        "page_index": int(CRAWLER_CONFIG.get("page_index", 1) or 1),
        "max_pages": int(CRAWLER_CONFIG.get("max_pages", 3)),
        "timeout": int(CRAWLER_CONFIG.get("timeout", 30)),
        "searchtype": str(CRAWLER_CONFIG.get("searchtype", "2")),
        "bidSort": str(CRAWLER_CONFIG.get("bidSort", "0")),
        "time_type": str(CRAWLER_CONFIG.get("timeType") or CRAWLER_CONFIG.get("time_type") or "4"),
        "start_time": CRAWLER_CONFIG.get("start_time") or "",
        "end_time": CRAWLER_CONFIG.get("end_time") or "",
        "detail_limit": 0,
        "detail_delay_min": 5.0,
        "detail_delay_max": 12.0,
        "detail_timeout": 30,
        "detail_workers": 2,
        "run_list": True,
        "run_import": True,
        "run_detail": True,
        "json_path": "",
    }


def run_crawler_graph(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the configured crawler workflow.

    The name is kept for compatibility with the existing Web UI copy and router.
    """
    cfg = _normalize_payload(payload or {})
    backend = cfg["fetch_backend"]

    print("=" * 60)
    print("Crawler Workflow")
    print("=" * 60)
    print(
        f"[CONFIG] backend={backend}; keyword={cfg['keyword']}; pages={cfg['max_pages']}; "
        f"page_index={cfg['page_index']}; searchtype={cfg['searchtype']}; timeType={cfg['time_type']}"
    )
    print(
        f"[CONFIG] list_delay={cfg['delay_min']}-{cfg['delay_max']}s; "
        f"detail_delay={cfg['detail_delay_min']}-{cfg['detail_delay_max']}s; "
        f"detail_workers={cfg['detail_workers']}"
    )

    if backend == "smart":
        return _run_smart_workflow(cfg, backend_label="smart")

    traditional_report = _run_traditional_workflow(cfg, backend_label=backend)
    if backend != "auto":
        return traditional_report

    if _should_fallback_to_smart(cfg, traditional_report):
        print("[AUTO] 传统列表阶段没有抓到结果，切换 Smart Fetch 低频兜底。")
        smart_report = _run_smart_workflow(cfg, backend_label="auto")
        smart_report["fallback_reason"] = "traditional_list_empty"
        smart_report["traditional"] = traditional_report
        return smart_report

    return traditional_report


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    defaults = crawler_workflow_defaults()
    cfg = {**defaults, **{k: v for k, v in payload.items() if v is not None}}

    backend = str(cfg.get("fetch_backend") or "auto").strip().lower()
    if backend not in VALID_BACKENDS:
        raise ValueError(f"未知 fetch_backend={backend}，可选：traditional/smart/auto")
    cfg["fetch_backend"] = backend

    cfg["keyword"] = str(cfg.get("keyword") or defaults["keyword"]).strip()
    cfg["base_url"] = str(cfg.get("base_url") or defaults["base_url"]).strip()
    cfg["searchtype"] = str(cfg.get("searchtype") or defaults["searchtype"]).strip()
    cfg["bidSort"] = str(cfg.get("bidSort") or defaults["bidSort"]).strip()
    cfg["time_type"] = str(cfg.get("time_type") or defaults["time_type"]).strip()
    cfg["start_time"] = str(cfg.get("start_time") or "").strip()
    cfg["end_time"] = str(cfg.get("end_time") or "").strip()
    cfg["json_path"] = str(cfg.get("json_path") or "").strip()

    for key in ("delay_min", "delay_max", "detail_delay_min", "detail_delay_max"):
        cfg[key] = max(0.0, _as_float(cfg.get(key), defaults[key]))
    for key in ("timeout", "detail_timeout", "page_index", "max_pages", "detail_workers", "detail_limit"):
        cfg[key] = max(0, _as_int(cfg.get(key), defaults[key]))

    cfg["page_index"] = max(1, cfg["page_index"])
    cfg["detail_workers"] = max(1, min(cfg["detail_workers"], 8))
    cfg["include_browser"] = bool(cfg.get("include_browser", False))
    cfg["run_list"] = bool(cfg.get("run_list", True))
    cfg["run_import"] = bool(cfg.get("run_import", True))
    cfg["run_detail"] = bool(cfg.get("run_detail", True))
    return cfg


def _run_traditional_workflow(cfg: dict[str, Any], *, backend_label: str) -> dict[str, Any]:
    try:
        _configure_traditional_modules(cfg)
    except ModuleNotFoundError as exc:
        print(f"[TRADITIONAL] 传统爬虫依赖缺失：{exc}")
        return {
            "success": False,
            "backend": backend_label,
            "active_backend": "traditional",
            "list": {
                "success": False,
                "items_crawled": 0,
                "new_items": 0,
                "error": str(exc),
            },
            "detail": None,
            "import": {},
        }
    list_result: dict[str, Any] | None = None
    detail_result: dict[str, Any] | None = None
    import_result: dict[str, Any] = {}

    if cfg["run_list"]:
        list_result = run_crawl_list(max_pages=cfg["max_pages"])
    else:
        list_path = cfg["json_path"] or str(CRAWLER_OUTPUT_DIR / "tenders_list.jsonl")
        print(f"[SKIP] 跳过列表爬取，列表路径={list_path}")
        list_result = {"skipped": True, "json_path": list_path, "items_crawled": 0, "new_items": 0}

    list_path = str(list_result.get("json_path") or cfg["json_path"] or CRAWLER_OUTPUT_DIR / "tenders_list.jsonl")
    if cfg["run_import"]:
        import_result["list"] = import_tenders_from_jsonl(list_path)

    if cfg["run_detail"]:
        detail_limit = cfg["detail_limit"] or None
        detail_result = run_crawl_detail(
            limit=detail_limit,
            concurrent=cfg["detail_workers"] > 1,
            max_workers=cfg["detail_workers"],
            source_json=list_path,
        )
        if cfg["run_import"] and detail_result.get("json_path"):
            import_result["detail"] = update_tender_details_from_jsonl(detail_result["json_path"])
    else:
        print("[SKIP] 跳过详情爬取")

    return {
        "success": True,
        "backend": backend_label,
        "active_backend": "traditional",
        "list": list_result,
        "detail": detail_result,
        "import": import_result,
    }


def _run_smart_workflow(cfg: dict[str, Any], *, backend_label: str) -> dict[str, Any]:
    if not cfg["run_list"]:
        print("[SMART] Smart Fetch 需要先抓搜索列表；当前 run_list=false，跳过 Smart 阶段。")
        return {
            "success": False,
            "backend": backend_label,
            "active_backend": "smart",
            "list": {"skipped": True, "reason": "smart_requires_list_stage"},
            "detail": None,
            "import": {},
        }

    pages = cfg["max_pages"] if cfg["max_pages"] > 0 else 1
    list_path = Path(cfg["json_path"]) if cfg["json_path"] else CRAWLER_OUTPUT_DIR / "tenders_list_smart_fetch.jsonl"
    detail_path = CRAWLER_OUTPUT_DIR / "tenders_detail_smart_fetch.jsonl"
    print(
        f"[SMART] 低频抓取 pages={pages}; include_browser={cfg['include_browser']}; "
        f"list_output={list_path}"
    )

    smart_result = run_smart_search(
        keyword=cfg["keyword"],
        pages=pages,
        crawl_details=cfg["run_detail"],
        detail_limit=cfg["detail_limit"] or None,
        list_output=str(list_path),
        detail_output=str(detail_path),
        timeout=cfg["timeout"],
        include_browser=cfg["include_browser"],
        searchtype=cfg["searchtype"],
        bid_sort=cfg["bidSort"],
        time_type=cfg["time_type"],
        start_time=cfg["start_time"],
        end_time=cfg["end_time"] or None,
        page_delay_min=cfg["delay_min"],
        page_delay_max=cfg["delay_max"],
        detail_delay_min=cfg["detail_delay_min"],
        detail_delay_max=cfg["detail_delay_max"],
    )

    import_result: dict[str, Any] = {}
    list_output = smart_result.get("list_output")
    detail_output = smart_result.get("detail_output")
    if cfg["run_import"] and list_output and smart_result.get("list_count", 0) > 0:
        import_result["list"] = import_tenders_from_jsonl(list_output)
    if cfg["run_import"] and detail_output and smart_result.get("detail_count", 0) > 0:
        import_result["detail"] = update_tender_details_from_jsonl(detail_output)

    return {
        "success": bool(smart_result.get("success")),
        "backend": backend_label,
        "active_backend": "smart",
        "list": smart_result,
        "detail": smart_result if cfg["run_detail"] else None,
        "import": import_result,
    }


def _configure_traditional_modules(cfg: dict[str, Any]) -> None:
    from src.crawler import ccgp_crawler, crawl_detail

    ccgp_crawler.CONFIG.update(
        {
            "base_url": cfg["base_url"],
            "keyword": cfg["keyword"],
            "delay_min": cfg["delay_min"],
            "delay_max": cfg["delay_max"],
            "timeout": cfg["timeout"],
            "page_index": cfg["page_index"],
            "searchtype": cfg["searchtype"],
            "bidSort": cfg["bidSort"],
            "timeType": cfg["time_type"],
            "start_time": cfg["start_time"],
            "end_time": cfg["end_time"] or None,
        }
    )
    ccgp_crawler.START_PAGE = cfg["page_index"]
    crawl_detail.REQUEST_TIMEOUT = cfg["detail_timeout"]
    crawl_detail.POST_REQUEST_SLEEP_SERIAL = (cfg["detail_delay_min"], cfg["detail_delay_max"])
    crawl_detail.POST_REQUEST_SLEEP_CONCURRENT = (cfg["detail_delay_min"], cfg["detail_delay_max"])


def _should_fallback_to_smart(cfg: dict[str, Any], report: dict[str, Any]) -> bool:
    if not cfg["run_list"]:
        return False
    list_report = report.get("list") or {}
    if list_report.get("skipped"):
        return False
    return int(list_report.get("items_crawled") or 0) == 0


def _as_int(value: Any, fallback: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(fallback)


def _as_float(value: Any, fallback: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)
