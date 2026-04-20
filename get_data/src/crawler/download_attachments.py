# -*- coding: utf-8 -*-
"""
下载招标公告附件
从 tender_attachments 表或 JSON 文件读取附件链接，下载到本地 attachments 目录
"""

import sqlite3
import os
import sys
import json
import time
import random
import hashlib
import re
from urllib.parse import unquote

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH, ATTACHMENT_DIR
from src.utils.jsonl_helper import load_jsonl

# 尝试导入 curl_cffi.requests，如果不存在则使用 requests
try:
    from curl_cffi import requests
except ImportError:
    import requests

# 附件保存目录（从配置读取）
ATTACHMENTS_DIR = ATTACHMENT_DIR
os.makedirs(ATTACHMENTS_DIR, exist_ok=True)

# 下载配置
DOWNLOAD_CONFIG = {
    "timeout": 60,
    "delay_min": 1,
    "delay_max": 3,
    "max_retries": 3,
}


def get_safe_filename(filename):
    """生成安全的文件名，去除非法字符"""
    # 去除非法字符
    illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in illegal_chars:
        filename = filename.replace(char, '_')
    # 限制长度
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext
    return filename.strip()


def extract_filename_from_url(url):
    """从 URL 中提取文件名"""
    # 先 URL 解码
    decoded = unquote(url)
    # 提取最后一个/之后的部分
    filename = decoded.split('/')[-1]
    # 如果有查询参数，去掉
    if '?' in filename:
        filename = filename.split('?')[0]
    # 如果是 uuid 参数，尝试从 URL 中提取
    if not filename or filename == 'download':
        match = re.search(r'uuid=([0-9A-Fa-f]+)', url)
        if match:
            filename = f"attachment_{match.group(1)}.pdf"
    return get_safe_filename(filename) if filename else "unknown.pdf"


def generate_file_path(tender_id, file_name, url):
    """生成文件保存路径"""
    # 按 tender_id 分目录保存
    tender_dir = os.path.join(ATTACHMENTS_DIR, str(tender_id))
    os.makedirs(tender_dir, exist_ok=True)

    # 生成安全的文件名
    safe_name = extract_filename_from_url(url) if not file_name else get_safe_filename(file_name)

    # 如果文件名太简单，添加 URL 哈希
    if len(safe_name) < 10:
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        name, ext = os.path.splitext(safe_name)
        safe_name = f"{name}_{url_hash}{ext}"

    return os.path.join(tender_dir, safe_name)


def download_file(url, save_path, max_retries=3):
    """下载文件"""
    for attempt in range(max_retries):
        try:
            print(f"  [DOWNLOAD] {url[:80]}...")
            r = requests.get(url, timeout=DOWNLOAD_CONFIG["timeout"])

            if r.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(r.content)
                file_size = len(r.content)
                print(f"  [OK] Saved: {save_path} ({file_size} bytes)")
                return True, file_size
            else:
                print(f"  [FAIL] Status: {r.status_code}")

        except Exception as e:
            print(f"  [ERROR] Attempt {attempt + 1}/{max_retries}: {e}")
            time.sleep(2 ** attempt)  # 指数退避

    return False, 0


def load_attachments_from_db():
    """从数据库加载附件列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查表是否存在
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='tender_attachments'
    """)

    if not cursor.fetchone():
        print("[WARN] tender_attachments 表不存在")
        conn.close()
        return []

    cursor.execute("""
        SELECT id, tender_id, file_name, download_url, uuid
        FROM tender_attachments
        WHERE download_url IS NOT NULL
    """)

    rows = cursor.fetchall()
    conn.close()

    attachments = []
    for row in rows:
        attachments.append({
            "id": row[0],
            "tender_id": row[1],
            "file_name": row[2],
            "download_url": row[3],
            "uuid": row[4]
        })

    return attachments


def load_attachments_from_jsonl(jsonl_path):
    """从 JSONL 文件加载附件列表"""
    if not os.path.exists(jsonl_path):
        print(f"[ERROR] JSONL 文件不存在：{jsonl_path}")
        return []

    data = load_jsonl(str(jsonl_path))

    print(f"[INFO] 从 JSONL 加载 {len(data)} 条附件")
    return data


def check_downloaded(save_path):
    """检查文件是否已下载"""
    if os.path.exists(save_path):
        file_size = os.path.getsize(save_path)
        if file_size > 0:
            print(f"  [SKIP] Already exists: {save_path} ({file_size} bytes)")
            return True
    return False


def download_all_attachments(jsonl_path=None, use_db=True):
    """批量下载所有附件"""
    # 加载附件列表
    if jsonl_path:
        attachments = load_attachments_from_jsonl(jsonl_path)
    elif use_db:
        attachments = load_attachments_from_db()
    else:
        print("[ERROR] 请指定 JSON 文件或使用 --db 参数")
        return

    if not attachments:
        print("[INFO] 无附件可下载")
        return

    print(f"\n{'='*60}")
    print(f"开始下载附件，共 {len(attachments)} 个")
    print(f"{'='*60}\n")

    stats = {
        'total': len(attachments),
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'total_bytes': 0
    }

    for idx, att in enumerate(attachments, 1):
        tender_id = att.get('tender_id', 'unknown')
        file_name = att.get('file_name', '')
        url = att.get('download_url', '')

        if not url:
            print(f"[{idx}/{len(attachments)}] [SKIP] No URL")
            stats['skipped'] += 1
            continue

        print(f"\n[{idx}/{len(attachments)}] Tender ID: {tender_id}")
        print(f"  File: {file_name[:60]}...")
        print(f"  URL: {url[:80]}...")

        # 生成保存路径
        save_path = generate_file_path(tender_id, file_name, url)

        # 检查是否已下载
        if check_downloaded(save_path):
            stats['skipped'] += 1
            continue

        # 下载
        success, file_size = download_file(url, save_path)

        if success:
            stats['success'] += 1
            stats['total_bytes'] += file_size

            # 更新数据库状态（如果从数据库加载）
            if use_db and att.get('id'):
                update_attachment_status(att['id'], save_path, file_size)
        else:
            stats['failed'] += 1

        # 随机延迟
        if idx < len(attachments):
            delay = random.uniform(DOWNLOAD_CONFIG["delay_min"], DOWNLOAD_CONFIG["delay_max"])
            time.sleep(delay)

    # 打印统计
    print(f"\n{'='*60}")
    print("下载完成!")
    print(f"{'='*60}")
    print(f"总数：{stats['total']}")
    print(f"成功：{stats['success']}")
    print(f"失败：{stats['failed']}")
    print(f"跳过：{stats['skipped']}")
    print(f"总大小：{stats['total_bytes'] / 1024 / 1024:.2f} MB")
    print(f"{'='*60}")


def update_attachment_status(att_id, save_path, file_size):
    """更新附件下载状态"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 添加新字段（如果不存在）
    try:
        cursor.execute("ALTER TABLE tender_attachments ADD COLUMN local_path TEXT")
        cursor.execute("ALTER TABLE tender_attachments ADD COLUMN file_size INTEGER")
        cursor.execute("ALTER TABLE tender_attachments ADD COLUMN download_status TEXT DEFAULT 'pending'")
        conn.commit()
    except Exception:
        pass  # 字段可能已存在

    cursor.execute("""
        UPDATE tender_attachments
        SET local_path = ?,
            file_size = ?,
            download_status = 'downloaded'
        WHERE id = ?
    """, (save_path, file_size, att_id))

    conn.commit()
    conn.close()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='下载招标公告附件')
    parser.add_argument('--jsonl', type=str, help='JSONL 文件路径')
    parser.add_argument('--db', action='store_true', help='从数据库加载（默认）')
    parser.add_argument('--no-db', action='store_true', help='不从数据库加载')

    args = parser.parse_args()

    use_db = args.db or (not args.jsonl and not args.no_db)

    download_all_attachments(
        jsonl_path=args.jsonl,
        use_db=use_db
    )


if __name__ == "__main__":
    import re  # 在模块级别导入
    main()
