#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CCGP批量爬取脚本 v2
- 列表页爬取（多页）提取：URL、公告名称、时间、采购人、代理机构、类型、地区
- 详情页爬取提取：完整结构化字段
- 列表页数据与详情页数据绑定
- JSONL暂存

使用系统Chromium + DISPLAY=:10（远程桌面可见模式）
"""

import sys, os, time, random, re, json
from pathlib import Path
from datetime import datetime
from urllib.parse import quote, urlparse
import shutil

from playwright.sync_api import sync_playwright

# 项目路径
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from src.config import CRAWLER_OUTPUT_DIR

# ==================== 配置 ====================

CHROMIUM_PATH = shutil.which('chromium-browser') or '/usr/bin/chromium-browser'
DISPLAY_ENV = os.environ.get('DISPLAY', ':10')
ENV = os.environ.copy()
ENV['DISPLAY'] = DISPLAY_ENV

# 27个推荐关键词（综合评分>=5.0）
VALID_KEYWORDS = [
    # 卫星通信（4个有效）
    ("应急救援设备", "em_rescue_equip", "satellite"),
    ("卫星通信", "sat_comms", "satellite"),
    ("应急通信", "em_comms", "satellite"),
    ("卫星电话", "sat_phone", "satellite"),
    # 工业5G/AI（9个有效）
    ("机器人", "robot", "industrial_ai"),
    ("人工智能", "ai", "industrial_ai"),
    ("AI", "ai_short", "industrial_ai"),
    ("专网", "private_net", "industrial_5g"),
    ("智能制造", "smart_mfg", "industrial_5g"),
    ("边缘计算", "edge", "industrial_5g"),
    ("智能终端", "smart_term", "industrial_5g"),
    ("具身智能", "embodied_ai", "industrial_ai"),
    ("工业互联网", "iiot", "industrial_5g"),
    # 应急通信场景（11个有效）
    ("应急救援", "em_rescue", "scene"),
    ("应急", "emergency", "monitor"),
    ("消防", "fire", "monitor"),
    ("救援", "rescue", "monitor"),
    ("森林防火", "forest_fire", "scene"),
    ("无人机", "uav", "scene"),
    ("物联网", "iot", "scene"),
    ("管控", "管控", "monitor"),
    ("视频监控", "video_monitor", "monitor"),
    ("应急指挥", "em_command", "scene"),
    ("无线电", "radio", "monitor"),
    ("屏蔽", "shielding", "monitor"),
    ("通信保障", "comms_support", "scene"),
    ("抢险救援", "rescue_op", "scene"),
    ("工业5G", "industrial_5g_kw", "industrial_5g"),
    ("5G专网", "5g_pnet", "industrial_5g"),
    ("无线投屏", "wireless_display", "sparklink"),
]

# 输出目录
OUTPUT_DIR = Path(CRAWLER_OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DATE_START = "2025:05:14"
DATE_END = "2026:05:14"
TIME_TYPE = "6"
BID_TYPE = "3"

# ==================== 工具函数 ====================

def launch_browser(p):
    return p.chromium.launch(
        executable_path=CHROMIUM_PATH,
        headless=False,
        env=ENV,
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--disable-web-security']
    )

def search_url(keyword: str, page: int = 1) -> str:
    kw = quote(keyword)
    return (
        f"http://search.ccgp.gov.cn/bxsearch?"
        f"searchtype=2&page_index={page}&bidSort=0&buyerName=&projectId=&pinMu=0"
        f"&bidType={BID_TYPE}&dbselect=bidx&kw={kw}"
        f"&start_time={DATE_START}&end_time={DATE_END}&timeType={TIME_TYPE}"
        f"&displayZone=&zoneId=&pppStatus=0&agentName="
    )

def is_rate_limited(content: str) -> bool:
    if not content:
        return True
    if any(k in content for k in ['请输入验证码', '访问频率', '系统繁忙', '操作过于频繁', 'Too Many Requests', '403 Forbidden']):
        return True
    if '共找到' not in content and '条' not in content:
        return True
    return False

def extract_list_count(content: str) -> str:
    for pat in [r'共找到\s*<[^>]*>(\d+)<[^>]*>\s*条', r'共找到\s*(\d+)\s*条']:
        m = re.search(pat, content)
        if m:
            return m.group(1)
    return "0"

def extract_list_items(content: str) -> list:
    """
    从列表页提取所有记录（vT-srch-result-list-bid 结构）
    每条记录包含: url, title, pub_date, buyer, agency, type, region
    """
    items = []

    # 找到列表区域 <ul class="vT-srch-result-list-bid">
    pos = content.find('vT-srch-result-list-bid')
    if pos == -1:
        return items
    end_pos = content.find('</ul>', pos)
    segment = content[pos:end_pos]

    # 提取所有 <li> 项
    lis = re.findall(r'<li>(.*?)</li>', segment, re.DOTALL)

    for li in lis:
        # 提取URL
        url_m = re.search(r'href="(http://www\.ccgp\.gov\.cn[^"]+)"', li)
        if not url_m:
            continue
        detail_url = url_m.group(1).strip()

        # 提取标题（从<a>中）
        title_m = re.search(r'target="_blank">\s*\n?\s*([^\n<]+)', li)
        title = title_m.group(1).strip() if title_m else ""
        title = re.sub(r'<[^>]+>', '', title).strip()

        # 从<span>块提取其他字段
        span_m = re.search(r'<span[^>]*>(.*?)</span>', li, re.DOTALL)
        if span_m:
            span = span_m.group(1)

            # 日期
            date_m = re.search(r'(\d{4}[./]\d{2}[./]\d{2}\s*\d{2}:\d{2}:\d{2})', span)
            pub_date = date_m.group(1).strip() if date_m else ""

            # 采购人
            buyer_m = re.search(r'采购人[：:]\s*([^<\n|]+)', span)
            buyer = buyer_m.group(1).strip() if buyer_m else ""

            # 代理机构
            agency_m = re.search(r'代理机构[：:]\s*([^<\n|]+)', span)
            agency = agency_m.group(1).strip() if agency_m else ""

            # 公告类型
            type_m = re.search(r'<strong[^>]*>\s*([^<]+)', span)
            ann_type = type_m.group(1).strip() if type_m else ""

            # 地区
            region_m = re.search(r'</strong>\s*[|\s]*([^\n<]+)', span)
            region = region_m.group(1).strip() if region_m else ""
        else:
            pub_date = buyer = agency = ann_type = region = ""

        if detail_url:
            items.append({
                "list_url": detail_url,
                "title": title,
                "pub_date": pub_date,
                "buyer": buyer,
                "agency": agency,
                "ann_type": ann_type,
                "region": region
            })

    return items

def extract_detail_content(page) -> dict:
    """从详情页提取结构化内容"""
    content = page.content()

    title = ""
    title_m = re.search(r'<title>([^<]+)</title>', content)
    if title_m:
        title = re.sub(r'\s+', ' ', title_m.group(1)).strip()

    # 采购人
    buyer = ""
    for pat in [
        r'采购人[：:]\s*([^<\n\r]{2,60})',
        r'采购单位[：:]\s*([^<\n\r]{2,60})',
        r'采购单位名称[：:]\s*([^<\n\r]{2,60})',
    ]:
        m = re.search(pat, content)
        if m:
            buyer = m.group(1).strip()
            break

    # 代理机构
    agency = ""
    for pat in [
        r'代理机构[：:]\s*([^<\n\r]{2,80})',
        r'代理公司[：:]\s*([^<\n\r]{2,80})',
        r'受托单位[：:]\s*([^<\n\r]{2,80})',
    ]:
        m = re.search(pat, content)
        if m:
            agency = m.group(1).strip()
            break

    # 预算金额
    amount = ""
    for pat in [
        r'预算金额[：:]\s*([^\n\r<]{5,100})',
        r'采购预算[：:]\s*([^\n\r<]{5,100})',
        r'最高限价[：:]\s*([^\n\r<]{5,100})',
        r'项目预算[：:]\s*([^\n\r<]{5,100})',
    ]:
        m = re.search(pat, content)
        if m:
            amount = m.group(1).strip()
            break

    # 发布日期
    date = ""
    for pat in [
        r'发布日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
        r'公告日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
        r'发布时间[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
    ]:
        m = re.search(pat, content)
        if m:
            date = m.group(1).strip()
            break

    # 地区
    region = ""
    for pat in [
        r'地区[：:]\s*([^<\n\r]{2,30})',
        r'所在地区[：:]\s*([^<\n\r]{2,30})',
        r'采购地区[：:]\s*([^<\n\r]{2,30})',
    ]:
        m = re.search(pat, content)
        if m:
            region = m.group(1).strip()
            break

    # 采购需求正文
    body = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
    body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL)
    body = re.sub(r'<[^>]+>', ' ', body)
    body = re.sub(r'\s+', ' ', body).strip()

    # 定位正文区域（从采购需求/技术需求/招标公告之后）
    body_start = max(body.find('采购需求'), body.find('技术需求'), body.find('招标公告'), body.find('采购内容'))
    body_text = body[body_start:body_start + 5000] if body_start != -1 else body[:5000]

    # 采购类型
    ann_type = ""
    if any(k in content for k in ['单一来源', '单一来源采购']):
        ann_type = "单一来源"
    elif any(k in content for k in ['竞争性磋商', '竞争性磋商采购']):
        ann_type = "竞争性磋商"
    elif any(k in content for k in ['竞争性谈判', '竞争性谈判采购']):
        ann_type = "竞争性谈判"
    elif any(k in content for k in ['公开招标', '公开招标采购']):
        ann_type = "公开招标"
    elif any(k in content for k in ['询价采购', '询价公告']):
        ann_type = "询价采购"
    elif any(k in content for k in ['变更公告', '更正公告']):
        ann_type = "变更公告"
    elif any(k in content for k in ['结果公告', '中标公告', '成交公告']):
        ann_type = "结果公告"

    return {
        "detail_title": title,
        "detail_buyer": buyer,
        "detail_agency": agency,
        "detail_amount": amount,
        "detail_date": date,
        "detail_region": region,
        "detail_type": ann_type,
        "detail_body": body_text
    }

# ==================== 主流程 ====================

def crawl_keyword(keyword: str, tag: str, category: str, browser, max_pages: int = 5):
    """爬取单个关键词，返回完整记录列表"""
    print(f"\n{'='*60}")
    print(f"关键词: {keyword} ({category})")

    all_list_items = []
    total_count = "?"
    rate_limit_count = 0

    # ---- 列表页爬取 ----
    for page in range(1, max_pages + 1):
        url = search_url(keyword, page)
        retry = 0
        success = False

        while retry < 3 and not success:
            try:
                p = browser.new_page(viewport={"width": 1280, "height": 720})
                p.goto(url, timeout=30000, wait_until='load')
                time.sleep(random.uniform(4, 6))

                content = p.content()

                if is_rate_limited(content):
                    print(f"  ⚠️ 第{page}页被限流，等待60秒后重试 ({retry+1}/3)")
                    p.close()
                    time.sleep(60)
                    retry += 1
                    rate_limit_count += 1
                    if rate_limit_count >= 3:
                        print(f"  已连续3次限流，跳过该关键词")
                        return []
                    continue

                success = True

                if page == 1:
                    total_count = extract_list_count(content)
                    print(f"  总数: {total_count} 条 (timeType={TIME_TYPE}, bidType={BID_TYPE})")

                list_items = extract_list_items(content)
                print(f"  第{page}页: 提取到 {len(list_items)} 条记录")

                if len(list_items) == 0:
                    p.close()
                    break

                all_list_items.extend(list_items)
                p.close()
                time.sleep(random.uniform(3, 5))

            except Exception as e:
                print(f"  第{page}页失败(重试{retry+1}/3): {str(e)[:60]}")
                try:
                    p.close()
                except:
                    pass
                time.sleep(15)
                retry += 1
                if retry >= 3:
                    break

        if not success and retry >= 3:
            break

    # 去重（按URL）
    seen_urls = set()
    unique_items = []
    for item in all_list_items:
        if item['list_url'] not in seen_urls:
            seen_urls.add(item['list_url'])
            unique_items.append(item)
    all_list_items = unique_items

    print(f"  去重后共 {len(all_list_items)} 个详情URL")

    if not all_list_items:
        return []

    # ---- 详情页爬取 ----
    matched_records = []
    for i, item in enumerate(all_list_items):
        success = False
        retry = 0

        while retry < 3 and not success:
            try:
                p = browser.new_page(viewport={"width": 1280, "height": 720})
                p.goto(item['list_url'], timeout=30000, wait_until='load')
                time.sleep(random.uniform(3, 5))

                content = p.content()

                if is_rate_limited(content):
                    print(f"  ⚠️ [{i+1}/{len(all_list_items)}] 详情页被限流，等待60秒后重试 ({retry+1}/3)")
                    p.close()
                    time.sleep(60)
                    retry += 1
                    continue

                detail = extract_detail_content(p)

                # 合并列表页数据 + 详情页数据
                record = {
                    # 关键词信息
                    "keyword_searched": keyword,
                    "keyword_tag": tag,
                    "category": category,
                    # 列表页数据
                    "list_url": item['list_url'],
                    "list_title": item['title'],
                    "list_pub_date": item['pub_date'],
                    "list_buyer": item['buyer'],
                    "list_agency": item['agency'],
                    "list_ann_type": item['ann_type'],
                    "list_region": item['region'],
                    # 详情页数据
                    "detail_url": item['list_url'],  # 同URL
                    "detail_title": detail['detail_title'],
                    "detail_buyer": detail['detail_buyer'],
                    "detail_agency": detail['detail_agency'],
                    "detail_amount": detail['detail_amount'],
                    "detail_date": detail['detail_date'],
                    "detail_region": detail['detail_region'],
                    "detail_type": detail['detail_type'],
                    "detail_body_preview": detail['detail_body'][:2000] if detail['detail_body'] else "",
                    # 元信息
                    "crawl_time": datetime.now().isoformat(),
                    # 来源关键词（用于粗匹配）
                    "source_keywords": [keyword]
                }

                matched_records.append(record)

                # 打印摘要
                title_disp = (item['title'] or detail['detail_title'] or item['list_url'])[:50]
                buyer_disp = detail['detail_buyer'] or item['buyer'] or '-'
                print(f"  📄 [{i+1}/{len(all_list_items)}] {title_disp}")
                print(f"      采购人: {buyer_disp} | 金额: {detail['detail_amount'][:40] if detail['detail_amount'] else '-'}")

                p.close()
                time.sleep(random.uniform(2, 4))
                success = True

            except Exception as e:
                print(f"  ❌ [{i+1}/{len(all_list_items)}] 详情页失败(重试{retry+1}/3): {str(e)[:60]}")
                try:
                    p.close()
                except:
                    pass
                time.sleep(15)
                retry += 1
                if retry >= 3:
                    # 即使失败也保留列表页数据
                    record_fail = {
                        "keyword_searched": keyword,
                        "keyword_tag": tag,
                        "category": category,
                        "list_url": item['list_url'],
                        "list_title": item['title'],
                        "list_pub_date": item['pub_date'],
                        "list_buyer": item['buyer'],
                        "list_agency": item['agency'],
                        "list_ann_type": item['ann_type'],
                        "list_region": item['region'],
                        "detail_url": item['list_url'],
                        "detail_title": "",
                        "detail_buyer": "",
                        "detail_agency": "",
                        "detail_amount": "",
                        "detail_date": "",
                        "detail_region": "",
                        "detail_type": "",
                        "detail_body_preview": "",
                        "crawl_time": datetime.now().isoformat(),
                        "source_keywords": [keyword],
                        "detail_error": str(e)[:100]
                    }
                    matched_records.append(record_fail)
                    print(f"  ⚠️ 保留列表页数据（详情页失败）: {item['title'][:40]}")

    print(f"  共爬取: {len(matched_records)} 条")
    return matched_records

def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = OUTPUT_DIR / f"ccgp_v2_{timestamp}.jsonl"
    all_records = []

    print(f"开始批量爬取 {len(VALID_KEYWORDS)} 个关键词...")
    print(f"参数: timeType={TIME_TYPE}, bidType={BID_TYPE}, 日期范围={DATE_START} ~ {DATE_END}")
    print(f"输出: {output_file}")

    with sync_playwright() as p:
        browser = launch_browser(p)

        for keyword, tag, category in VALID_KEYWORDS:
            try:
                records = crawl_keyword(keyword, tag, category, browser, max_pages=5)
                all_records.extend(records)
            except Exception as e:
                print(f"关键词 {keyword} 整体失败: {e}")

        browser.close()

    # 写入JSONL
    with open(output_file, 'w', encoding='utf-8') as f:
        for record in all_records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    print(f"\n\n{'#'*60}")
    print(f"爬取完成！")
    print(f"总记录数: {len(all_records)} 条")
    print(f"输出文件: {output_file}")

    # 按类别统计
    cat_count = {}
    for r in all_records:
        cat = r['category']
        cat_count[cat] = cat_count.get(cat, 0) + 1
    print(f"\n按类别统计:")
    for c, n in sorted(cat_count.items(), key=lambda x: -x[1]):
        print(f"  {c}: {n} 条")

    # 按关键词统计（前10）
    kw_count = {}
    for r in all_records:
        kw = r['keyword_searched']
        kw_count[kw] = kw_count.get(kw, 0) + 1
    print(f"\n按关键词统计(TOP 10):")
    for kw, n in sorted(kw_count.items(), key=lambda x: -x[1])[:10]:
        print(f"  {kw}: {n} 条")

    return output_file, all_records

if __name__ == '__main__':
    main()
