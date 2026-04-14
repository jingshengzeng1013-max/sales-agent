# -*- coding: utf-8 -*-
"""
结构化标讯入库模块
将 LLM 抽取的 tenders_structured.json 数据导入 SQLite tender_structured 表
"""

import sqlite3
import json
import os
from pathlib import Path
from src.config import DB_PATH

def init_structured_table():
    """初始化结构化数据表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 创建结构化数据表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tender_structured (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    conn.commit()
    conn.close()
    print(f"[DB] 结构化数据表初始化完成")

def import_structured_tenders(json_path: str, mode: str = 'append'):
    """
    从 JSON 文件导入结构化标讯数据
    
    Args:
        json_path: JSON 文件路径
        mode: 'append' (跳过已存在的 source_url) 或 'replace' (覆盖已存在的记录)
    """
    if not os.path.exists(json_path):
        print(f"[ERROR] JSON 文件不存在：{json_path}")
        return {"success": False, "error": "文件不存在"}

    print("=" * 60)
    print(f"正在导入结构化数据: {json_path} (模式: {mode})")
    print("=" * 60)

    # 确保表已创建
    init_structured_table()

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    inserted = 0
    updated = 0
    skipped = 0

    for item in data:
        source_url = item.get('source_url')
        if not source_url:
            continue

        # 准备字段数据 (处理列表和字典为 JSON 字符串)
        fields = (
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
            item.get('winning_bidder'),
            item.get('winning_amount'),
            item.get('winning_product'),
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
                        source_url, project_name, buyer_name_std, agency_name_std,
                        province, city, budget_amount, budget_unit,
                        product_keywords, application_scenario, technical_requirements_summary,
                        content_summary, winning_bidder, winning_amount, winning_product,
                        contact_person, contact_phone, buyer_contacts, agency_contacts,
                        project_contacts, opportunity_score, opportunity_reason,
                        next_action, llm_model
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, fields)
                if cursor.rowcount > 0:
                    # 简单判断插入还是更新 (SQLite INSERT OR REPLACE 逻辑)
                    # 实际生产中可能需要更复杂的逻辑来区分
                    updated += 1
            else:
                cursor.execute("""
                    INSERT INTO tender_structured (
                        source_url, project_name, buyer_name_std, agency_name_std,
                        province, city, budget_amount, budget_unit,
                        product_keywords, application_scenario, technical_requirements_summary,
                        content_summary, winning_bidder, winning_amount, winning_product,
                        contact_person, contact_phone, buyer_contacts, agency_contacts,
                        project_contacts, opportunity_score, opportunity_reason,
                        next_action, llm_model
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, fields)
                inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1
            continue
        except Exception as e:
            print(f"[ERROR] 导入单条记录失败 ({source_url}): {e}")

    conn.commit()
    conn.close()

    print(f"[DB] 导入完成：新增 {inserted} 条，更新/替换 {updated} 条，跳过 {skipped} 条")
    return {"success": True, "inserted": inserted, "updated": updated, "skipped": skipped}

if __name__ == "__main__":
    # 默认导入路径
    STRUCTURED_JSON = "D:/sales_agent/get_data/data/output/etl/tenders_structured.json"
    import_structured_tenders(STRUCTURED_JSON, mode='replace')
