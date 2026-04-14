# -*- coding: utf-8 -*-
"""
招标公告入库模块
将爬取的 JSON 数据导入 SQLite tenders 表
"""

import sqlite3
import json
import os
from pathlib import Path
from src.config import DB_PATH, CRAWLER_OUTPUT_DIR


def init_database():
    """初始化 SQLite 数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tenders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            publish_date TEXT,
            detail_url TEXT,
            content TEXT,
            buyer_name TEXT,
            agency_name TEXT,
            budget TEXT,
            attachment_urls TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print(f"[DB] 数据库初始化完成：{DB_PATH}")


def import_tenders_from_json(json_path=None):
    """
    从 JSON 文件导入招标列表数据到 tenders 表

    Args:
        json_path: JSON 文件路径，默认使用 crawler_output/tenders_list.json
    """
    if json_path is None:
        json_path = CRAWLER_OUTPUT_DIR / "tenders_list.json"

    json_path = Path(json_path)
    if not json_path.exists():
        print(f"[ERROR] JSON 文件不存在：{json_path}")
        return {"success": False, "error": "文件不存在", "inserted": 0, "skipped": 0}

    print("=" * 60)
    print(f"从 JSON 导入招标列表：{json_path}")
    print("=" * 60)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 获取已存在的项目名
    cursor.execute("SELECT project_name FROM tenders")
    existing = {row[0] for row in cursor.fetchall()}

    inserted = 0
    skipped = 0

    for item in data:
        name = item.get('project_name', '')
        if name in existing:
            skipped += 1
            continue

        cursor.execute("""
            INSERT INTO tenders (project_name, detail_url, content, status)
            VALUES (?, ?, ?, 'new')
        """, (
            name,
            item.get('detail_url', ''),
            item.get('content', ''),
        ))
        inserted += 1
        existing.add(name)

    conn.commit()
    conn.close()

    print(f"[DB] 插入 {inserted} 条，跳过 {skipped} 条")
    print(f"[DB] 已写入：{DB_PATH}")

    return {"success": True, "inserted": inserted, "skipped": skipped}


def update_tender_details_from_json(json_path=None):
    """
    从 JSON 文件更新招标详情数据到 tenders 表

    Args:
        json_path: JSON 文件路径，默认使用 crawler_output/tenders_detail.json
    """
    if json_path is None:
        json_path = CRAWLER_OUTPUT_DIR / "tenders_detail.json"

    json_path = Path(json_path)
    if not json_path.exists():
        print(f"[ERROR] JSON 文件不存在：{json_path}")
        return {"success": False, "error": "文件不存在", "updated": 0}

    print("=" * 60)
    print(f"从 JSON 更新招标详情：{json_path}")
    print("=" * 60)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

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


def import_attachments_from_json(json_path=None):
    """
    从 JSON 文件导入附件数据到 tender_attachments 表

    Args:
        json_path: JSON 文件路径，默认使用 crawler_output/tenders_attachments.json
    """
    if json_path is None:
        json_path = CRAWLER_OUTPUT_DIR / "tenders_attachments.json"

    json_path = Path(json_path)
    if not json_path.exists():
        print(f"[ERROR] JSON 文件不存在：{json_path}")
        return {"success": False, "error": "文件不存在", "inserted": 0, "skipped": 0}

    print("=" * 60)
    print(f"从 JSON 导入附件：{json_path}")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 确保表存在
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tender_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id INTEGER,
            file_name TEXT NOT NULL,
            download_url TEXT NOT NULL,
            uuid TEXT,
            source_html_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tender_id) REFERENCES tenders(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_tender_id ON tender_attachments(tender_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_url ON tender_attachments(download_url)")

    # 获取已存在的 URL
    cursor.execute("SELECT download_url FROM tender_attachments")
    existing = {row[0] for row in cursor.fetchall()}

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    inserted = 0
    skipped = 0

    for item in data:
        url = item.get('download_url', '')
        if url in existing:
            skipped += 1
            continue

        cursor.execute("""
            INSERT INTO tender_attachments (tender_id, file_name, download_url, uuid, source_html_file)
            VALUES (?, ?, ?, ?, ?)
        """, (
            item.get('tender_id'),
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
    result_list = import_tenders_from_json()

    # 更新招标详情
    result_detail = update_tender_details_from_json()

    # 导入附件
    result_attachment = import_attachments_from_json()

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
