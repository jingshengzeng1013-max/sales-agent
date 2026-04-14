#!/usr/bin/env python3
"""
中国政府采购网招标爬虫 - 列表页爬取
使用 curl_cffi 获取完整页面内容，结果保存为 JSON 文件
"""

import time
import random
import re
import sys
import os
import json
from datetime import datetime
from urllib.parse import urljoin, quote
from curl_cffi import requests as requests_cffi
from tqdm import tqdm

# 添加项目路径（get_data/src）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CRAWLER_CONFIG, CRAWLER_OUTPUT_DIR
from crawler.crawl_detail import _canonical_detail_url

# 输出目录
OUTPUT_DIR = CRAWLER_OUTPUT_DIR
os.makedirs(OUTPUT_DIR, exist_ok=True)

def _config_time_type() -> str:
    """与 config.py 一致：优先 timeType，兼容旧键 time_type。"""
    v = CRAWLER_CONFIG.get("timeType") or CRAWLER_CONFIG.get("time_type")
    if v is not None and str(v).strip() != "":
        return str(v).strip()
    return "3"


START_PAGE = max(1, int(CRAWLER_CONFIG.get("page_index", 1) or 1))

CONFIG = {
    "base_url": CRAWLER_CONFIG["base_url"],
    "keyword": CRAWLER_CONFIG["keyword"],
    "delay_min": CRAWLER_CONFIG["delay_min"],
    "delay_max": CRAWLER_CONFIG["delay_max"],
    "timeout": CRAWLER_CONFIG.get("timeout", 30),
    "searchtype": CRAWLER_CONFIG.get("searchtype", "1"),
    "bidSort": CRAWLER_CONFIG.get("bidSort", "0"),
    "timeType": _config_time_type(),
    "start_time": CRAWLER_CONFIG.get("start_time"),
    "end_time": CRAWLER_CONFIG.get("end_time"),
    "buyerName": CRAWLER_CONFIG.get("buyerName", ""),
    "projectId": CRAWLER_CONFIG.get("projectId", ""),
    "pinMu": str(CRAWLER_CONFIG.get("pinMu", "0")),
    "bidType": str(CRAWLER_CONFIG.get("bidType", "0")),
    "dbselect": str(CRAWLER_CONFIG.get("dbselect", "bidx")),
    "displayZone": CRAWLER_CONFIG.get("displayZone", ""),
    "zoneId": CRAWLER_CONFIG.get("zoneId", ""),
    "pppStatus": str(CRAWLER_CONFIG.get("pppStatus", "0")),
    "agentName": CRAWLER_CONFIG.get("agentName", ""),
}


def random_delay():
    """随机延迟"""
    delay = random.uniform(CONFIG["delay_min"], CONFIG["delay_max"])
    print(f"  [WAIT] {delay:.1f}s...")
    time.sleep(delay)


def fetch_page(url):
    """使用 curl_cffi 获取完整页面"""
    print(f"\n[FETCH] {url}")

    try:
        r = requests_cffi.get(url, impersonate="chrome124", timeout=CONFIG["timeout"])

        if r.status_code == 200:
            print(f"  [OK] Status: {r.status_code}, Length: {len(r.text)}")
            return r.text
        else:
            print(f"  [FAIL] Status: {r.status_code}")
            return None

    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


def build_search_url(page=1):
    """构建搜索 URL（参数顺序与政府采购网 bxsearch 常见请求一致，含 dbselect 等）。"""
    end_time = CONFIG["end_time"]
    if end_time is None:
        end_time = datetime.now().strftime("%Y:%m:%d")
    else:
        end_time = str(end_time)

    start_time = str(CONFIG["start_time"]) if CONFIG.get("start_time") else ""

    # 键顺序对齐浏览器，便于对照 Network 面板
    params = [
        ("searchtype", str(CONFIG["searchtype"])),
        ("page_index", str(page)),
        ("bidSort", str(CONFIG["bidSort"])),
        ("buyerName", str(CONFIG.get("buyerName", ""))),
        ("projectId", str(CONFIG.get("projectId", ""))),
        ("pinMu", str(CONFIG.get("pinMu", "0"))),
        ("bidType", str(CONFIG.get("bidType", "0"))),
        ("dbselect", str(CONFIG.get("dbselect", "bidx"))),
        ("kw", str(CONFIG["keyword"])),
        ("start_time", start_time),
        ("end_time", end_time),
        ("timeType", str(CONFIG["timeType"])),
        ("displayZone", str(CONFIG.get("displayZone", ""))),
        ("zoneId", str(CONFIG.get("zoneId", ""))),
        ("pppStatus", str(CONFIG.get("pppStatus", "0"))),
        ("agentName", str(CONFIG.get("agentName", ""))),
    ]
    query = "&".join(f"{k}={quote(v, safe='')}" for k, v in params)
    return f"{CONFIG['base_url']}?{query}"


def parse_list_page(html):
    """解析列表页面 HTML，提取招标项目信息"""
    items = []

    list_pattern = r'<ul class="vT-srch-result-list-bid"[^>]*>(.*?)</ul>'
    list_match = re.search(list_pattern, html, re.DOTALL)

    if not list_match:
        print("  [WARN] List container not found")
        return items

    list_content = list_match.group(1)

    item_pattern = r'<li[^>]*>(.*?)</li>'
    item_matches = re.findall(item_pattern, list_content, re.DOTALL)

    print(f"  [INFO] Found {len(item_matches)} list items")

    for item_html in item_matches:
        link_match = re.search(r'href="([^"]+)"', item_html)

        if link_match:
            link = link_match.group(1)

            title_match = re.search(r'<a[^>]*>(.*?)</a>', item_html, re.DOTALL)
            if title_match:
                title_raw = title_match.group(1)
                title_clean = re.sub(r'<[^>]+>', '', title_raw)
                title = ' '.join(title_clean.split())
            else:
                title = "Unknown"

            if link.startswith('//'):
                full_url = 'https:' + link
            elif link.startswith('/'):
                full_url = urljoin("https://search.ccgp.gov.cn", link)
            else:
                full_url = link

            if len(title) > 10:
                items.append({
                    "title": title,
                    "url": full_url,
                })

    return items


def load_existing_json(json_path):
    """加载已有的 JSON 数据，用于去重。空文件、损坏 JSON 时返回 [] 并提示，避免爬取收尾崩溃。"""
    if not os.path.exists(json_path):
        return []
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        print(f"[WARN] 无法读取 {json_path}：{e}，按空列表处理")
        return []
    if not raw.strip():
        print(f"[WARN] {json_path} 为空，按空列表处理")
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[WARN] {json_path} 不是合法 JSON（{e}），按空列表处理；将用本批结果重写文件")
        return []
    if isinstance(data, list):
        return data
    print(f"[WARN] {json_path} 根节点不是数组（类型 {type(data).__name__}），按空列表处理")
    return []


def save_to_json(results, json_path):
    """保存数据到 JSON 文件；与详情爬取一致，按 canonical detail_url 去重。"""
    existing = load_existing_json(json_path)
    existing_urls: set[str] = set()
    for item in existing:
        u = _canonical_detail_url(item.get("detail_url"))
        if u:
            existing_urls.add(u)

    new_count = 0
    skipped_dup = 0
    skipped_no_url = 0
    for item in results:
        u = _canonical_detail_url(item.get("detail_url"))
        if not u:
            skipped_no_url += 1
            continue
        if u in existing_urls:
            skipped_dup += 1
            continue
        existing_urls.add(u)
        existing.append(item)
        new_count += 1

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(
        f"[JSON] 新增 {new_count} 条，共 {len(existing)} 条（唯一 URL）；"
        f"本批重复/已存在 {skipped_dup}；无有效 URL {skipped_no_url}"
    )
    print(f"[JSON] 已保存到：{json_path}")
    return new_count


def crawl_list_page(page_num):
    """爬取列表页，返回数据列表"""
    print(f"\n{'='*60}")
    print(f"[PAGE {page_num}]")
    print(f"{'='*60}")

    url = build_search_url(page_num)
    html = fetch_page(url)

    if not html:
        print("  [FAIL] No HTML content")
        return []

    if "频繁访问" in html or "请稍后再试" in html:
        print("  [BLOCKED] Access denied!")
        return []

    items = parse_list_page(html)
    print(f"  [FOUND] {len(items)} tenders")

    for i, item in enumerate(items[:5], 1):
        print(f"    {i}. {item['title'][:60]}...")

    results = []
    for item in items:
        results.append({
            "project_name": item["title"],
            "detail_url": item["url"],
            "content": "",
        })

    print(f"  [PAGE {page_num}] 爬取到 {len(results)} 条")
    return results


def _page_results_fingerprint(rows: list) -> tuple[str, ...]:
    """当前页列表条目的 canonical URL 指纹，用于检测站点是否重复返回同一页。"""
    keys: list[str] = []
    for row in rows:
        u = _canonical_detail_url(row.get("detail_url"))
        if u:
            keys.append(u)
    return tuple(sorted(keys))


def run_crawl_list(max_pages=3):
    """
    爬取招标列表并保存为 JSON

    Args:
        max_pages: 最大爬取页数，0 表示爬取所有

    Returns:
        dict: 爬取结果统计
    """
    print("="*60)
    print("CCGP Crawler - 列表页爬取")
    print("="*60)
    _et = CONFIG["end_time"] or datetime.now().strftime("%Y:%m:%d")
    print(
        f"[CONFIG] 起始页={START_PAGE}；timeType={CONFIG['timeType']}；"
        f"searchtype={CONFIG['searchtype']}；bidSort={CONFIG['bidSort']}；"
        f"dbselect={CONFIG.get('dbselect', 'bidx')}"
    )
    print(
        f"[CONFIG] 时间范围 start_time={CONFIG.get('start_time') or '(空)'} "
        f"end_time={_et}"
    )

    json_path = OUTPUT_DIR / "tenders_list.json"

    all_results = []
    prev_fingerprint: tuple[str, ...] | None = None
    pages_fetched = 0
    total_new_items = 0

    def persist_page(page_num: int, results: list) -> None:
        """每页成功后立即合并写入 tenders_list.json（断点可续、不丢本页）。"""
        nonlocal total_new_items
        n = save_to_json(results, json_path)
        total_new_items += n
        print(f"[LIST] 第 {page_num} 页已写入 {json_path.name}（本页合并新增 {n} 条）")

    if max_pages <= 0:
        page = START_PAGE
        while True:
            results = crawl_list_page(page)
            if not results:
                break
            fp = _page_results_fingerprint(results)
            if prev_fingerprint is not None and fp == prev_fingerprint:
                print(
                    f"\n[INFO] 第 {page} 页与上一页结果完全相同，停止翻页"
                    f"（请检查 config 中 timeType / 时间范围是否与站点分页一致）"
                )
                break
            prev_fingerprint = fp
            all_results.extend(results)
            pages_fetched += 1
            persist_page(page, results)
            random_delay()
            page += 1
    else:
        page_progress = tqdm(
            range(START_PAGE, START_PAGE + max_pages),
            desc="列表页抓取",
            unit="页",
        )
        for page in page_progress:
            results = crawl_list_page(page)
            fp = _page_results_fingerprint(results)
            if prev_fingerprint is not None and fp == prev_fingerprint:
                print(
                    f"\n[INFO] 第 {page} 页与上一页结果完全相同，提前结束本批"
                    f"（若需更多结果，请在 config 中调整 timeType 或日期范围）"
                )
                break
            prev_fingerprint = fp
            all_results.extend(results)
            pages_fetched += 1
            persist_page(page, results)
            page_progress.set_postfix(current_page=page, total=len(all_results))
            if page < START_PAGE + max_pages - 1 and results:
                random_delay()

    print("\n" + "="*60)
    print(f"爬取完成!")
    print(f"爬取条数：{len(all_results)}")
    print(f"新增条数（本 run 累计）：{total_new_items}")
    print(f"JSON 文件：{json_path}")
    print("="*60)

    return {
        "success": True,
        "pages_crawled": pages_fetched,
        "items_crawled": len(all_results),
        "new_items": total_new_items,
        "json_path": str(json_path),
    }


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='中国政府采购网招标爬虫')
    parser.add_argument('--pages', type=int, default=3, help='爬取页数，0=爬取所有')

    args = parser.parse_args()

    run_crawl_list(max_pages=args.pages)


if __name__ == "__main__":
    main()
