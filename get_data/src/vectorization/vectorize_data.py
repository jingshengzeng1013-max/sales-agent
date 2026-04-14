# -*- coding: utf-8 -*-
"""
向量化工具类 - 使用本地 OpenAI 兼容的 Embedding 接口
"""
import os
import json
import numpy as np
from typing import List, Dict, Any, Union
from openai import OpenAI

# ==================== 配置区域 ====================
# 默认使用 test_local_llm.py 中的配置，也可以通过环境变量覆盖
DEFAULT_BASE_URL = "http://10.210.10.51:11437/v1"
DEFAULT_API_KEY = "sk-local"
# 注意：Embedding 通常使用专门的向量模型，如果本地服务支持，请修改此名称
DEFAULT_EMBEDDING_MODEL = "bge-large-zh-v1.5" 
# ==================== 配置区域 ====================

class Vectorizer:
    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        self.base_url = base_url or os.environ.get("LOCAL_EMBEDDING_BASE_URL", DEFAULT_BASE_URL)
        self.api_key = api_key or os.environ.get("LOCAL_EMBEDDING_API_KEY", DEFAULT_API_KEY)
        self.model = model or os.environ.get("LOCAL_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=60.0
        )

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """调用本地接口获取向量"""
        try:
            # 过滤空字符串
            texts = [t if t and t.strip() else "None" for t in texts]
            
            response = self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            print(f"向量化失败: {e}")
            # 如果失败，返回零向量作为占位（实际生产环境应有更好处理）
            return [[0.0] * 1024 for _ in texts] # 假设维度是 1024

    def vectorize_products(self, product_path: str, output_path: str):
        """将 product.json 向量化并保存"""
        print(f"正在向量化产品数据: {product_path}")
        with open(product_path, 'r', encoding='utf-8') as f:
            products = json.load(f)
        
        # 构建用于向量化的文本内容
        texts_to_embed = []
        for p in products:
            # 组合名称、描述、特性和关键词，形成丰富的语义描述
            content = f"产品名称: {p['name']}\n"
            content += f"分类: {p['category']} - {p.get('sub_category', '')}\n"
            content += f"描述: {p['description']}\n"
            content += f"特性: {' '.join(p['features'])}\n"
            content += f"应用场景: {' '.join(p['use_cases'])}\n"
            content += f"关键词: {' '.join(p.get('keywords', []))}"
            texts_to_embed.append(content)
        
        embeddings = self.get_embeddings(texts_to_embed)
        
        # 将向量存回对象
        for i, p in enumerate(products):
            p['embedding'] = embeddings[i]
            
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        print(f"产品向量化完成，保存至: {output_path}")

    def vectorize_tenders(self, tender_path: str, output_path: str):
        """将 tenders_structured.json 向量化并保存"""
        print(f"正在向量化标讯数据: {tender_path}")
        if not os.path.exists(tender_path):
            print(f"文件不存在: {tender_path}")
            return

        with open(tender_path, 'r', encoding='utf-8') as f:
            tenders = json.load(f)
        
        # 构建用于向量化的文本内容
        texts_to_embed = []
        for t in tenders:
            # 组合标题、项目名称、采购内容、预算等信息
            content = f"项目名称: {t['title']}\n"
            content += f"采购人: {t.get('buyer', '')}\n"
            content += f"预算: {t.get('budget_amount', '')} {t.get('budget_unit', '')}\n"
            content += f"采购内容: {t.get('purchase_items_description', '')}\n"
            content += f"公告类型: {t.get('notice_type', '')}\n"
            # 提取中标信息（如果有）
            if t.get('winning_bidder'):
                content += f"中标人: {t['winning_bidder']}\n"
            texts_to_embed.append(content)
        
        # 批量处理，避免一次性发送过多文本（如果本地服务有长度限制）
        batch_size = 20
        all_embeddings = []
        for i in range(0, len(texts_to_embed), batch_size):
            batch = texts_to_embed[i:i+batch_size]
            print(f"处理批次: {i//batch_size + 1}/{(len(texts_to_embed)-1)//batch_size + 1}")
            all_embeddings.extend(self.get_embeddings(batch))
        
        # 将向量存回对象
        for i, t in enumerate(tenders):
            t['embedding'] = all_embeddings[i]
            
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(tenders, f, ensure_ascii=False, indent=2)
        print(f"标讯向量化完成，保存至: {output_path}")

if __name__ == "__main__":
    # 示例运行
    vectorizer = Vectorizer()
    
    # 向量化产品
    product_in = "D:/sales_agent/get_data/data/product.json"
    product_out = "D:/sales_agent/get_data/data/product_embedded.json"
    vectorizer.vectorize_products(product_in, product_out)
    
    # 向量化标讯
    tender_in = "D:/sales_agent/get_data/data/output/etl/tenders_structured.json"
    tender_out = "D:/sales_agent/get_data/data/output/etl/tenders_embedded.json"
    vectorizer.vectorize_tenders(tender_in, tender_out)
