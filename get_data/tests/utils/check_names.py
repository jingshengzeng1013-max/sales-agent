# -*- coding: utf-8 -*-
import os
import sqlite3
import sys

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from config import DB_PATH


conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute(
    """
    SELECT tenders.id, project_name, buyer_name_std, status
    FROM tenders
    LEFT JOIN tender_structured ON tenders.id = tender_structured.tender_id
    WHERE project_name != ''
    LIMIT 10
"""
)

print("Records with project_name:")
for row in cursor.fetchall():
    id, name, buyer, status = row
    print(f"ID: {id}")
    print(f"  Name: {name[:50]}...")
    print(f"  Buyer: {buyer[:30] if buyer else 'N/A'}")
    print(f"  Status: {status}")
    print()

conn.close()
