# -*- coding: utf-8 -*-
"""
CCGP v2数据入库模块
将 ccgp_v2_*.jsonl (列表+详情绑定数据) 导入 SQLite tenders 表
"""

import sys
import os
import sqlite3
import json
from pathlib import Path
import uuid as uuid_lib

root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from src.config import DB_PATH


def init_database():
    """初始化/升级 tenders 表"""
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
            region TEXT,
            ann_type TEXT,
            attachment_urls TEXT,
            status TEXT DEFAULT 'new',
            source_keywords TEXT,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 动态添加缺失的列
    existing_cols = [col[1] for col in cursor.execute("PRAGMA table_info(tenders)").fetchall()]
    new_cols = {
        'region': 'TEXT',
        'ann_type': 'TEXT',
        'source_keywords': 'TEXT',
        'category': 'TEXT',
    }
    for col, col_type in new_cols.items():
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE tenders ADD COLUMN {col} {col_type}")

    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_tenders_url ON tenders(detail_url)')
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_tenders_uuid ON tenders(uuid)')

    conn.commit()
    conn.close()
    print(f"[DB] 数据库初始化完成: {DB_PATH}")


def import_ccgp_v2(jsonl_path):
    """导入CCGP v2数据到tenders表"""
    jsonl_path = Path(jsonl_path)
    if not jsonl_path.exists():
        print(f"[ERROR] 文件不存在: {jsonl_path}")
        return {"success": False, "error": "文件不存在", "inserted": 0, "skipped": 0, "updated": 0}

    print("=" * 60)
    print(f"导入CCGP v2数据: {jsonl_path}")
    print("=" * 60)

    # 读取数据
    records = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    print(f"[DB] 读取 {len(records)} 条记录")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 已存在的URL
    cursor.execute("SELECT detail_url FROM tenders")
    existing_urls = {row[0] for row in cursor.fetchall() if row[0]}

    inserted = 0
    skipped = 0
    updated = 0

    for item in records:
        url = item.get('detail_url', '')
        if not url:
            continue

        # 字段映射
        project_name = item.get('list_title', '') or item.get('detail_title', '') or ''
        publish_date = item.get('list_pub_date', '') or item.get('detail_date', '') or ''
        content = item.get('detail_body_preview', '') or ''
        buyer_name = item.get('list_buyer', '') or item.get('detail_buyer', '') or ''
        agency_name = item.get('list_agency', '') or item.get('detail_agency', '') or ''
        budget = item.get('detail_amount', '') or ''
        region = item.get('list_region', '') or item.get('detail_region', '') or ''
        ann_type = item.get('list_ann_type', '') or item.get('detail_type', '') or ''
        source_keywords = ','.join(item.get('source_keywords', [])) if item.get('source_keywords') else ''
        category = item.get('category', '') or ''

        if url in existing_urls:
            # 更新已有记录
            cursor.execute("""
                UPDATE tenders SET
                    project_name = COALESCE(NULLIF(?, ''), project_name),
                    publish_date = COALESCE(NULLIF(?, ''), publish_date),
                    content = COALESCE(NULLIF(?, ''), content),
                    buyer_name = COALESCE(NULLIF(?, ''), buyer_name),
                    agency_name = COALESCE(NULLIF(?, ''), agency_name),
                    budget = COALESCE(NULLIF(?, ''), budget),
                    region = COALESCE(NULLIF(?, ''), region),
                    ann_type = COALESCE(NULLIF(?, ''), ann_type),
                    source_keywords = COALESCE(NULLIF(?, ''), source_keywords),
                    category = COALESCE(NULLIF(?, ''), category),
                    status = 'new'
                WHERE detail_url = ?
            """, (project_name, publish_date, content, buyer_name, agency_name,
                  budget, region, ann_type, source_keywords, category, url))
            updated += cursor.rowcount
            skipped += 1
        else:
            cursor.execute("""
                INSERT INTO tenders (uuid, project_name, publish_date, detail_url, content,
                    buyer_name, agency_name, budget, region, ann_type, source_keywords, category, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
            """, (str(uuid_lib.uuid4()), project_name, publish_date, url, content,
                  buyer_name, agency_name, budget, region, ann_type, source_keywords, category))
            inserted += 1
            existing_urls.add(url)

    conn.commit()

    # 统计
    total = cursor.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
    conn.close()

    print(f"[DB] 插入 {inserted} 条，更新 {updated} 条（已存在），跳过 {skipped} 条")
    print(f"[DB] 总记录数: {total} 条")
    print(f"[DB] 已写入: {DB_PATH}")

    return {"success": True, "inserted": inserted, "updated": updated, "skipped": skipped, "total": total}


def mark_processed(status='processed'):
    """将匹配后的记录标记为已处理"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE tenders SET status = ? WHERE status = 'new'", (status,))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"[DB] 标记 {count} 条为 '{status}'")
    return count


def get_stats():
    """获取数据库统计"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    total = cursor.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
    new_count = cursor.execute("SELECT COUNT(*) FROM tenders WHERE status = 'new'").fetchone()[0]
    processed = cursor.execute("SELECT COUNT(*) FROM tenders WHERE status != 'new'").fetchone()[0]

    print(f"\n=== 数据库统计 ===")
    print(f"总记录: {total}")
    print(f"新记录(new): {new_count}")
    print(f"已处理: {processed}")

    # 按category统计
    print(f"\n按category统计:")
    for row in cursor.execute("SELECT category, COUNT(*) FROM tenders GROUP BY category ORDER BY COUNT(*) DESC").fetchall():
        print(f"  {row[0] or '(无)'}: {row[1]}")

    conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="导入CCGP v2数据到数据库")
    parser.add_argument("--file", type=str, help="指定JSONL文件路径")
    parser.add_argument("--init", action="store_true", help="初始化数据库")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")
    parser.add_argument("--mark", type=str, default=None, help="将new记录标记为指定状态")
    args = parser.parse_args()

    if args.init:
        init_database()

    if args.stats:
        get_stats()

    if args.mark:
        mark_processed(args.mark)

    if args.file:
        import_ccgp_v2(args.file)

    if not any([args.init, args.stats, args.mark, args.file]):
        # 默认导入最新的v2数据
        default_file = Path(__file__).resolve().parents[2] / "data/output/crawler/ccgp_v2_20260514_185934.jsonl"
        if default_file.exists():
            import_ccgp_v2(str(default_file))
            get_stats()
        else:
            print(f"[ERROR] 默认文件不存在: {default_file}")
            print("请使用 --file 参数指定文件路径")