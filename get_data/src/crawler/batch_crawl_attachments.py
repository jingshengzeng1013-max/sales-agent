# -*- coding: utf-8 -*-
"""
批量爬取 tenders 表中所有记录的详情页，提取附件下载链接
结果保存为 JSON 文件
"""

import re
import os
import sys
import json
import time
import random
from urllib.parse import urljoin

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CRAWLER_OUTPUT_DIR

# 输出目录
OUTPUT_DIR = CRAWLER_OUTPUT_DIR
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 尝试导入 curl_cffi.requests，如果不存在则使用 requests
try:
    from curl_cffi import requests
except ImportError:
    import requests


def extract_element_by_id(html, element_id):
    """通过 ID 提取 HTML 元素"""
    pattern = rf'<[^>]*id=["\']{element_id}["\'][^>]*>.*?</[^>]+>'
    match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    return match.group(0) if match else None


def extract_element_by_class(html, class_name):
    """通过 class 提取 HTML 元素"""
    pattern = rf'<[^>]*class=["\'][^"\']*{class_name}[^"\']*["\'][^>]*>.*?</[^>]+>'
    match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    return match.group(0) if match else None


def html_to_clean_text(html):
    """去除 HTML 标签，返回纯文本"""
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def is_attachment_url(url, text=""):
    """判断 URL 是否为附件下载链接"""
    url_lower = url.lower()
    text_lower = text.lower()

    # 常见的附件扩展名
    attachment_extensions = [
        '.pdf', '.doc', '.docx', '.xls', '.xlsx',
        '.zip', '.rar', '.7z', '.tar', '.gz',
        '.txt', '.csv', '.ppt', '.pptx', '.ofd', '.wps'
    ]

    # 检查是否包含附件扩展名
    for ext in attachment_extensions:
        if url_lower.endswith(ext) or text_lower.endswith(ext):
            return True

    # 检查是否是已知的附件下载路径模式
    attachment_patterns = [
        r'/fileApi/',                    # 江苏政府采购网
        r'/oss/download\?',              # 中央政府采购网 (带 uuid 参数)
        r'download\.ccgp\.gov\.cn',      # 中央政府采购网域名
        r'zcy-gov-open-doc',             # 政采云文档
        r'gov-open-doc',                 # 政府开放文档
        r'/TPFrame/.*downAttach',        # 某些交易平台
        r'/WebbuilderMIS/attach/',       # 某些平台
        r'attachGuid=',                  # 某些平台附件参数
        r'/downALoad',                   # 某些平台下载
    ]

    for pattern in attachment_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return True

    return False


def extract_attachment_urls(page_html, page_url):
    """提取详情页中所有附件 URL"""
    attachments = []
    seen = set()

    # 1. 先尝试从 bizDownload 区域提取
    biz_download = extract_element_by_id(page_html, "bizDownload")
    if biz_download:
        for match in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                                  biz_download, re.IGNORECASE | re.DOTALL):
            href = match.group(1)
            text = html_to_clean_text(match.group(2))
            if href and is_attachment_url(href, text):
                full_url = urljoin(page_url, href)
                if full_url not in seen:
                    seen.add(full_url)
                    attachments.append({"url": full_url, "text": text})

    # 2. 从全文提取所有可能的附件链接
    for match in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                              page_html, re.IGNORECASE | re.DOTALL):
        href = match.group(1)
        text = html_to_clean_text(match.group(2))
        if href and is_attachment_url(href, text):
            full_url = urljoin(page_url, href)
            if full_url not in seen:
                seen.add(full_url)
                attachments.append({"url": full_url, "text": text})

    return attachments


def fetch_detail(url):
    """获取详情页 HTML"""
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            return r.text
        else:
            print(f"  [FAIL] Status: {r.status_code}")
            return None
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


def extract_uuid_from_url(url):
    """从 URL 中提取 uuid"""
    match = re.search(r'[?&]uuid=([0-9A-Fa-f]+)', url)
    return match.group(1) if match else None


def load_tenders_from_json(json_path=None):
    """从列表 JSON 文件中加载招标数据"""
    if json_path is None:
        json_path = OUTPUT_DIR / "tenders_list.json"

    if not os.path.exists(json_path):
        print(f"[ERROR] JSON 文件不存在：{json_path}")
        return []

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 返回有 id 和 detail_url 的记录
    result = []
    for idx, item in enumerate(data, 1):
        result.append((idx, item.get('project_name'), item.get('detail_url')))
    return result


def load_existing_json(json_path):
    """加载已有的 JSON 数据"""
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_to_json(results, json_path):
    """保存数据到 JSON 文件"""
    existing = load_existing_json(json_path)
    existing_urls = {item.get('download_url') for item in existing}

    new_count = 0
    for item in results:
        if item.get('download_url') not in existing_urls:
            existing.append(item)
            new_count += 1

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"[JSON] 新增 {new_count} 条，共 {len(existing)} 条")
    print(f"[JSON] 已保存到：{json_path}")
    return new_count


def run_crawl_attachments():
    """
    批量爬取所有 tenders 的附件，保存为 JSON 文件

    Returns:
        dict: 爬取结果统计
    """
    output_json = OUTPUT_DIR / "tenders_attachments.json"
    print(f"[INFO] 输出文件：{output_json}")

    tenders = load_tenders_from_json()
    print(f"[INFO] Found {len(tenders)} tenders with detail_url")

    existing = load_existing_json(output_json)
    existing_urls = {item.get('download_url') for item in existing}
    print(f"[INFO] 已有 {len(existing)} 条附件记录")

    all_attachments = []
    stats = {
        'total': len(tenders),
        'success': 0,
        'failed': 0,
        'total_attachments': 0,
        'new_attachments': 0,
        'skipped': 0
    }

    for idx, (tender_id, project_name, detail_url) in enumerate(tenders, 1):
        print(f"\n[{idx}/{len(tenders)}] {project_name[:50]}...")

        html = fetch_detail(detail_url)
        if not html:
            stats['failed'] += 1
            continue

        stats['success'] += 1
        attachments = extract_attachment_urls(html, detail_url)

        if not attachments:
            print("  [INFO] No attachments found")
            continue

        print(f"  [FOUND] {len(attachments)} attachment(s)")
        stats['total_attachments'] += len(attachments)

        for att in attachments:
            url = att['url']
            file_name = att['text'] if att['text'] else os.path.basename(url)
            uuid = extract_uuid_from_url(url)

            if url in existing_urls:
                stats['skipped'] += 1
                continue

            stats['new_attachments'] += 1
            existing_urls.add(url)
            all_attachments.append({
                'tender_id': tender_id,
                'tender_name': project_name,
                'file_name': file_name,
                'download_url': url,
                'uuid': uuid,
                'source_html_file': detail_url
            })
            print(f"    [NEW] {file_name[:60]}...")

        time.sleep(random.uniform(0.5, 1.5))

    print("\n" + "=" * 60)
    if all_attachments:
        existing.extend(all_attachments)
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        print(f"[JSON] 新增 {len(all_attachments)} 条，共 {len(existing)} 条")
        print(f"[JSON] 已保存到：{output_json}")
    else:
        print("[JSON] 无新增数据")

    print("\n" + "=" * 60)
    print(f"成功：{stats['success']}, 失败：{stats['failed']}")
    print(f"新增附件：{stats['new_attachments']}")
    print("=" * 60)

    return {
        "success": True,
        "stats": stats,
        "json_path": str(output_json)
    }


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='批量爬取招标公告附件')
    parser.add_argument('--file', type=str, help='JSON 文件路径')

    args = parser.parse_args()

    run_crawl_attachments()


if __name__ == "__main__":
    main()
