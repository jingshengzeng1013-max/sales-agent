# -*- coding: utf-8 -*-
"""
招标公告入库模块
将爬取的 JSON 数据导入 SQLite tenders 表
"""

import sys
import os
import sqlite3
import json
from pathlib import Path

# 将项目根目录添加到 sys.path，解决直接运行脚本时的导入问题
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from src.config import DB_PATH, CRAWLER_OUTPUT_DIR
from src.utils.jsonl_helper import load_jsonl

import uuid

def init_database():
    """初始化 SQLite 数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tenders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE,
            project_name TEXT NOT NULL,
            publish_date TEXT,
            detail_url TEXT UNIQUE,
            content TEXT,
            buyer_name TEXT,
            agency_name TEXT,
            budget TEXT,
            attachment_urls TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 检查并添加缺失的列 (如果表已存在但结构旧)
    cursor.execute("PRAGMA table_info(tenders)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'uuid' not in columns:
        cursor.execute("ALTER TABLE tenders ADD COLUMN uuid TEXT")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tenders_uuid ON tenders(uuid)")
    if 'agency_name' not in columns:
        cursor.execute("ALTER TABLE tenders ADD COLUMN agency_name TEXT")
    if 'budget' not in columns:
        cursor.execute("ALTER TABLE tenders ADD COLUMN budget TEXT")
    
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_tenders_url ON tenders(detail_url)')

    conn.commit()
    conn.close()
    print(f"[DB] 数据库初始化完成：{DB_PATH}")


def import_tenders_from_jsonl(jsonl_path=None):
    """
    从 JSONL 文件导入招标列表数据到 tenders 表
    """
    if jsonl_path is None:
        jsonl_path = CRAWLER_OUTPUT_DIR / "tenders_list.jsonl"

    jsonl_path = Path(jsonl_path)
    if not jsonl_path.exists():
        print(f"[ERROR] JSONL 文件不存在：{jsonl_path}")
        return {"success": False, "error": "文件不存在", "inserted": 0, "skipped": 0}

    print("=" * 60)
    print(f"从 JSONL 导入招标列表：{jsonl_path}")
    print("=" * 60)

    data = load_jsonl(str(jsonl_path))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 获取已存在的 URL
    cursor.execute("SELECT detail_url FROM tenders")
    existing_urls = {row[0] for row in cursor.fetchall() if row[0]}

    inserted = 0
    skipped = 0

    for item in data:
        url = item.get('detail_url', '')
        if not url:
            continue
            
        if url in existing_urls:
            skipped += 1
            continue

        cursor.execute("""
            INSERT INTO tenders (uuid, project_name, detail_url, content, status)
            VALUES (?, ?, ?, ?, 'new')
        """, (
            str(uuid.uuid4()),
            item.get('project_name', ''),
            url,
            item.get('content', ''),
        ))
        inserted += 1
        existing_urls.add(url)

    conn.commit()
    conn.close()

    print(f"[DB] 插入 {inserted} 条，跳过 {skipped} 条")
    print(f"[DB] 已写入：{DB_PATH}")

    return {"success": True, "inserted": inserted, "skipped": skipped}


def update_tender_details_from_jsonl(jsonl_path=None):
    """
    从 JSONL 文件更新招标详情数据到 tenders 表
    """
    if jsonl_path is None:
        jsonl_path = CRAWLER_OUTPUT_DIR / "tenders_detail.jsonl"

    jsonl_path = Path(jsonl_path)
    if not jsonl_path.exists():
        print(f"[ERROR] JSONL 文件不存在：{jsonl_path}")
        return {"success": False, "error": "文件不存在", "updated": 0}

    print("=" * 60)
    print(f"从 JSONL 更新招标详情：{jsonl_path}")
    print("=" * 60)

    data = load_jsonl(str(jsonl_path))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    updated = 0

    for item in data:
        url = item.get('url', '')
        if not url:
            continue

        cursor.execute("""
            UPDATE tenders
            SET publish_date = ?,
                buyer_name = ?,
                agency_name = ?,
                budget = ?,
                content = ?,
                status = 'processed'
            WHERE detail_url = ?
        """, (
            item.get('publish_date', ''),
            item.get('buyer', ''),
            item.get('agency', ''),
            item.get('budget', ''),
            item.get('content', ''),
            url
        ))
        updated += cursor.rowcount

    conn.commit()
    conn.close()

    print(f"[DB] 更新 {updated} 条记录")
    print(f"[DB] 已写入：{DB_PATH}")

    return {"success": True, "updated": updated}


def import_attachments_from_jsonl(jsonl_path=None):
    """
    从 JSONL 文件导入附件数据到 tender_attachments 表
    """
    if jsonl_path is None:
        jsonl_path = CRAWLER_OUTPUT_DIR / "tenders_attachments.jsonl"

    jsonl_path = Path(jsonl_path)
    if not jsonl_path.exists():
        print(f"[ERROR] JSONL 文件不存在：{jsonl_path}")
        return {"success": False, "error": "文件不存在", "inserted": 0, "skipped": 0}

    print("=" * 60)
    print(f"从 JSONL 导入附件：{jsonl_path}")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 确保表存在
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tender_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id INTEGER,
            tender_uuid TEXT,
            file_name TEXT NOT NULL,
            download_url TEXT NOT NULL,
            uuid TEXT,
            source_html_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tender_id) REFERENCES tenders(id) ON DELETE CASCADE
        )
    """)
    
    # 检查并添加缺失的列
    cursor.execute("PRAGMA table_info(tender_attachments)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'tender_uuid' not in columns:
        cursor.execute("ALTER TABLE tender_attachments ADD COLUMN tender_uuid TEXT")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_tender_uuid ON tender_attachments(tender_uuid)")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_tender_id ON tender_attachments(tender_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_url ON tender_attachments(download_url)")

    # 获取已存在的 URL
    cursor.execute("SELECT download_url FROM tender_attachments")
    existing = {row[0] for row in cursor.fetchall()}

    data = load_jsonl(str(jsonl_path))

    inserted = 0
    skipped = 0

    # 获取 tenders 表中的 detail_url 到 uuid 的映射
    cursor.execute("SELECT detail_url, uuid FROM tenders")
    url_to_uuid = {row[0]: row[1] for row in cursor.fetchall() if row[0]}

    for item in data:
        url = item.get('download_url', '')
        if url in existing:
            skipped += 1
            continue

        # 查找对应的 tender_uuid
        # 注意：这里假设附件 JSON 中没有直接提供 tender_uuid，需要通过关联表查找
        # 如果有 source_html_file，可以尝试解析出关联的 tender
        tender_uuid = None
        # 这里逻辑可以根据实际附件数据的来源进一步优化
        
        cursor.execute("""
            INSERT INTO tender_attachments (tender_id, tender_uuid, file_name, download_url, uuid, source_html_file)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            item.get('tender_id'),
            tender_uuid,
            item.get('file_name', ''),
            url,
            item.get('uuid'),
            item.get('source_html_file', '')
        ))
        inserted += 1
        existing.add(url)

    conn.commit()
    conn.close()

    print(f"[DB] 插入 {inserted} 条，跳过 {skipped} 条")
    print(f"[DB] 已写入：{DB_PATH}")

    return {"success": True, "inserted": inserted, "skipped": skipped}


def import_all():
    """
    一次性导入所有数据（列表 + 详情 + 附件）
    """
    print("\n" + "=" * 60)
    print("开始批量导入所有数据")
    print("=" * 60 + "\n")

    # 初始化数据库
    init_database()

    # 导入招标列表
    result_list = import_tenders_from_jsonl()

    # 更新招标详情
    result_detail = update_tender_details_from_jsonl()

    # 导入附件
    result_attachment = import_attachments_from_jsonl()

    print("\n" + "=" * 60)
    print("导入完成")
    print(f"招标列表：插入 {result_list.get('inserted', 0)} 条，跳过 {result_list.get('skipped', 0)} 条")
    print(f"招标详情：更新 {result_detail.get('updated', 0)} 条")
    print(f"附件：插入 {result_attachment.get('inserted', 0)} 条，跳过 {result_attachment.get('skipped', 0)} 条")
    print("=" * 60)

    return {
        "success": True,
        "list": result_list,
        "detail": result_detail,
        "attachment": result_attachment
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="导入招标数据到数据库")
    parser.add_argument("--list", action="store_true", help="导入招标列表 (tenders_list.jsonl)")
    parser.add_argument("--detail", action="store_true", help="更新招标详情 (tenders_detail.jsonl)")
    parser.add_argument("--attachments", action="store_true", help="导入附件 (tenders_attachments.jsonl)")
    parser.add_argument("--all", action="store_true", help="导入所有数据 (列表+详情+附件)")
    
    args = parser.parse_args()
    
    if args.all or (not args.list and not args.detail and not args.attachments):
        import_all()
    else:
        if args.list:
            import_tenders_from_jsonl()
        if args.detail:
            update_tender_details_from_jsonl()
        if args.attachments:
            import_attachments_from_jsonl()
