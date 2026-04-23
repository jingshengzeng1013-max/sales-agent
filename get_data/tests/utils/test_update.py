# -*- coding: utf-8 -*-
"""
测试更新逻辑
"""

import os
import sqlite3
import sys

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from config import DB_PATH


def test_update():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 查看第一条记录
    cursor.execute(
        """
        SELECT id, project_name, detail_url, status
        FROM tenders
        LIMIT 1
    """
    )
    row = cursor.fetchone()

    if row:
        id, name, url, status = row
        print("Before update:")
        print(f"  ID: {id}")
        print(f"  Name: {name}")
        print(f"  URL: {url}")
        print(f"  Status: {status}")

        # 模拟更新（不破坏原有 name）
        cursor.execute(
            """
            UPDATE tenders
            SET publish_date = '2026-03-27',
                status = 'processed'
            WHERE id = ?
        """,
            (id,),
        )
        conn.commit()

        # 查看更新后
        cursor.execute(
            "SELECT project_name, status FROM tenders WHERE id = ?",
            (id,),
        )
        updated = cursor.fetchone()
        print("\nAfter update:")
        print(f"  Name: {updated[0]} (应该保持不变)")
        print(f"  Status: {updated[1]}")

    conn.close()


if __name__ == "__main__":
    test_update()
