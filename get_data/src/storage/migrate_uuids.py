# -*- coding: utf-8 -*-
"""
数据迁移脚本：为现有标讯数据生成并填充 UUID
"""

import sqlite3
import uuid
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

from src.config import DB_PATH

def migrate_uuids():
    print(f"[INFO] 开始为数据库 {DB_PATH} 填充 UUID...")
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        # 1. 处理 tenders 表
        cursor.execute("SELECT id FROM tenders WHERE uuid IS NULL")
        tender_ids = cursor.fetchall()
        print(f"[INFO] 发现 {len(tender_ids)} 条 tenders 记录需要填充 UUID")
        
        for (tid,) in tender_ids:
            new_uuid = str(uuid.uuid4())
            # 更新 tenders 表
            cursor.execute("UPDATE tenders SET uuid = ? WHERE id = ?", (new_uuid, tid))
            # 同步更新关联表（通过旧的 tender_id 关联）
            cursor.execute("UPDATE tender_structured SET uuid = ? WHERE tender_id = ?", (new_uuid, tid))
            cursor.execute("UPDATE tender_attachments SET tender_uuid = ? WHERE tender_id = ?", (new_uuid, tid))
            cursor.execute("UPDATE tender_chunks SET tender_uuid = ? WHERE tender_id = ?", (new_uuid, tid))

        # 2. 处理那些在 tenders 表中没有，但在 tender_structured 中存在的记录（如果有的话）
        cursor.execute("SELECT id FROM tender_structured WHERE uuid IS NULL")
        structured_ids = cursor.fetchall()
        if structured_ids:
            print(f"[INFO] 发现 {len(structured_ids)} 条孤立的 tender_structured 记录需要填充 UUID")
            for (sid,) in structured_ids:
                new_uuid = str(uuid.uuid4())
                cursor.execute("UPDATE tender_structured SET uuid = ? WHERE id = ?", (new_uuid, sid))

        conn.commit()
        print("[SUCCESS] UUID 填充完成！")
        
        # 验证一下
        cursor.execute("SELECT COUNT(*) FROM tender_structured WHERE uuid IS NOT NULL")
        count = cursor.fetchone()[0]
        print(f"[INFO] 当前 tender_structured 中已填充 UUID 的记录数: {count}")

    except Exception as e:
        print(f"[ERROR] 迁移失败: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_uuids()
