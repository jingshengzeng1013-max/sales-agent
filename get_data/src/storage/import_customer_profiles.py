# -*- coding: utf-8 -*-
"""
客户画像入库模块
将生成的 customer_profiles.json 导入 SQLite customer_profiles 表
"""

import os
import sys
import sqlite3
import json
from pathlib import Path

# 将项目根目录添加到 sys.path
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from src.config import DB_PATH, CUSTOMER_OUTPUT_DIR
from src.utils.jsonl_helper import load_jsonl

def init_profiles_table():
    """初始化客户画像表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 创建客户画像表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customer_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT UNIQUE,
            province TEXT,
            city TEXT,
            industry TEXT,
            tech_keywords TEXT,
            application_scenarios TEXT,
            tender_count INTEGER,
            total_budget REAL,
            avg_opportunity_score REAL,
            past_winners TEXT,
            contact_info TEXT,
            full_profile_json TEXT,
            last_updated DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customer_name ON customer_profiles(customer_name)")
    conn.commit()
    conn.close()
    print(f"[DB] 客户画像表初始化完成")

def import_profiles(jsonl_path=None):
    """
    从 JSONL 文件导入客户画像
    """
    if jsonl_path is None:
        jsonl_path = CUSTOMER_OUTPUT_DIR / "customer_profiles.jsonl"
    
    if not os.path.exists(jsonl_path):
        print(f"[ERROR] JSONL 文件不存在：{jsonl_path}")
        return

    print("=" * 60)
    print(f"正在导入客户画像: {jsonl_path}")
    print("=" * 60)

    init_profiles_table()

    data = load_jsonl(str(jsonl_path))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    count = 0
    for item in data:
        name = item.get('customer_name')
        if not name: continue

        # 准备扁平化字段以便快速查询
        basic = item.get('basic_info', {})
        demand = item.get('demand_profile', {})
        value = item.get('value_profile', {})
        compete = item.get('competitive_landscape', {})
        
        fields = (
            name,
            basic.get('province'),
            basic.get('city'),
            ",".join(basic.get('industries', [])),
            json.dumps(demand.get('tech_keywords', []), ensure_ascii=False),
            json.dumps(demand.get('application_scenarios', []), ensure_ascii=False),
            value.get('tender_count', 0),
            value.get('total_budget', 0.0),
            value.get('avg_opportunity_score', 0.0),
            json.dumps(compete.get('past_winners', []), ensure_ascii=False),
            json.dumps(item.get('contact_info', {}), ensure_ascii=False),
            json.dumps(item, ensure_ascii=False),
            item.get('last_updated')
        )

        cursor.execute("""
            INSERT OR REPLACE INTO customer_profiles (
                customer_name, province, city, industry, tech_keywords,
                application_scenarios, tender_count, total_budget,
                avg_opportunity_score, past_winners, contact_info,
                full_profile_json, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, fields)
        count += 1

    conn.commit()
    conn.close()
    print(f"[DB] 成功导入/更新 {count} 个客户画像")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="导入客户画像到数据库")
    parser.add_argument("--json", type=str, help="画像 JSON 文件路径")
    args = parser.parse_args()
    
    import_profiles(args.json)
