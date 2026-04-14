# -*- coding: utf-8 -*-
"""
生成 tender_chunks 表数据
从 tender_structured 表中读取结构化字段，生成 RAG 检索所需的 chunk 数据
"""

import json
import sqlite3
import sys
import os
from datetime import datetime

# 添加项目根目录和 src 目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)
from config import DB_PATH

# 日志配置
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def create_chunks_table(conn):
    """确保 tender_chunks 表存在"""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tender_chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id INTEGER NOT NULL,
            chunk_type TEXT,
            chunk_text TEXT NOT NULL,
            chunk_order INTEGER,
            metadata_json TEXT,
            embedding_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tender_id) REFERENCES tenders(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tender_chunks_tender_id ON tender_chunks(tender_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tender_chunks_chunk_type ON tender_chunks(chunk_type)")
    conn.commit()


def get_structured_data(conn, tender_id=None):
    """获取结构化数据"""
    cursor = conn.cursor()

    if tender_id:
        cursor.execute("""
            SELECT tender_id, announce_type, buyer_name_std, province, city,
                   content_summary, technical_requirements_summary,
                   buyer_contacts, agency_contacts, project_contacts,
                   contact_chunk, requirement_chunks, attachment_summary
            FROM tender_structured
            WHERE tender_id = ?
        """, (tender_id,))
    else:
        cursor.execute("""
            SELECT tender_id, announce_type, buyer_name_std, province, city,
                   content_summary, technical_requirements_summary,
                   buyer_contacts, agency_contacts, project_contacts,
                   contact_chunk, requirement_chunks, attachment_summary
            FROM tender_structured
        """)

    rows = cursor.fetchall()
    columns = ['tender_id', 'announce_type', 'buyer_name_std', 'province', 'city',
               'content_summary', 'technical_requirements_summary',
               'buyer_contacts', 'agency_contacts', 'project_contacts',
               'contact_chunk', 'requirement_chunks', 'attachment_summary']

    return [dict(zip(columns, row)) for row in rows]


def generate_chunks_for_tender(tender):
    """为单条招标数据生成 chunks"""
    chunks = []
    tender_id = tender['tender_id']

    # 1. title chunk (项目标题)
    cursor = sqlite3.connect(DB_PATH).cursor()
    cursor.execute("SELECT project_name FROM tenders WHERE id = ?", (tender_id,))
    row = cursor.fetchone()
    if row and row[0]:
        chunks.append({
            'tender_id': tender_id,
            'chunk_type': 'title',
            'chunk_text': row[0],
            'chunk_order': 1,
            'metadata_json': json.dumps({
                'announce_type': tender.get('announce_type'),
                'buyer_name_std': tender.get('buyer_name_std'),
                'province': tender.get('province'),
                'city': tender.get('city')
            }, ensure_ascii=False)
        })

    # 2. content_summary chunk (公告摘要)
    if tender.get('content_summary'):
        chunks.append({
            'tender_id': tender_id,
            'chunk_type': 'content_summary',
            'chunk_text': tender['content_summary'],
            'chunk_order': 2,
            'metadata_json': json.dumps({
                'announce_type': tender.get('announce_type'),
                'buyer_name_std': tender.get('buyer_name_std'),
                'province': tender.get('province'),
                'city': tender.get('city')
            }, ensure_ascii=False)
        })

    # 3. contact_chunk (联系方式块)
    if tender.get('contact_chunk'):
        chunks.append({
            'tender_id': tender_id,
            'chunk_type': 'contact_chunk',
            'chunk_text': tender['contact_chunk'],
            'chunk_order': 3,
            'metadata_json': json.dumps({
                'buyer_contacts': tender.get('buyer_contacts', '[]'),
                'agency_contacts': tender.get('agency_contacts', '[]'),
                'project_contacts': tender.get('project_contacts', '[]')
            }, ensure_ascii=False)
        })

    # 4. requirement_chunk (技术要求分块)
    if tender.get('requirement_chunks'):
        try:
            req_chunks = json.loads(tender['requirement_chunks'])
            for idx, req_chunk in enumerate(req_chunks, start=4):
                chunks.append({
                    'tender_id': tender_id,
                    'chunk_type': 'requirement_chunk',
                    'chunk_text': req_chunk.get('text', ''),
                    'chunk_order': idx,
                    'metadata_json': json.dumps({
                        'requirement_type': req_chunk.get('type'),
                        'announce_type': tender.get('announce_type'),
                        'buyer_name_std': tender.get('buyer_name_std')
                    }, ensure_ascii=False)
                })
        except (json.JSONDecodeError, TypeError):
            pass

    # 5. attachment_summary chunk (附件摘要)
    if tender.get('attachment_summary') and tender['attachment_summary'] != '无附件':
        chunks.append({
            'tender_id': tender_id,
            'chunk_type': 'attachment_summary',
            'chunk_text': tender['attachment_summary'],
            'chunk_order': 99,
            'metadata_json': json.dumps({
                'announce_type': tender.get('announce_type'),
                'buyer_name_std': tender.get('buyer_name_std')
            }, ensure_ascii=False)
        })

    return chunks


def insert_chunks(conn, chunks, replace=False):
    """插入 chunks 到数据库"""
    cursor = conn.cursor()

    # 获取已存在的 tender_id
    cursor.execute("SELECT DISTINCT tender_id FROM tender_chunks")
    existing = {row[0] for row in cursor.fetchall()}

    inserted = 0
    updated = 0
    skipped = 0

    for chunk in chunks:
        tender_id = chunk['tender_id']

        if tender_id in existing:
            if replace:
                # 删除旧的 chunks
                cursor.execute("DELETE FROM tender_chunks WHERE tender_id = ?", (tender_id,))
                inserted += 1
            else:
                skipped += 1
                continue

        cursor.execute("""
            INSERT INTO tender_chunks (tender_id, chunk_type, chunk_text, chunk_order, metadata_json)
            VALUES (?, ?, ?, ?, ?)
        """, (
            tender_id,
            chunk['chunk_type'],
            chunk['chunk_text'],
            chunk['chunk_order'],
            chunk['metadata_json']
        ))
        inserted += 1

    conn.commit()
    return inserted, updated, skipped


def main():
    import argparse

    parser = argparse.ArgumentParser(description='生成 tender_chunks 表数据')
    parser.add_argument('--tender-id', type=int, help='指定 tender_id，只处理单条数据')
    parser.add_argument('--all', action='store_true', help='处理所有数据')
    parser.add_argument('--replace', action='store_true', help='替换已存在的 chunks')

    args = parser.parse_args()

    print("=" * 60)
    print("开始生成 tender_chunks 数据")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    create_chunks_table(conn)

    # 获取数据
    if args.tender_id:
        print(f"处理单条数据：tender_id={args.tender_id}")
        structured_data = get_structured_data(conn, args.tender_id)
    elif args.all:
        print("处理所有数据...")
        structured_data = get_structured_data(conn)
    else:
        # 默认处理最近 100 条
        print("处理最近 100 条数据...")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tender_id FROM tender_structured
            ORDER BY tender_id DESC LIMIT 100
        """)
        tender_ids = [row[0] for row in cursor.fetchall()]
        structured_data = [get_structured_data(conn, tid)[0] for tid in tender_ids if get_structured_data(conn, tid)]

    print(f"获取到 {len(structured_data)} 条结构化数据")

    # 生成 chunks
    all_chunks = []
    for tender in structured_data:
        chunks = generate_chunks_for_tender(tender)
        all_chunks.extend(chunks)

    print(f"生成 {len(all_chunks)} 个 chunks")

    # 插入数据库
    inserted, updated, skipped = insert_chunks(conn, all_chunks, replace=args.replace)

    print(f"[DB] 插入 {inserted} 条，更新 {updated} 条，跳过 {skipped} 条")
    print("=" * 60)

    conn.close()


if __name__ == "__main__":
    main()
