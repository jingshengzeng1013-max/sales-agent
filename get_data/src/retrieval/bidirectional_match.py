# -*- coding: utf-8 -*-
"""
双向混合检索匹配工具 - 实现“标讯找产品”和“产品找标讯”的双向匹配逻辑
"""
import json
import os
import numpy as np
from typing import List, Dict, Any
from src.retrieval.hybrid_retriever import HybridRetriever

# ==================== 配置区域 ====================
PRODUCT_EMBEDDED = "D:/sales_agent/get_data/data/product_embedded.json"
TENDER_EMBEDDED = "D:/sales_agent/get_data/data/output/etl/tenders_embedded.json"
MATCH_RESULT_DIR = "D:/sales_agent/get_data/data/output/etl"
# ==================== 配置区域 ====================

class BidirectionalMatcher:
    def __init__(self):
        self.product_retriever = None
        self.tender_retriever = None
        self.products = []
        self.tenders = []
        
        self._initialize_retrievers()

    def _initialize_retrievers(self):
        """初始化两个方向的检索器"""
        if os.path.exists(PRODUCT_EMBEDDED):
            print(f"正在构建产品库索引: {PRODUCT_EMBEDDED}")
            self.product_retriever = HybridRetriever(PRODUCT_EMBEDDED)
            with open(PRODUCT_EMBEDDED, 'r', encoding='utf-8') as f:
                self.products = json.load(f)
        
        if os.path.exists(TENDER_EMBEDDED):
            print(f"正在构建标讯库索引: {TENDER_EMBEDDED}")
            self.tender_retriever = HybridRetriever(TENDER_EMBEDDED)
            with open(TENDER_EMBEDDED, 'r', encoding='utf-8') as f:
                self.tenders = json.load(f)

    def match_tenders_for_products(self, top_n: int = 10):
        """方向一：为每个产品匹配最相关的标讯 (产品找标讯)"""
        if not self.tender_retriever or not self.products:
            print("错误: 标讯索引或产品数据未就绪")
            return

        print("\n[方向一] 正在执行：产品 -> 匹配标讯...")
        results = []
        for p in self.products:
            # 构造查询：组合名称、描述、特性
            query_text = f"{p['name']} {p['category']} {' '.join(p['features'])}"
            query_vector = p['embedding']
            
            matches = self.tender_retriever.search(query_text, query_vector, top_n=top_n)
            
            results.append({
                "product_id": p["id"],
                "product_name": p["name"],
                "matched_tenders": [
                    {
                        "tender_id": m.get("id"),
                        "title": m.get("title"),
                        "buyer": m.get("buyer"),
                        "score": m["retrieval_score"]
                    } for m in matches
                ]
            })
        
        output_path = os.path.join(MATCH_RESULT_DIR, "match_product_to_tenders.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"结果已保存至: {output_path}")

    def match_products_for_tenders(self, top_n: int = 5):
        """方向二：为每个标讯匹配最相关的产品 (标讯找产品)"""
        if not self.product_retriever or not self.tenders:
            print("错误: 产品索引或标讯数据未就绪")
            return

        print("\n[方向二] 正在执行：标讯 -> 匹配产品...")
        results = []
        for t in self.tenders:
            # 构造查询：组合项目名称、采购内容
            query_text = f"{t['title']} {t.get('purchase_items_description', '')}"
            query_vector = t['embedding']
            
            matches = self.product_retriever.search(query_text, query_vector, top_n=top_n)
            
            results.append({
                "tender_id": t.get("id"),
                "tender_title": t.get("title"),
                "buyer": t.get("buyer"),
                "matched_products": [
                    {
                        "product_id": m["id"],
                        "product_name": m["name"],
                        "score": m["retrieval_score"]
                    } for m in matches
                ]
            })
        
        output_path = os.path.join(MATCH_RESULT_DIR, "match_tender_to_products.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"结果已保存至: {output_path}")

def main():
    matcher = BidirectionalMatcher()
    
    # 1. 产品找标讯 (适合：销售看自家产品能卖给谁)
    matcher.match_tenders_for_products(top_n=10)
    
    # 2. 标讯找产品 (适合：看到一个新标，看自家哪个产品能投)
    matcher.match_products_for_tenders(top_n=5)

if __name__ == "__main__":
    main()
