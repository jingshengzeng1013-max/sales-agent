# -*- coding: utf-8 -*-
"""
爬取招标详情页面，结果保存为 JSON 文件。
每条记录含正文、元数据及 attachments（附件显示名与 download_url，规则同 batch_crawl_attachments）。

默认行为：从 tenders_list.json 与已有 tenders_detail.json 求差集，不限制条数，直至待爬 URL 全部爬完（可用 --limit 限制本批数量）。
"""

import time
import random
import re
import sys
import os
import json
import html
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin, urlunparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests as requests_cffi
from tqdm import tqdm

# 项目根目录（get_data），保证与 src.config 一致
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from src.config import CRAWLER_OUTPUT_DIR
from src.crawler.proxy_manager import proxy_manager
from src.utils.jsonl_helper import load_jsonl, save_jsonl, save_jsonl_single

# 输出目录
OUTPUT_DIR = CRAWLER_OUTPUT_DIR
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 并发配置：8 通道 (配合 5-10 个代理 IP)
CONCURRENT_CHANNELS = 8
REQUEST_TIMEOUT = 30

# 请求节奏：随机间隔（秒），降低瞬时 QPS、减少封 IP / 限流风险
# 并发：每个工作线程在单次请求结束后休眠（多线程仍可能并行，但单线程内连续请求被拉开）
POST_REQUEST_SLEEP_CONCURRENT = (1.0, 2.8)
# 串行：相邻两次请求之间的间隔（在循环里调用）+ fetch_detail 内也会睡一次，取较大间隔避免过快
POST_REQUEST_SLEEP_SERIAL = (2.0, 5.0)


def _normalize_detail_url(url) -> str | None:
    """统一 URL 字符串（首尾空白、无效则跳过）。"""
    if url is None:
        return None
    u = url.strip() if isinstance(url, str) else str(url).strip()
    return u or None


def _canonical_detail_url(url) -> str | None:
    """
    详情 URL 规范化，用于去重与落盘：
    - 去 fragment；hostname 小写；默认端口不写进 netloc
    - 政府采购网统一为 http://www.ccgp.gov.cn/...（合并 https/http、ccgp 与 www 差异）
    """
    u = _normalize_detail_url(url)
    if not u:
        return None
    try:
        p = urlparse(u)
        host = (p.hostname or "").strip().lower()
        if not host:
            return u
        scheme = (p.scheme or "http").lower()
        port = p.port
        if host in ("ccgp.gov.cn", "www.ccgp.gov.cn"):
            scheme = "http"
            host = "www.ccgp.gov.cn"
        if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
            netloc = f"{host}:{port}"
        else:
            netloc = host
        path = p.path or "/"
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        return urlunparse((scheme, netloc, path, "", p.query or "", ""))
    except Exception:
        return u


def _sleep_after_request(post_sleep_range: tuple[float, float] | None) -> None:
    if post_sleep_range:
        lo, hi = post_sleep_range
        if hi > 0:
            time.sleep(random.uniform(lo, hi))


def _fetch_detail_single(
    url: str,
    channel: int,
    post_sleep_range: tuple[float, float] | None = None,
) -> tuple[str, str | None]:
    """
    单个 URL 爬取（通道化），支持自动代理刷新
    post_sleep_range: 本次 HTTP 结束后随机休眠区间（秒），用于并发降速防封。
    Returns: (url, html_content or None)
    """
    print(f"\n[CHAN-{channel}] [FETCH] {url[:90]}...")

    max_retries = 2
    for attempt in range(max_retries):
        try:
            # 轻微错开多线程同时打第一包
            time.sleep(random.uniform(0, 0.35))
            
            # 获取当前可用代理
            proxies = proxy_manager.get_proxy()
            
            r = requests_cffi.get(
                url, 
                impersonate="chrome124", 
                timeout=REQUEST_TIMEOUT,
                proxies=proxies
            )

            if r.status_code == 200:
                # 检查是否被封禁
                if "频繁访问" in r.text or "请稍后再试" in r.text:
                    print(f"  [CHAN-{channel}] [BLOCKED] Detected block message, forcing proxy refresh...")
                    proxy_manager.get_proxy(force_refresh=True)
                    continue
                    
                print(f"  [CHAN-{channel}] [OK] Status: {r.status_code}, Length: {len(r.text)}")
                return (url, r.text)
            elif r.status_code in [403, 429]:
                print(f"  [CHAN-{channel}] [FAIL] Status: {r.status_code}, forcing proxy refresh...")
                proxy_manager.get_proxy(force_refresh=True)
            else:
                print(f"  [CHAN-{channel}] [FAIL] Status: {r.status_code}")
                return (url, None)

        except Exception as e:
            print(f"  [CHAN-{channel}] [ERROR] {e}")
            if attempt < max_retries - 1:
                proxy_manager.get_proxy(force_refresh=True)
            else:
                return (url, None)
        finally:
            _sleep_after_request(post_sleep_range)
    
    return (url, None)


def _remove_style_script_tags(html_frag: str) -> str:
    """去掉 style/script，避免去标签后把 CSS/JS 当成正文。"""
    s = re.sub(r"<style[^>]*>.*?</style>", "", html_frag, flags=re.I | re.DOTALL)
    s = re.sub(r"<script[^>]*>.*?</script>", "", s, flags=re.I | re.DOTALL)
    return s


def _strip_css_rule_blocks_from_text(text: str) -> str:
    """
    去掉泄漏到纯文本里的 CSS 规则块（政府采购网常见：#noticeArea 整段样式贴在正文前）。
    循环剥离 `#noticeArea ... { ... }`，直到没有匹配。
    """
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"#noticeArea[^{]*\{[^}]*\}", "", text, flags=re.DOTALL)
    # 偶发：仅余孤立 `}` 或连续 `}`
    text = re.sub(r"\}\s*\}", " ", text)
    text = text.lstrip().lstrip("}").strip()
    return text


def _html_fragment_to_clean_text(html_frag: str) -> str:
    """HTML片段 → 纯文本正文，不包含前端样式/脚本代码。
    
    保留换行符 \n 以便 LLM 识别段落结构（如联系方式列表）。
    """
    frag = _remove_style_script_tags(html_frag or "")
    # 将常见的块级标签替换为换行，确保文本结构不丢失
    frag = re.sub(r"<(p|div|br|tr|li|h[1-6])[^>]*>", "\n", frag, flags=re.I)
    plain = re.sub(r"<[^>]+>", " ", frag)
    plain = html.unescape(plain)
    plain = _strip_css_rule_blocks_from_text(plain)
    # 历史正则：零散的 `#id{}` / `.class{}`（非 noticeArea 的短块）
    plain = re.sub(r"#[a-zA-Z0-9_-]+\s*\{[^}]*\}", "", plain)
    plain = re.sub(r"\.[a-zA-Z0-9_-]+\s*\{[^}]*\}", "", plain)
    plain = re.sub(r"@\s*media[^{]*\{[^}]*\}", "", plain)
    plain = re.sub(r"@\s*charset[^;]*;", "", plain)
    plain = re.sub(r"<!--.*?-->", "", plain, flags=re.DOTALL)
    
    # 压缩连续空格，但保留换行
    lines = []
    for line in plain.splitlines():
        line = " ".join(line.split()).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def fetch_detail(url):
    """获取详情页（串行；支持自动代理刷新）"""
    print(f"\n[FETCH] {url}")

    max_retries = 2
    for attempt in range(max_retries):
        try:
            proxies = proxy_manager.get_proxy()
            r = requests_cffi.get(
                url, 
                impersonate="chrome124", 
                timeout=30,
                proxies=proxies
            )

            if r.status_code == 200:
                if "频繁访问" in r.text or "请稍后再试" in r.text:
                    print(f"  [BLOCKED] Detected block message, forcing proxy refresh...")
                    proxy_manager.get_proxy(force_refresh=True)
                    continue
                print(f"  [OK] Status: {r.status_code}, Length: {len(r.text)}")
                return r.text
            elif r.status_code in [403, 429]:
                print(f"  [FAIL] Status: {r.status_code}, forcing proxy refresh...")
                proxy_manager.get_proxy(force_refresh=True)
            else:
                print(f"  [FAIL] Status: {r.status_code}")
                return None

        except Exception as e:
            print(f"  [ERROR] {e}")
            if attempt < max_retries - 1:
                proxy_manager.get_proxy(force_refresh=True)
            else:
                return None
        finally:
            _sleep_after_request(POST_REQUEST_SLEEP_SERIAL)
    
    return None


def _strip_tags_text(s: str) -> str:
    t = re.sub(r"<[^>]+>", " ", s or "")
    t = html.unescape(t)
    return " ".join(t.split()).strip()


def _extract_detail_title(html: str) -> str:
    """政府采购网详情：ArticleTitle meta > vF_detail_header内 h2 > title标签。"""
    m = re.search(
        r'<meta\s+name\s*=\s*["\']ArticleTitle["\']\s+content\s*=\s*["\']([^"\']+)["\']',
        html,
        re.I,
    )
    if not m:
        m = re.search(
            r'<meta\s+content\s*=\s*["\']([^"\']+)["\']\s+name\s*=\s*["\']ArticleTitle["\']',
            html,
            re.I,
        )
    if m:
        return _strip_tags_text(m.group(1))

    m = re.search(
        r'class\s*=\s*["\'][^"\']*vF_detail_header[^"\']*["\'][^>]*>.*?<h2[^>]*>(.*?)</h2>',
        html,
        re.DOTALL | re.I,
    )
    if m:
        return _strip_tags_text(m.group(1))

    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL | re.I)
    if m:
        return _strip_tags_text(m.group(1))

    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.I)
    if m:
        return _strip_tags_text(m.group(1))
    return ""


def _parse_datetime_to_iso_local(raw: str) -> str | None:
    """
    解析政府采购网常见时间串为 YYYY-MM-DDTHH:MM:SS（无秒则补 :00）。
    支持：2026-03-24 10:43、2026年03月24日 10:43
    """
    if not raw:
        return None
    s = raw.strip()
    m = re.match(
        r"(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?",
        s,
    )
    if m:
        y, mo, d, hh, mm, ss = m.groups()
        sec = int(ss) if ss else 0
        try:
            dt = datetime(int(y), int(mo), int(d), int(hh), int(mm), sec)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return None
    m = re.match(
        r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?",
        s,
    )
    if m:
        y, mo, d, hh, mm, ss = m.groups()
        sec = int(ss) if ss else 0
        try:
            dt = datetime(int(y), int(mo), int(d), int(hh), int(mm), sec)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return None
    return None


def _extract_publish_datetime(html: str) -> str:
    """优先 meta PubDate，其次 span#pubTime，再尝试正文常见「发布时间」。"""
    candidates: list[str] = []

    for pat in (
        r'<meta\s+name\s*=\s*["\']PubDate["\']\s+content\s*=\s*["\']([^"\']+)["\']',
        r'<meta\s+content\s*=\s*["\']([^"\']+)["\']\s+name\s*=\s*["\']PubDate["\']',
    ):
        m = re.search(pat, html, re.I)
        if m:
            candidates.append(m.group(1))
            break

    m = re.search(r'<span[^>]*id\s*=\s*["\']pubTime["\'][^>]*>([^<]+)</span>', html, re.I)
    if m:
        candidates.append(m.group(1))

    m = re.search(r"发布时间\s*[:：]\s*([^<\n]{4,40})", html)
    if m:
        candidates.append(m.group(1).strip())

    for c in candidates:
        iso = _parse_datetime_to_iso_local(c)
        if iso:
            return iso

    # 仅日期兜底（补00:00:00）
    for pattern in (
        r"(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{1,2})",
        r"(\d{4})年(\d{1,2})月(\d{1,2})日",
    ):
        m = re.search(pattern, html)
        if m:
            if len(m.groups()) >= 3 and "年" in pattern:
                iso = _parse_datetime_to_iso_local(
                    f"{m.group(1)}年{m.group(2)}月{m.group(3)}日 00:00"
                )
            else:
                iso = _parse_datetime_to_iso_local(
                    f"{m.group(1)} {m.group(2)}:{m.group(3)}"
                )
            if iso:
                return iso

    m = re.search(r"(\d{4}-\d{2}-\d{2})", html)
    if m:
        iso = _parse_datetime_to_iso_local(f"{m.group(1)} 00:00")
        if iso:
            return iso
    return ""


# 按长度降序匹配，避免「磋商公告」误匹配短后缀
_KNOWN_ANNOUNCE_SUFFIXES: tuple[str, ...] = (
    "竞争性磋商公告",
    "竞争性谈判公告",
    "公开招标公告",
    "询价公告",
    "单一来源采购公示",
    "合同公告",
    "中标（成交）公告",
    "中标公告",
    "成交公告",
    "更正公告",
    "废标公告",
    "流标公告",
    "终止公告",
    "采购意向公开",
    "采购公告",
)


def _announce_type_from_title(title: str) -> str:
    """标题末尾常见「…公告/公示」类型；非常见类型返回空串，交由面包屑。"""
    t = (title or "").strip()
    if not t:
        return ""
    for suf in sorted(_KNOWN_ANNOUNCE_SUFFIXES, key=len, reverse=True):
        if t.endswith(suf):
            return suf
    return ""


def _announce_type_from_breadcrumb(html: str) -> str:
    links = re.findall(
        r'<a[^>]*class\s*=\s*["\'][^"\']*CurrChnlCls[^"\']*["\'][^>]*>([^<]+)</a>',
        html,
        re.I,
    )
    if links:
        return links[-1].strip()
    return ""


def _extract_announce_type(html: str, title: str) -> str:
    t = _announce_type_from_title(title)
    if t:
        return t
    return _announce_type_from_breadcrumb(html)


# --- 详情页附件链接（与 batch_crawl_attachments 规则对齐） ---


def _extract_element_by_id(html: str, element_id: str) -> str | None:
    pattern = rf'<[^>]*id=["\']{element_id}["\'][^>]*>.*?</[^>]+>'
    match = re.search(pattern, html, re.I | re.DOTALL)
    return match.group(0) if match else None


def _html_to_clean_text_simple(fragment: str) -> str:
    """锚点内 HTML → 纯文本（附件链接文案）。"""
    text = re.sub(r"<script[^>]*>.*?</script>", "", fragment, flags=re.I | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.I | re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    return " ".join(text.split()).strip()


def _is_attachment_href(href: str, link_text: str = "") -> bool:
    """判断 href 是否像附件下载链接。"""
    url_lower = href.lower()
    text_lower = (link_text or "").lower()
    exts = (
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".txt",
        ".csv",
        ".ppt",
        ".pptx",
        ".ofd",
        ".wps",
    )
    for ext in exts:
        if url_lower.endswith(ext) or text_lower.endswith(ext):
            return True
    patterns = (
        r"/fileApi/",
        r"/oss/download\?",
        r"download\.ccgp\.gov\.cn",
        r"zcy-gov-open-doc",
        r"gov-open-doc",
        r"/TPFrame/.*downAttach",
        r"/WebbuilderMIS/attach/",
        r"attachGuid=",
        r"/downALoad",
    )
    for p in patterns:
        if re.search(p, href, re.I):
            return True
    return False


def _uuid_from_download_url(url: str) -> str | None:
    m = re.search(r"[?&]uuid=([0-9A-Fa-f]+)", url)
    return m.group(1) if m else None


def extract_attachments_for_detail(page_html: str, page_url: str) -> list[dict]:
    """
    从详情页 HTML 提取附件：file_name、download_url、uuid（中央网 oss 链接常有）。
    去重按 download_url。
    """
    base = (page_url or "").strip()
    records: list[dict] = []
    seen: set[str] = set()

    def push(href: str, link_text: str) -> None:
        h = (href or "").strip()
        if not h or h.startswith(("javascript:", "mailto:", "#")):
            return
        if not _is_attachment_href(h, link_text):
            return
        full = urljoin(base, h) if base else h
        if full in seen:
            return
        seen.add(full)
        name = link_text if link_text else (os.path.basename(urlparse(full).path) or full)
        records.append(
            {
                "file_name": name,
                "download_url": full,
                "uuid": _uuid_from_download_url(full),
            }
        )

    biz = _extract_element_by_id(page_html, "bizDownload")
    if biz:
        for m in re.finditer(
            r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            biz,
            re.I | re.DOTALL,
        ):
            push(m.group(1), _html_to_clean_text_simple(m.group(2)))

    for m in re.finditer(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        page_html,
        re.I | re.DOTALL,
    ):
        push(m.group(1), _html_to_clean_text_simple(m.group(2)))

    return records


def parse_detail(html, url):
    """解析详情页面"""
    if not html:
        return None

    url_norm = _canonical_detail_url(url) or ""
    title = _extract_detail_title(html)
    publish_date = _extract_publish_datetime(html)
    announce_type = _extract_announce_type(html, title)

    data = {
        "url": url_norm,
        "title": title,
        "publish_date": publish_date,
        "announce_type": announce_type,
        "budget": "",
        "content": "",
        "attachments": extract_attachments_for_detail(html, url_norm or (url or "")),
        "crawl_time": datetime.now().isoformat(),
    }

    # 提取预算金额
    budget_patterns = [
        r'预算金额 [:：]\s*([^<\n]+)',
        r'预算 [:：]\s*([^<\n]+)',
        r'(\d+[\.\d]*\s*[万元]+)',
    ]
    for pattern in budget_patterns:
        budget_match = re.search(pattern, html)
        if budget_match:
            data["budget"] = budget_match.group(1).strip()
            break

    # 提取正文内容 - 使用 BeautifulSoup 处理嵌套标签
    content = ""
    soup = BeautifulSoup(html, "html.parser")

    # 1. 优先提取 #noticeArea（政府采购网常见）
    notice_area = soup.find(id="noticeArea")
    if notice_area:
        content = _html_fragment_to_clean_text(str(notice_area))

    # 2. 尝试 vF_detail_content
    if not content:
        vf_content = soup.find("div", class_="vF_detail_content")
        if vf_content:
            content = _html_fragment_to_clean_text(str(vf_content))

    # 3. 尝试 detail_content
    if not content:
        det_content = soup.find("div", class_="detail_content")
        if det_content:
            content = _html_fragment_to_clean_text(str(det_content))

    # 4. 最后尝试：提取所有 <p> 标签内容
    if not content:
        p_tags = soup.find_all("p")
        if p_tags:
            merged = "".join(str(p) for p in p_tags)
            content = _html_fragment_to_clean_text(merged)

    data["content"] = content

    return data


def load_existing_jsonl(jsonl_path):
    """加载已有的 JSONL 数据，增加容错处理"""
    return load_jsonl(str(jsonl_path))


def save_to_jsonl(results, jsonl_path, is_single=False):
    """
    保存数据到 JSONL：同一 url 只保留一条。
    is_single: 如果为 True，表示 results 是单条记录，采用追加模式。
    """
    if is_single:
        # 单条保存模式，直接追加
        save_jsonl_single(results, str(jsonl_path))
        return 1

    # 批量保存模式
    existing = load_existing_jsonl(jsonl_path)
    by_url: dict[str, dict] = {}
    for item in existing:
        u = _canonical_detail_url(item.get("url") or item.get("detail_url"))
        if u and u not in by_url:
            by_url[u] = item

    n_before = len(by_url)
    new_items = results if isinstance(results, list) else [results]
    to_append = []
    for item in new_items:
        u = _canonical_detail_url(item.get("url") or item.get("detail_url"))
        if not u:
            continue
        if u not in by_url:
            by_url[u] = item
            to_append.append(item)

    if to_append:
        save_jsonl(to_append, str(jsonl_path), append=True)

    new_count = len(by_url) - n_before
    print(f"[JSONL] 新增 {new_count} 条，共 {len(by_url)} 条（已按 url 去重）")
    print(f"[JSONL] 已保存到：{jsonl_path}")
    return new_count


def load_tenders_from_json(json_path=None, return_stats: bool = False):
    """从列表 JSONL 文件中加载待处理的招标。

    同一 canonical detail_url 只保留首次出现的记录（与详情去重逻辑一致）。
    return_stats 为 True 时返回 (out, stats)，否则只返回 out。
    """
    if json_path is None:
        json_path = OUTPUT_DIR / "tenders_list.jsonl"

    if not os.path.exists(json_path):
        print(f"[ERROR] JSONL 文件不存在：{json_path}")
        empty: list[tuple[str, str]] = []
        if return_stats:
            return empty, {
                "raw_total": 0,
                "unique_urls": 0,
                "duplicate_rows": 0,
                "no_url_rows": 0,
            }
        return []

    data = load_jsonl(str(json_path))

    raw_total = len(data)
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    duplicate_rows = 0
    no_url_rows = 0
    for item in data:
        u = _canonical_detail_url(item.get("detail_url"))
        if not u:
            no_url_rows += 1
            continue
        if u in seen:
            duplicate_rows += 1
            continue
        seen.add(u)
        name = item.get("project_name") or ""
        out.append((u, name if isinstance(name, str) else str(name)))

    stats = {
        "raw_total": raw_total,
        "unique_urls": len(out),
        "duplicate_rows": duplicate_rows,
        "no_url_rows": no_url_rows,
    }
    if return_stats:
        return out, stats
    return out


def crawl_details(
    limit: int | None = None,
    source_json=None,
    concurrent: bool = True,
    max_workers: int = CONCURRENT_CHANNELS,
):
    """
    爬取详情页面并保存为 JSON

    Args:
        limit: 最多处理的条数；为 None、0 或负数时不限制，处理待爬列表中的全部 URL（默认即全部）
        source_json: 源 JSON 文件路径，默认使用 OUTPUT_DIR/tenders_list.json
        concurrent: 是否启用并发模式
        max_workers: 并发通道数（默认 3）

    Returns:
        dict: 爬取结果统计
    """
    print("="*60)
    print("Crawl Detail Pages - 详情页爬取")
    print(f"并发模式：{'开启' if concurrent else '关闭'}，通道数：{max_workers}")
    print("="*60)

    # 获取待处理的招标（URL 已为 canonical）
    all_from_list, list_stats = load_tenders_from_json(source_json, return_stats=True)
    print(
        f"\n[INFO] 列表 JSONL 原始 {list_stats['raw_total']} 行；"
        f"唯一 detail_url {list_stats['unique_urls']} 条；"
        f"重复行 {list_stats['duplicate_rows']}；"
        f"无有效 URL {list_stats['no_url_rows']}"
    )

    existing_detail_jsonl = OUTPUT_DIR / "tenders_detail.jsonl"
    existing = load_existing_jsonl(existing_detail_jsonl)
    existing_urls: set[str] = set()
    for item in existing:
        u = _canonical_detail_url(item.get("url") or item.get("detail_url"))
        if u:
            existing_urls.add(u)

    skipped_already = sum(1 for u, _ in all_from_list if u in existing_urls)
    pending = [(url, name) for url, name in all_from_list if url not in existing_urls]

    print(
        f"[INFO] 待爬队列（唯一 URL）{len(all_from_list)} 条；"
        f"详情 JSONL 已存在 {len(existing_urls)} 条（canonical）；"
        f"因已爬取跳过 {skipped_already} 条；尚待爬取 {len(pending)} 条"
    )

    # 限制数量（仅当传入正整数时）
    if limit is not None and limit > 0:
        before_lim = len(pending)
        pending = pending[:limit]
        if before_lim > len(pending):
            print(f"[INFO] limit={limit}，本批只处理其中 {len(pending)} 条")

    # 如果 pending 为空且 limit > 0，说明全部已爬取，但用户可能想强制重爬
    # 暂时保持现状，除非用户明确要求强制重爬。
    # 修复：如果 pending 为空，但 all_from_list 不为空，且 limit > 0，
    # 可能是因为现有数据不完整，用户想重爬前 limit 条。
    if not pending and all_from_list and limit is not None and limit > 0:
        print(f"[INFO] 待爬队列为空，但检测到 limit={limit}，将强制重爬前 {limit} 条以修复数据...")
        pending = all_from_list[:limit]

    print(f"[INFO] 本批将请求 {len(pending)} 个详情页")

    if not pending:
        print("[INFO] No pending tenders to crawl")
        return {"success": True, "processed": 0, "success_count": 0}

    results = []
    seen_this_run: set[str] = set()
    success_count = 0
    failed_count = 0
    
    # 创建线程锁，保证多线程写入 JSON 时不冲突
    import threading
    file_lock = threading.Lock()

    if concurrent and len(pending) > 1:
        # === 并发模式：多通道 ===
        print(
            f"\n[INFO] 启动并发爬取，通道数：{max_workers}；"
            f"每通道请求后随机休眠约 {POST_REQUEST_SLEEP_CONCURRENT[0]}–{POST_REQUEST_SLEEP_CONCURRENT[1]} 秒"
        )

        # 过滤去重后的任务
        tasks = []
        for url, name in pending:
            nu = _canonical_detail_url(url)
            if not nu:
                print(f"[SKIP] 无效 URL: {url[:50]}...")
                continue
            if nu in existing_urls:
                # 即使已经在 existing_urls 里，如果文件里没有，也可能需要爬
                # 这里保持逻辑一致，跳过已存在的
                continue
            if nu in seen_this_run:
                continue
            seen_this_run.add(nu)
            tasks.append((nu, name))

        print(f"[INFO] 实际待爬取：{len(tasks)} 条")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {
                executor.submit(
                    _fetch_detail_single,
                    url,
                    (i % max_workers) + 1,
                    POST_REQUEST_SLEEP_CONCURRENT,
                ): (url, name)
                for i, (url, name) in enumerate(tasks)
            }

            for future in as_completed(future_to_item):
                url, name = future_to_item[future]

                try:
                    result_url, html_content = future.result()

                    if html_content:
                        detail_data = parse_detail(html_content, result_url)
                        if detail_data:
                            print(f"  [PARSE] Title: {detail_data['title'][:50]}...")
                            success_count += 1
                            
                            # 实时保存单条数据
                            with file_lock:
                                save_to_jsonl(detail_data, existing_detail_jsonl, is_single=True)
                    else:
                        failed_count += 1
                        print(f"[FAIL] {url[:80]}...")

                except Exception as e:
                    failed_count += 1
                    print(f"[EXCEPTION] {url[:80]}...: {e}")

    else:
        # === 串行模式 ===
        print(
            f"\n[INFO] 使用串行爬取模式；"
            f"单次请求结束后休眠约 {POST_REQUEST_SLEEP_SERIAL[0]}–{POST_REQUEST_SLEEP_SERIAL[1]} 秒"
        )

        detail_progress = tqdm(pending, desc="详情页抓取", unit="条")
        for i, (url, name) in enumerate(detail_progress, 1):
            detail_progress.set_postfix(success=success_count)
            nu = _canonical_detail_url(url)
            if not nu:
                continue
            if nu in existing_urls:
                continue
            if nu in seen_this_run:
                continue
            seen_this_run.add(nu)

            print(f"\n[{i}/{len(pending)}] {name[:50]}...")

            html_content = fetch_detail(nu)

            if html_content:
                detail_data = parse_detail(html_content, nu)

                if detail_data:
                    print(f"  [PARSE] Title: {detail_data['title'][:50]}...")
                    print(f"  [PARSE] Date: {detail_data['publish_date']}")
                    print(f"  [PARSE] Budget: {detail_data['budget']}")

                    success_count += 1
                    detail_progress.set_postfix(success=success_count)
                    
                    # 实时保存单条数据
                    save_to_jsonl(detail_data, existing_detail_jsonl, is_single=True)

    # 实时保存单条数据
    # if results:
    #     save_to_jsonl(results, existing_detail_jsonl)

    print(f"\n{'='*60}")
    print(f"Done! 成功 {success_count} 条，失败 {failed_count} 条，共处理 {len(pending)} 条")
    print(f"{'='*60}")

    return {
        "success": True,
        "processed": len(pending),
        "success_count": success_count,
        "failed_count": failed_count,
        "json_path": str(existing_detail_jsonl)
    }


def run_crawl_detail(
    limit: int | None = None,
    concurrent: bool = True,
    max_workers: int = CONCURRENT_CHANNELS,
    source_json: str | os.PathLike[str] | None = None,
):
    """包装函数，用于工作流调用。limit 为 None 时爬取列表与详情 JSON 差集中的全部待爬 URL。"""
    return crawl_details(
        limit=limit,
        source_json=source_json,
        concurrent=concurrent,
        max_workers=max_workers,
    )


def main():
    """CLI：默认不限制条数，爬完 tenders_list 中所有尚未写入 tenders_detail 的详情页。"""
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "从 tenders_list.json 读取详情 URL，爬取尚未出现在 tenders_detail.json 中的页面；"
            "默认不限制数量，直至待爬 URL 全部完成。"
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="本批最多爬取 N 条待爬详情（正整数）；省略或 ≤0 表示不限制",
    )
    parser.add_argument(
        "--serial",
        action="store_true",
        help="串行爬取（单线程）",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=CONCURRENT_CHANNELS,
        help=f"并发通道数（默认 {CONCURRENT_CHANNELS}，--serial 时忽略）",
    )
    parser.add_argument(
        "--list-json",
        type=str,
        default=None,
        metavar="PATH",
        help="列表 JSON 路径（默认使用配置目录下 tenders_list.json）",
    )
    args = parser.parse_args()

    lim: int | None = args.limit
    if lim is not None and lim <= 0:
        lim = None

    list_path = Path(args.list_json).resolve() if args.list_json else None

    crawl_details(
        limit=lim,
        source_json=str(list_path) if list_path else None,
        concurrent=not args.serial,
        max_workers=max(1, int(args.workers)),
    )


if __name__ == "__main__":
    main()
