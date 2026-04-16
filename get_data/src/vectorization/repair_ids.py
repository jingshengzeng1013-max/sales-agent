# -*- coding: utf-8 -*-
"""
修复脚本：为 embedded.json 文件补充 UUID
"""
import json
import sqlite3
import sys
from pathlib import Path

# 添加项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

from src.config import DB_PATH

def repair_json_ids():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # 1. 修复产品数据
    product_json = BASE_DIR / "data/embedding/product_embedded.json"
    if product_json.exists():
        print(f"[INFO] 正在修复产品数据: {product_json}")
        with open(product_json, 'r', encoding='utf-8') as f:
            products = json.load(f)
        
        # 产品表目前可能没有 uuid，我们先用 id 或者生成一个
        for i, p in enumerate(products):
            if 'uuid' not in p:
                p['uuid'] = p.get('id') or f"prod_{i+1}"
        
        with open(product_json, 'w', encoding='utf-8') as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        print("[SUCCESS] 产品数据修复完成")

    # 2. 修复标讯数据
    tender_json = BASE_DIR / "data/embedding/tenders_embedded.json"
    if tender_json.exists():
        print(f"[INFO] 正在修复标讯数据: {tender_json}")
        with open(tender_json, 'r', encoding='utf-8') as f:
            tenders = json.load(f)
        
        # 从数据库获取 url -> uuid 映射
        cursor.execute("SELECT detail_url, uuid FROM tenders")
        url_to_uuid = {row[0]: row[1] for row in cursor.fetchall() if row[0]}
        
        repaired_count = 0
        for t in tenders:
            url = t.get('source_url')
            if url in url_to_uuid:
                t['uuid'] = url_to_uuid[url]
                repaired_count += 1
            else:
                # 如果数据库里没有，可能需要重新同步，这里先跳过或打标签
                t['uuid'] = None
        
        # 过滤掉没有 uuid 的（确保索引一致性）
        valid_tenders = [t for t in tenders if t.get('uuid')]
        
        with open(tender_json, 'w', encoding='utf-8') as f:
            json.dump(valid_tenders, f, ensure_ascii=False, indent=2)
        print(f"[SUCCESS] 标讯数据修复完成，共修复 {repaired_count} 条，有效记录 {len(valid_tenders)} 条")

    conn.close()

if __name__ == "__main__":
    repair_json_ids()
