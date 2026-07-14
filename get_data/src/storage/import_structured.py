# -*- coding: utf-8 -*-
"""
结构化标讯入库模块
将 LLM 抽取的 tenders_structured.json 数据导入 SQLite tender_structured 表
"""

import sqlite3
import json
import os
from pathlib import Path
import sys

# 将项目根目录添加到 sys.path
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from src.config import DB_PATH, ETL_OUTPUT_DIR
from src.utils.jsonl_helper import load_jsonl

import uuid

def init_structured_table():
    """初始化结构化数据表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 如果表已存在，先检查结构
    cursor.execute("PRAGMA table_info(tender_structured)")
    columns = {column[1]: column[2] for column in cursor.fetchall()}

    if not columns:
        # 表不存在，创建新表
        print("[DB] 正在创建 tender_structured 表...")
        cursor.execute('''
            CREATE TABLE tender_structured (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE,
                tender_id INTEGER,
                source_url TEXT UNIQUE,
                project_name TEXT,
                buyer_name_std TEXT,
                agency_name_std TEXT,
                province TEXT,
                city TEXT,
                budget_amount REAL,
                budget_unit TEXT,
                product_keywords TEXT,
                application_scenario TEXT,
                technical_requirements_summary TEXT,
                content_summary TEXT,
                winning_bidder TEXT,
                winning_amount REAL,
                winning_product TEXT,
                contact_person TEXT,
                contact_phone TEXT,
                buyer_contacts TEXT,
                agency_contacts TEXT,
                project_contacts TEXT,
                opportunity_score INTEGER,
                opportunity_reason TEXT,
                next_action TEXT,
                llm_model TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        # 表已存在，检查并修复列
        if 'uuid' not in columns:
            print("[DB] 为 tender_structured 添加 uuid 列...")
            cursor.execute("ALTER TABLE tender_structured ADD COLUMN uuid TEXT")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_structured_uuid ON tender_structured(uuid)")
        
        # 检查 tender_id 是否允许 NULL
        cursor.execute("PRAGMA table_info(tender_structured)")
        table_info = cursor.fetchall()
        tender_id_info = next((c for c in table_info if c[1] == 'tender_id'), None)
        
        needs_rebuild = False
        if tender_id_info and tender_id_info[3] == 1: # notnull == 1
            print("[DB] 警告: tender_id 具有 NOT NULL 约束，正在准备重建表以修复...")
            needs_rebuild = True
        
        if 'source_url' not in columns:
            print("[DB] 警告: source_url 列缺失，正在准备重建表以修复...")
            needs_rebuild = True

        if needs_rebuild:
            print("[DB] 正在重建 tender_structured 表以修复结构问题...")
            cursor.execute("DROP TABLE tender_structured")
            cursor.execute('''
                CREATE TABLE tender_structured (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tender_id INTEGER, -- 允许 NULL
                    source_url TEXT UNIQUE,
                    project_name TEXT,
                    buyer_name_std TEXT,
                    agency_name_std TEXT,
                    province TEXT,
                    city TEXT,
                    budget_amount REAL,
                    budget_unit TEXT,
                    product_keywords TEXT,
                    application_scenario TEXT,
                    technical_requirements_summary TEXT,
                    content_summary TEXT,
                    winning_bidder TEXT,
                    winning_amount REAL,
                    winning_product TEXT,
                    contact_person TEXT,
                    contact_phone TEXT,
                    buyer_contacts TEXT,
                    agency_contacts TEXT,
                    project_contacts TEXT,
                    opportunity_score INTEGER,
                    opportunity_reason TEXT,
                    next_action TEXT,
                    llm_model TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_structured_url ON tender_structured(source_url)")
    conn.commit()
    conn.close()
    print(f"[DB] 结构化数据表初始化完成")

def import_structured_tenders(jsonl_path: str, mode: str = 'append'):
    """
    从 JSONL 文件导入结构化标讯数据
    """
    if not os.path.exists(jsonl_path):
        print(f"[ERROR] JSONL 文件不存在：{jsonl_path}")
        return {"success": False, "error": "文件不存在"}

    print("=" * 60)
    print(f"正在导入结构化数据: {jsonl_path} (模式: {mode})")
    print("=" * 60)

    # 确保表已创建并包含所有列
    init_structured_table()

    data = load_jsonl(jsonl_path)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 获取 tenders 表中的 detail_url 到 (id, uuid, publish_date) 的映射，以便填充相关信息
    cursor.execute("SELECT detail_url, id, uuid, publish_date FROM tenders")
    url_to_info = {row[0]: (row[1], row[2], row[3]) for row in cursor.fetchall() if row[0]}

    inserted = 0
    updated = 0
    skipped = 0

    for item in data:
        source_url = item.get('source_url')
        if not source_url:
            continue

        tender_info = url_to_info.get(source_url)
        tender_id, tender_uuid, publish_date = tender_info if tender_info else (None, str(uuid.uuid4()), None)

        # 准备字段数据 (处理列表和字典为 JSON 字符串)
        fields = (
            tender_id,
            tender_uuid,
            publish_date,
            source_url,
            item.get('project_name'),
            item.get('buyer_name_std'),
            item.get('agency_name_std'),
            item.get('province'),
            item.get('city'),
            item.get('budget_amount'),
            item.get('budget_unit'),
            json.dumps(item.get('product_keywords', []), ensure_ascii=False),
            item.get('application_scenario'),
            item.get('technical_requirements_summary'),
            item.get('content_summary'),
            json.dumps(item.get('winning_bidder', []), ensure_ascii=False) if isinstance(item.get('winning_bidder'), list) else item.get('winning_bidder'),
            item.get('winning_amount'),
            json.dumps(item.get('winning_product', []), ensure_ascii=False) if isinstance(item.get('winning_product'), list) else item.get('winning_product'),
            item.get('contact_person'),
            item.get('contact_phone'),
            json.dumps(item.get('buyer_contacts', []), ensure_ascii=False),
            json.dumps(item.get('agency_contacts', []), ensure_ascii=False),
            json.dumps(item.get('project_contacts', []), ensure_ascii=False),
            item.get('opportunity_score'),
            item.get('opportunity_reason'),
            item.get('next_action'),
            item.get('llm_model')
        )

        try:
            if mode == 'replace':
                cursor.execute("""
                    INSERT OR REPLACE INTO tender_structured (
                        tender_id, uuid, publish_date, source_url, project_name, buyer_name_std, agency_name_std,
                        province, city, budget_amount, budget_unit,
                        product_keywords, application_scenario, technical_requirements_summary,
                        content_summary, winning_bidder, winning_amount, winning_product,
                        contact_person, contact_phone, buyer_contacts, agency_contacts,
                        project_contacts, opportunity_score, opportunity_reason,
                        next_action, llm_model
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, fields)
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO tender_structured (
                        tender_id, uuid, publish_date, source_url, project_name, buyer_name_std, agency_name_std,
                        province, city, budget_amount, budget_unit,
                        product_keywords, application_scenario, technical_requirements_summary,
                        content_summary, winning_bidder, winning_amount, winning_product,
                        contact_person, contact_phone, buyer_contacts, agency_contacts,
                        project_contacts, opportunity_score, opportunity_reason,
                        next_action, llm_model
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, fields)
                inserted += 1
        except sqlite3.IntegrityError as e:
            skipped += 1
            continue
        except Exception as e:
            print(f"[ERROR] 导入单条记录失败 ({source_url}): {e}")

    conn.commit()
    conn.close()

    print(f"[DB] 导入完成：新增 {inserted} 条，更新/替换 {updated} 条，跳过 {skipped} 条")
    return {"success": True, "inserted": inserted, "updated": updated, "skipped": skipped}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="导入结构化标讯数据到数据库")
    parser.add_argument("--json", type=str, help="结构化 JSON/JSONL 文件路径")
    parser.add_argument("--mode", type=str, choices=['append', 'replace'], default='replace', 
                        help="导入模式: append (跳过已存在) 或 replace (覆盖已存在)")
    
    args = parser.parse_args()
    
    json_path = args.json or str(ETL_OUTPUT_DIR / "tenders_structured.jsonl")
    import_structured_tenders(json_path, mode=args.mode)
