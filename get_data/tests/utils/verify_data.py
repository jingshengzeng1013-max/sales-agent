# -*- coding: utf-8 -*-
import os
import sqlite3
import sys

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from config import DB_PATH


def verify():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 统计
    cursor.execute("SELECT COUNT(*) FROM tenders")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tenders WHERE status = 'processed'")
    processed = cursor.fetchone()[0]

    print("=" * 60)
    print("Data Verification")
    print("=" * 60)
    print(f"\nTotal tenders: {total}")
    print(f"Processed: {processed}")
    print(f"Pending: {total - processed}")

    # 查看最新 5 条
    cursor.execute(
        """
        SELECT project_name, publish_date, status
        FROM tenders
        ORDER BY created_at DESC
        LIMIT 5
    """
    )
    rows = cursor.fetchall()

    print("\nLatest 5 tenders:")
    for i, (name, date, status) in enumerate(rows, 1):
        print(f"  {i}. [{status}] {date}")

    conn.close()
    print("\n" + "=" * 60)


if __name__ == "__main__":
    verify()
