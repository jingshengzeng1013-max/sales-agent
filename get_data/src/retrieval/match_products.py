# -*- coding: utf-8 -*-
"""
产品-标讯匹配脚本 - 使用混合检索 (Faiss + BM25 + RRF) 实现
"""
import json
import os
import numpy as np
from src.retrieval.hybrid_retriever import HybridRetriever
from src.vectorization.vectorize_data import Vectorizer

# ==================== 配置区域 ====================
PRODUCT_DATA = "D:/sales_agent/get_data/data/product_embedded.json"
TENDER_DATA = "D:/sales_agent/get_data/data/output/etl/tenders_embedded.json"
MATCH_RESULT_PATH = "D:/sales_agent/get_data/data/output/etl/product_tender_matches.json"
# ==================== 配置区域 ====================

def main():
    print("=" * 50)
    print("开始进行产品-标讯智能匹配 (Hybrid Retrieval)")
    print("=" * 50)

    # 1. 检查数据文件
    if not os.path.exists(PRODUCT_DATA) or not os.path.exists(TENDER_DATA):
        print("错误: 缺少向量化后的数据文件。请先运行 vectorize_data.py")
        return

    # 2. 初始化混合检索器 (针对标讯数据)
    print("\n[1/3] 初始化混合检索器...")
    retriever = HybridRetriever(TENDER_DATA)

    # 3. 加载产品数据
    print("\n[2/3] 加载产品数据...")
    with open(PRODUCT_DATA, 'r', encoding='utf-8') as f:
        products = json.load(f)

    # 4. 执行匹配
    print("\n[3/3] 执行匹配逻辑...")
    all_matches = []
    
    for product in products:
        print(f"正在为产品匹配标讯: {product['name']}")
        
        # 提取查询文本和向量
        query_text = f"{product['name']} {product['category']} {' '.join(product['features'])} {' '.join(product['use_cases'])}"
        query_vector = product['embedding']
        
        # 执行混合检索 (Top 10)
        matches = retriever.search(query_text, query_vector, top_n=10)
        
        # 组装匹配结果
        product_match = {
            "product_id": product["id"],
            "product_name": product["name"],
            "matched_tenders": []
        }
        
        for m in matches:
            product_match["matched_tenders"].append({
                "tender_id": m.get("id"),
                "tender_title": m.get("title"),
                "buyer": m.get("buyer"),
                "budget": f"{m.get('budget_amount', '')} {m.get('budget_unit', '')}",
                "retrieval_score": m["retrieval_score"],
                "notice_url": m.get("notice_url"),
                "notice_type": m.get("notice_type")
            })
            
        all_matches.append(product_match)

    # 5. 保存结果
    os.makedirs(os.path.dirname(MATCH_RESULT_PATH), exist_ok=True)
    with open(MATCH_RESULT_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_matches, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 50)
    print(f"匹配完成！结果已保存至: {MATCH_RESULT_PATH}")
    print("=" * 50)

if __name__ == "__main__":
    main()
