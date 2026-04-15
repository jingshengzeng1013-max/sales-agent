# -*- coding: utf-8 -*-
"""
验证 FAISS 向量检索功能
"""

import faiss
import numpy as np
import json
import os
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

from src.config import INDEX_DIR, TENDER_INDEX_DIR

def test_search(index_path, id_map_path, data_path, query_idx=0, top_k=5):
    """
    使用索引中的一个向量作为查询，搜索最相似的项
    """
    print(f"\n--- 测试搜索: {os.path.basename(index_path)} ---")
    
    # 加载索引
    index = faiss.read_index(str(index_path))
    
    # 加载 ID 映射
    with open(id_map_path, 'r', encoding='utf-8') as f:
        ids = json.load(f)
        
    # 加载原始数据（用于显示结果）
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 建立 ID 到数据的映射，支持多种可能的 ID 字段名
    data_dict = {}
    for item in data:
        item_id = item.get('id') or item.get('project_id')
        if item_id:
            data_dict[str(item_id)] = item

    # 获取一个查询向量
    query_id = ids[query_idx]
    query_item = data_dict.get(str(query_id))
    if not query_item:
        # 如果 ID 映射中的 ID 在原始数据里找不到，尝试使用列表索引
        query_item = data[query_idx]
        query_id = query_item.get('id') or query_item.get('project_id') or query_idx
        
    query_vector = np.array([query_item['embedding']]).astype('float32')
    faiss.normalize_L2(query_vector)

    # 搜索
    distances, indices = index.search(query_vector, top_k)

    print(f"查询项: {query_item.get('name') or query_item.get('project_name')}")
    print(f"Top {top_k} 匹配结果:")
    for i in range(len(indices[0])):
        idx = indices[0][i]
        dist = distances[0][i]
        if idx < len(ids):
            match_id = ids[idx]
            match_item = data_dict.get(str(match_id))
            if match_item:
                name = match_item.get('name') or match_item.get('project_name')
                print(f"  [{i+1}] 相似度: {dist:.4f} | ID: {match_id} | 名称: {name}")
            else:
                print(f"  [{i+1}] 相似度: {dist:.4f} | ID: {match_id} | (原始数据中未找到详情)")

if __name__ == "__main__":
    # 测试产品搜索
    test_search(
        INDEX_DIR / "product.index",
        INDEX_DIR / "product_ids.json",
        BASE_DIR / "data/embedding/product_embedded.json"
    )
    
    # 测试标讯搜索
    test_search(
        TENDER_INDEX_DIR / "tenders.index",
        TENDER_INDEX_DIR / "tenders_ids.json",
        BASE_DIR / "data/embedding/tenders_embedded.json"
    )
