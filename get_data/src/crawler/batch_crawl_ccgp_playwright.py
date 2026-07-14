#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CCGP批量爬取脚本 - Playwright版
- 列表页爬取（多页）
- 详情页爬取 + 粗匹配
- 匹配结果暂存JSONL，供后续精匹配

使用系统Chromium + DISPLAY=:10（远程桌面可见模式）
"""

import sys, os, time, random, re, json
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

# Playwright
import shutil
from playwright.sync_api import sync_playwright

# 项目路径
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from src.config import CRAWLER_OUTPUT_DIR

# ==================== 配置 ====================

CHROMIUM_PATH = shutil.which('chromium-browser') or '/usr/bin/chromium-browser'
DISPLAY = os.environ.get('DISPLAY', ':10')
ENV = os.environ.copy()
ENV['DISPLAY'] = DISPLAY

# 有效关键词（一年有结果的）
VALID_KEYWORDS = [
    # 核心产品线
    ("人工智能", "ai", "industrial_ai"),
    ("AI", "ai", "industrial_ai"),
    ("机器人", "robot", "industrial_ai"),
    ("智能制造", "smart_mfg", "industrial_5g"),
    ("智能制造设备", "smart_mfg_equip", "industrial_5g"),
    ("卫星通信", "sat_comms", "satellite"),
    ("卫星终端", "sat_term", "satellite"),
    ("专网", "private_net", "private_network"),
    ("5G专网", "5g_pnet", "industrial_5g"),
    ("边缘计算", "edge", "industrial_5g"),
    # 场景词
    ("无人机", "uav", "scene"),
    ("应急救援", "em_rescue", "scene"),
    ("通信保障", "comms_support", "scene"),
    ("森林防火", "forest_fire", "scene"),
    ("抢险救援", "rescue", "scene"),
    ("应急指挥", "em_command", "scene"),
    ("低功耗蓝牙", "ble", "sparklink_ref"),
    # 大量监控词（粗匹配过滤）
    ("应急", "emergency", "monitor"),
    ("消防", "fire", "monitor"),
    ("救援", "rescue_all", "monitor"),
    ("管控", "control", "monitor"),
    ("视频监控", "video_monitor", "monitor"),
    ("人工智能", "ai2", "monitor"),
    ("智能", "smart", "monitor"),
    ("无线电", "radio", "monitor"),
    ("干扰", "jamming", "monitor"),
    ("屏蔽", "shielding", "monitor"),
]

# 粗匹配关键词（详情页内容中出现即匹配）
ROUGH_MATCH_TERMS = {
    # 卫星移动通信
    "satellite": [
        "卫星通信", "卫星终端", "天通", "北斗", "卫星电话",
        "卫星物联网", "卫星移动通信", "高通量卫星", "卫星互联网",
        "卫星传输", "卫星设备", "船载卫星", "船载终端", "卫星系统",
        "卫星应急", "卫星宽带"
    ],
    # 工业5G/AI/机器人
    "industrial_5g": [
        "5G专网", "工业5G", "5G通信", "5G应用", "5G模组",
        "边缘计算", "边缘智能", "MEC", "工业互联网", "工业物联网",
        "专网通信", "专网设备", "5G工业"
    ],
    "industrial_ai": [
        "人工智能", "AI机器人", "智能制造", "工业机器人",
        "服务机器人", "特种机器人", "人形机器人", "机械臂",
        "机器视觉", "深度学习", "神经网络", "无人系统",
        "智能装备", "智能终端", "智慧工厂", "智能仓储"
    ],
    # 星闪短距
    "sparklink": [
        "星闪", "短距通信", "近场通信", "近距离无线",
        "无线近距离", "局域网通信", "SLE", "SparkLink"
    ],
    # 场景/应用
    "scene": [
        "应急通信", "应急指挥", "应急救援", "灾害预警", "森林防火",
        "抢险救援", "通信保障", "消防装备", "无人机", "无人系统",
        "边防巡逻", "海防", "电力通信", "电网通信", "专网通信"
    ]
}

# 输出目录
OUTPUT_DIR = Path(CRAWLER_OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
HTML_DIR = OUTPUT_DIR / "html"
HTML_DIR.mkdir(parents=True, exist_ok=True)

DATE_START = "2025:05:14"
DATE_END = "2026:05:14"

# timeType含义：
# 0=? 1=? 2=近一周(忽略日期) 3=? 4=? 5=? 6=自定义日期(完整结果)
# bidType: 0=全部 3=货物类
# 日期格式必须用冒号: 2025:05:14，不能用连字符 2025-05-14
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

def extract_list_count(content: str) -> str:
    """从列表页提取总数"""
    for pat in [r'共找到\s*<[^>]*>(\d+)<[^>]*>\s*条', r'共找到\s*(\d+)\s*条']:
        m = re.search(pat, content)
        if m:
            return m.group(1)
    return "0"

def extract_detail_urls(content: str) -> list:
    """从列表页提取所有详情URL"""
    urls = re.findall(r'href="(http://www\.ccgp\.gov\.cn/[^"]+)"', content)
    seen = set()
    result = []
    for u in urls:
        u = u.strip()
        if u and u not in seen and ('cgzx' in u or 'zxgg' in u or 'cggg' in u):
            seen.add(u)
            result.append(u)
    return result

def rough_match(content: str, category_hint: str = "") -> dict:
    """
    粗匹配v3：检测详情页是否包含产品相关关键词
    - 排除页眉页脚导航
    - 排除地址行（含"大厦/路/街/号"且含产品词的行，视为地址而非产品）
    - 标题命中优先；正文匹配次之
    - 只要有1个term命中就入库（防止错过隐藏商机）
    """
    title_m = re.search(r'<title>([^<]+)</title>', content)
    title = title_m.group(1).strip() if title_m else ""

    # 提取正文（去除脚本和样式）
    text = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # 定位正文区域（从"采购需求"之后开始）
    body_start = text.find('采购需求')
    if body_start == -1:
        body_start = text.find('技术需求')
    if body_start == -1:
        body_start = text.find('招标公告')
    body_text = text[body_start:body_start + 3000] if body_start != -1 else text[:3000]

    # 强过滤：含地址关键词且含产品词的行视为地址而非产品
    addr_kw = ['地址：', '地址:', '大厦', '大楼', '路', '街', '号', '室', '层']
    lines = body_text.split('　')  # 全角空格分隔
    filtered_lines = []
    for line in lines:
        line = line.strip()
        if any(k in line for k in addr_kw):
            if any(t in line for terms in ROUGH_MATCH_TERMS.values() for t in terms):
                continue  # 跳过地址行
        filtered_lines.append(line)
    body_text = ' '.join(filtered_lines)

    # 过滤页脚导航
    for kw in ['服务热线', '服务投诉', '400-810', '010-638', '京ICP备',
               '京公网安', '国家级政府采购', '中国政府采购网']:
        body_text = re.sub(kw + r'[^\n]{0,50}', '', body_text)

    matched_cats = []
    matched_terms = []

    for cat, terms in ROUGH_MATCH_TERMS.items():
        for term in terms:
            if term in title:
                matched_cats.append(cat)
                matched_terms.append(term)
            elif term in body_text:
                matched_cats.append(cat)
                matched_terms.append(term)

    matched_cats = list(dict.fromkeys(matched_cats))
    matched_terms = list(dict.fromkeys(matched_terms))

    return {
        "matched": len(matched_terms) > 0,
        "matched_categories": matched_cats,
        "matched_terms": matched_terms
    }

def extract_detail_content(page) -> dict:
    """从详情页提取结构化内容"""
    content = page.content()

    # 提取标题
    title = ""
    title_match = re.search(r'<title>([^<]+)</title>', content)
    if title_match:
        title = re.sub(r'\s+', ' ', title_match.group(1)).strip()

    # 提取采购单位
    buyer = ""
    buyer_match = re.search(r'采购人[：:]\s*([^<\n\r]{2,50})', content)
    if buyer_match:
        buyer = buyer_match.group(1).strip()

    # 提取金额
    amount = ""
    amount_match = re.search(r'预算金额[：:]\s*([^\n\r<]{5,80})', content)
    if amount_match:
        amount = amount_match.group(1).strip()

    # 提取日期
    date = ""
    date_match = re.search(r'发布日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})', content)
    if date_match:
        date = date_match.group(1).strip()

    # 提取正文（简化版）
    body = re.sub(r'<[^>]+>', ' ', content)
    body = re.sub(r'\s+', ' ', body).strip()
    # 取前3000字
    body = body[:3000]

    return {
        "title": title,
        "buyer": buyer,
        "amount": amount,
        "date": date,
        "body_preview": body
    }

# ==================== 主流程 ====================

def is_rate_limited(content: str) -> bool:
    """检测是否被限流（页面返回异常内容）"""
    if not content:
        return True
    # 限流特征
    if any(k in content for k in ['请输入验证码', '访问频率', '系统繁忙', '操作过于频繁', 'Too Many Requests', '403 Forbidden']):
        return True
    # 有效页面必须有结果统计
    if '共找到' not in content and '条' not in content:
        return True
    return False

def crawl_keyword(keyword: str, tag: str, category: str, browser, max_pages: int = 5):
    """爬取单个关键词，返回匹配的详情记录列表"""
    print(f"\n{'='*60}")
    print(f"关键词: {keyword} ({category})")

    all_urls = []
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
                # 用load等待更充分，不用domcontentloaded
                p.goto(url, timeout=30000, wait_until='load')
                time.sleep(random.uniform(4, 6))

                content = p.content()

                # 限流检测
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
                    print(f"  总数: {total_count} 条 (timeType={TIME_TYPE})")

                urls = extract_detail_urls(content)
                print(f"  第{page}页: 提取到 {len(urls)} 个URL")

                # 限流或空页就停止
                if len(urls) == 0:
                    p.close()
                    break

                all_urls.extend(urls)
                p.close()
                # 页间等待，随时间Type=4后URL增多，等待要更充分
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

    # 去重
    all_urls = list(dict.fromkeys(all_urls))
    print(f"  共提取 {len(all_urls)} 个详情URL")

    if not all_urls:
        return []

    # ---- 详情页爬取 + 粗匹配 ----
    matched_records = []
    for i, detail_url in enumerate(all_urls):
        success = False
        retry = 0

        while retry < 3 and not success:
            try:
                p = browser.new_page(viewport={"width": 1280, "height": 720})
                p.goto(detail_url, timeout=30000, wait_until='load')
                time.sleep(random.uniform(3, 5))

                content = p.content()

                # 限流检测
                if is_rate_limited(content):
                    print(f"  ⚠️ [{i+1}/{len(all_urls)}] 详情页被限流，等待60秒后重试 ({retry+1}/3)")
                    p.close()
                    time.sleep(60)
                    retry += 1
                    continue

                detail = extract_detail_content(p)

                # 粗匹配
                match_result = rough_match(content, category)

                record = {
                    "keyword_searched": keyword,
                    "category": category,
                    "url": detail_url,
                    "title": detail['title'],
                    "buyer": detail['buyer'],
                    "amount": detail['amount'],
                    "date": detail['date'],
                    "matched": match_result['matched'],
                    "matched_categories": match_result['matched_categories'],
                    "matched_terms": match_result['matched_terms'],
                    "crawl_time": datetime.now().isoformat(),
                }

                if match_result['matched']:
                    matched_records.append(record)
                    icon = "✅"
                else:
                    icon = "⚪"

                print(f"  {icon} [{i+1}/{len(all_urls)}] {detail['title'][:50] if detail['title'] else detail_url}")
                if match_result['matched']:
                    print(f"      命中: {match_result['matched_terms']}")

                p.close()
                time.sleep(random.uniform(2, 4))
                success = True

            except Exception as e:
                print(f"  ❌ [{i+1}/{len(all_urls)}] 详情页失败(重试{retry+1}/3): {str(e)[:60]}")
                try:
                    p.close()
                except:
                    pass
                time.sleep(15)
                retry += 1
                if retry >= 3:
                    print(f"  跳过该详情页")

    print(f"  匹配入库: {len(matched_records)} 条")
    return matched_records

def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = OUTPUT_DIR / f"ccgp_matched_{timestamp}.jsonl"
    all_records = []

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
    print(f"总匹配入库: {len(all_records)} 条")
    print(f"输出文件: {output_file}")

    # 分类统计
    cat_count = {}
    for r in all_records:
        for c in r['matched_categories']:
            cat_count[c] = cat_count.get(c, 0) + 1
    print(f"\n按类别统计:")
    for c, n in sorted(cat_count.items(), key=lambda x: -x[1]):
        print(f"  {c}: {n} 条")

    return output_file, all_records

if __name__ == '__main__':
    main()
