# -*- coding: utf-8 -*-
"""
使用 DeepSeek 大模型解析所有招标详情页
提取结构化信息并保存到数据库
"""

import sqlite3
import json
import sys
import os
import time
import re

# 添加项目根目录和 src 目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)
from config import DB_PATH, DEEPSEEK_CONFIG

# 尝试导入 openai
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("[ERROR] openai 库未安装，请运行：pip install openai")
    sys.exit(1)


def get_deepseek_client():
    """获取 DeepSeek 客户端"""
    api_key = DEEPSEEK_CONFIG.get('api_key')
    base_url = DEEPSEEK_CONFIG.get('base_url')
    model = DEEPSEEK_CONFIG.get('model')
    timeout = DEEPSEEK_CONFIG.get('timeout', 120)

    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)


def extract_page_info(html_content):
    """
    使用 DeepSeek 从详情页 HTML 提取信息

    Args:
        html_content: 详情页 HTML 内容

    Returns:
        dict: 提取的结构化信息
    """
    client = get_deepseek_client()

    # 截取 HTML（避免超出 token 限制）
    max_chars = 25000
    if len(html_content) > max_chars:
        html_content = html_content[:max_chars] + "\n...（内容截断）"

    prompt = f"""你是一个专业的招投标信息抽取专家。请从以下 HTML 内容中提取关键信息。

## 输出要求
1. 必须输出严格的 JSON 格式，不要有任何额外文字
2. 不要猜测，所有字段必须来源于 HTML 文本
3. 如果某字段未提及，设为 null

## 输出 JSON 格式
{{
  "project_name": "项目名称",
  "buyer_name": "采购人/招标单位名称",
  "agency_name": "代理机构名称",
  "budget": "预算金额（如有）",
  "publish_date": "发布日期",
  "contact_info": "联系人及方式",
  "key_requirements": ["关键需求 1", "关键需求 2"],
  "attachment_links": ["附件链接 1", "附件链接 2"]
}}

## HTML 内容
{html_content}

请提取信息并返回 JSON："""

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_CONFIG['model'],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2000
        )

        result = response.choices[0].message.content

        # 提取 JSON
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        else:
            print(f"  [WARN] 未找到 JSON: {result[:100]}")
            return None

    except Exception as e:
        print(f"  [ERROR] LLM 调用失败：{e}")
        return None


def get_pages_to_parse():
    """获取所有需要解析的页面"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查表结构
    cursor.execute("PRAGMA table_info(tenders)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'content' not in columns:
        print("[ERROR] tenders 表没有 content 字段")
        conn.close()
        return []

    # 获取所有有 content 的记录
    cursor.execute("""
        SELECT id, project_name, content
        FROM tenders
        WHERE content IS NOT NULL AND length(content) > 0
    """)

    rows = cursor.fetchall()
    conn.close()

    pages = []
    for row in rows:
        pages.append({
            "id": row[0],
            "project_name": row[1],
            "content": row[2]
        })

    return pages


def save_parsed_data(tender_id, parsed_data):
    """将解析数据保存到 tender_structured 表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 确保表存在
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tender_structured (
            tender_id INTEGER PRIMARY KEY,
            project_name TEXT,
            buyer_name TEXT,
            agency_name TEXT,
            budget TEXT,
            publish_date TEXT,
            contact_info TEXT,
            key_requirements TEXT,
            attachment_links TEXT,
            parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tender_id) REFERENCES tenders(id) ON DELETE CASCADE
        )
    """)

    # 检查是否已存在
    cursor.execute("SELECT 1 FROM tender_structured WHERE tender_id = ?", (tender_id,))
    if cursor.fetchone():
        print("  [SKIP] 已存在")
        conn.close()
        return False

    # 插入数据
    cursor.execute("""
        INSERT INTO tender_structured
        (tender_id, project_name, buyer_name, agency_name, budget,
         publish_date, contact_info, key_requirements, attachment_links)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        tender_id,
        parsed_data.get('project_name', ''),
        parsed_data.get('buyer_name', ''),
        parsed_data.get('agency_name', ''),
        parsed_data.get('budget', ''),
        parsed_data.get('publish_date', ''),
        parsed_data.get('contact_info', ''),
        json.dumps(parsed_data.get('key_requirements', []), ensure_ascii=False),
        json.dumps(parsed_data.get('attachment_links', []), ensure_ascii=False)
    ))

    conn.commit()
    conn.close()
    return True


def parse_all_pages():
    """解析所有页面"""
    if not HAS_OPENAI:
        print("[ERROR] openai 库未安装")
        return

    pages = get_pages_to_parse()

    if not pages:
        print("[INFO] 没有可解析的页面")
        return

    print("=" * 60)
    print(f"使用 DeepSeek 解析详情页，共 {len(pages)} 个")
    print("=" * 60)

    stats = {
        'total': len(pages),
        'success': 0,
        'failed': 0,
        'skipped': 0
    }

    for idx, page in enumerate(pages, 1):
        print(f"\n[{idx}/{len(pages)}] {page['project_name'][:50]}...")

        # 解析 HTML
        parsed = extract_page_info(page['content'])

        if not parsed:
            stats['failed'] += 1
            print("  [FAIL] 解析失败")
            continue

        # 保存数据
        if save_parsed_data(page['id'], parsed):
            stats['success'] += 1
            print(f"  [OK] buyer={parsed.get('buyer_name', 'N/A')}, budget={parsed.get('budget', 'N/A')}")
        else:
            stats['skipped'] += 1

        # 延迟避免限流
        if idx < len(pages):
            time.sleep(1)

    print("\n" + "=" * 60)
    print("解析完成!")
    print("=" * 60)
    print(f"总数：{stats['total']}")
    print(f"成功：{stats['success']}")
    print(f"失败：{stats['failed']}")
    print(f"跳过：{stats['skipped']}")
    print("=" * 60)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='使用 DeepSeek 解析招标详情页')
    parser.add_argument('--all', action='store_true', help='解析所有页面')

    args = parser.parse_args()

    if args.all:
        parse_all_pages()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
