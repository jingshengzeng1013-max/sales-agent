# -*- coding: utf-8 -*-
"""从 JSON 文件导入结构化数据到数据库"""

import sqlite3
import json
import sys
import os

# 添加项目根目录和 src 目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)
from config import DB_PATH, ETL_OUTPUT_DIR


def import_to_db(json_path=None):
    if json_path is None:
        json_path = str(ETL_OUTPUT_DIR / "tenders_structured.json")

    if not os.path.exists(json_path):
        print(f"[ERROR] JSON 文件不存在：{json_path}")
        return

    print("=" * 60)
    print(f"从 JSON 导入：{json_path}")
    print("=" * 60)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 确保表存在
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tender_structured (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id INTEGER NOT NULL,
            announce_type TEXT,
            buyer_name_std TEXT,
            agency_name_std TEXT,
            province TEXT,
            city TEXT,
            budget_raw TEXT,
            budget_amount REAL,
            budget_unit TEXT,
            product_keywords TEXT,
            application_scenario TEXT,
            content_summary TEXT,
            technical_requirements_summary TEXT,
            buyer_contacts TEXT,
            agency_contacts TEXT,
            project_contacts TEXT,
            contact_chunk TEXT,
            requirement_chunks TEXT,
            contact_person TEXT,
            contact_phone TEXT,
            attachment_summary TEXT,
            opportunity_score INTEGER,
            opportunity_reason TEXT,
            next_action TEXT,
            extracted_json TEXT,
            llm_model TEXT,
            llm_version TEXT,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tender_id) REFERENCES tenders(id)
        )
    """)

    # 获取已存在的 tender_id
    cursor.execute("SELECT tender_id FROM tender_structured")
    existing = {row[0] for row in cursor.fetchall()}

    def normalize(val):
        if val is None:
            return None
        if isinstance(val, (list, dict)):
            return json.dumps(val, ensure_ascii=False)
        return val

    inserted = 0
    updated = 0
    skipped = 0

    for item in data:
        tender_id = item.get('tender_id')
        if not tender_id:
            skipped += 1
            continue

        try:
            # 准备所有字段值
            values = (
                normalize(item.get('announce_type')),
                normalize(item.get('buyer_name_std')),
                normalize(item.get('agency_name_std')),
                normalize(item.get('province')),
                normalize(item.get('city')),
                normalize(item.get('budget_raw')),
                item.get('budget_amount'),
                normalize(item.get('budget_unit')),
                normalize(item.get('product_keywords')),
                normalize(item.get('application_scenario')),
                normalize(item.get('content_summary')),
                normalize(item.get('technical_requirements_summary')),
                normalize(item.get('buyer_contacts', [])),
                normalize(item.get('agency_contacts', [])),
                normalize(item.get('project_contacts', [])),
                normalize(item.get('contact_chunk')),
                normalize(item.get('requirement_chunks', [])),
                normalize(item.get('contact_person')),
                normalize(item.get('contact_phone')),
                normalize(item.get('attachment_summary')),
                item.get('opportunity_score'),
                normalize(item.get('opportunity_reason')),
                normalize(item.get('next_action')),
                normalize(item.get('extracted_json')) or normalize(item),
                normalize(item.get('llm_model', 'deepseek-chat')),
                normalize(item.get('llm_version', '')),
            )

            if tender_id in existing:
                cursor.execute("""
                    UPDATE tender_structured SET
                        announce_type=?, buyer_name_std=?, agency_name_std=?,
                        province=?, city=?, budget_raw=?, budget_amount=?, budget_unit=?,
                        product_keywords=?, application_scenario=?,
                        content_summary=?,
                        technical_requirements_summary=?,
                        buyer_contacts=?, agency_contacts=?, project_contacts=?,
                        contact_chunk=?, requirement_chunks=?,
                        contact_person=?, contact_phone=?,
                        attachment_summary=?, opportunity_score=?, opportunity_reason=?,
                        next_action=?, extracted_json=?, llm_model=?, llm_version=?
                    WHERE tender_id=?
                """, values + (tender_id,))
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO tender_structured (
                        tender_id, announce_type, buyer_name_std, agency_name_std,
                        province, city, budget_raw, budget_amount, budget_unit,
                        product_keywords, application_scenario,
                        content_summary,
                        technical_requirements_summary,
                        buyer_contacts, agency_contacts, project_contacts,
                        contact_chunk, requirement_chunks,
                        contact_person, contact_phone,
                        attachment_summary, opportunity_score, opportunity_reason,
                        next_action, extracted_json, llm_model, llm_version
                    ) VALUES (?, ?,?,?,?,?, ?,?,?, ?,?,?, ?,?, ?,?, ?,?, ?,?, ?,?, ?,?,?, ?, ?)
                """, (tender_id,) + values)
                inserted += 1
                existing.add(tender_id)
        except Exception as e:
            print(f"[ERROR] tender_id={tender_id}: {e}")
            skipped += 1

    conn.commit()
    conn.close()
    print(f"[DB] 插入 {inserted} 条，更新 {updated} 条，跳过 {skipped} 条")
    print(f"[DB] 已写入：{DB_PATH}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='从 JSON 导入结构化数据到数据库')
    parser.add_argument('--file', type=str, help='JSON 文件路径')
    args = parser.parse_args()
    import_to_db(args.file)
