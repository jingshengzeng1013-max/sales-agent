# -*- coding: utf-8 -*-
"""
向量化工具类 - 使用本地 OpenAI 兼容的 Embedding 接口
"""
import os
import sys
import json
import numpy as np
from typing import List, Dict, Any, Union
from pathlib import Path
from openai import OpenAI
from tqdm import tqdm

# 将项目根目录添加到 sys.path
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from src.config import EMBEDDING_CONFIG, DATA_DIR
from src.utils.jsonl_helper import load_jsonl, save_jsonl

class Vectorizer:
    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        self.base_url = base_url or EMBEDDING_CONFIG["base_url"]
        self.api_key = api_key or "sk-local"
        self.model = model or EMBEDDING_CONFIG["model"]
        self.dimension = EMBEDDING_CONFIG.get("dimension", 1024)
        
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
            print(f"\n[ERROR] 向量化失败: {e}")
            # 如果失败，返回零向量作为占位
            return [[0.0] * self.dimension for _ in texts]

    def vectorize_products(self, product_path: str, output_path: str):
        """将 product.jsonl 向量化并保存"""
        # 统一后缀
        product_path = str(product_path).replace(".json", ".jsonl") if not str(product_path).endswith(".jsonl") else str(product_path)
        output_path = str(output_path).replace(".json", ".jsonl") if not str(output_path).endswith(".jsonl") else str(output_path)
        
        print(f"\n[INFO] 正在向量化产品数据: {product_path}")
        
        if not os.path.exists(product_path):
            print(f"[ERROR] 文件不存在: {product_path}")
            return

        products = load_jsonl(product_path)
        
        # 构建用于向量化的文本内容：全部字段拼接在一起
        texts_to_embed = []
        for p in products:
            # 将所有非 embedding 字段的值拼接在一起
            full_text = " ".join([str(v) for k, v in p.items() if k != 'embedding' and v])
            texts_to_embed.append(full_text)
            # 记录拼接后的内容，方便后续排查
            p['embedded_content'] = full_text
        
        # 使用进度条处理
        embeddings = []
        batch_size = 10
        for i in tqdm(range(0, len(texts_to_embed), batch_size), desc="产品向量化"):
            batch = texts_to_embed[i:i+batch_size]
            embeddings.extend(self.get_embeddings(batch))
        
        # 将向量存回对象
        for i, p in enumerate(products):
            p['embedding'] = embeddings[i]
            
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
        save_jsonl(products, output_path)
        print(f"[SUCCESS] 产品向量化完成，保存至: {output_path}")

    def vectorize_tenders(self, tender_path: str, output_path: str):
        """将 tenders_structured.jsonl 向量化并保存"""
        # 统一后缀
        tender_path = str(tender_path).replace(".json", ".jsonl") if not str(tender_path).endswith(".jsonl") else str(tender_path)
        output_path = str(output_path).replace(".json", ".jsonl") if not str(output_path).endswith(".jsonl") else str(output_path)

        print(f"\n[INFO] 正在向量化标讯数据: {tender_path}")
        if not os.path.exists(tender_path):
            print(f"[ERROR] 文件不存在: {tender_path}")
            return

        # 从数据库获取最新的结构化数据（包含 publish_date 等）
        import sqlite3
        from src.config import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tender_structured")
        tenders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if not tenders:
            print("[WARNING] 数据库中没有结构化数据，尝试从 JSONL 加载...")
            tenders = load_jsonl(tender_path)
        
        # 构建用于向量化的文本内容（聚焦需求匹配）
        texts_to_embed = []
        for t in tenders:
            # 针对用户端（标讯），对重点字段进行拼接
            keywords = ", ".join(t.get('product_keywords', [])) if isinstance(t.get('product_keywords'), list) else str(t.get('product_keywords', ''))
            scenario = t.get('application_scenario', '')
            tech = t.get('technical_requirements_summary', '')
            content_summary = t.get('content_summary', '')
            winning_product = ", ".join(t.get('winning_product', [])) if isinstance(t.get('winning_product'), list) else str(t.get('winning_product', ''))
            
            # 拼接重点信息
            content = f"采购关键词: {keywords} | "
            content += f"应用场景: {scenario} | "
            content += f"技术要求摘要: {tech} | "
            content += f"内容摘要: {content_summary} | "
            content += f"中标产品: {winning_product}"
            
            texts_to_embed.append(content)
            # 记录拼接后的内容
            t['embedded_content'] = content
        
        # 批量处理，带进度条
        batch_size = 20
        all_embeddings = []
        for i in tqdm(range(0, len(texts_to_embed), batch_size), desc="标讯向量化"):
            batch = texts_to_embed[i:i+batch_size]
            all_embeddings.extend(self.get_embeddings(batch))
        
        # 将向量存回对象
        for i, t in enumerate(tenders):
            if i < len(all_embeddings):
                t['embedding'] = all_embeddings[i]
            
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
        save_jsonl(tenders, output_path)
        print(f"[SUCCESS] 标讯向量化完成，保存至: {output_path}")

if __name__ == "__main__":
    # 使用统一配置初始化
    vectorizer = Vectorizer()
    
    # 向量化产品
    product_in = "D:/sales_agent/get_data/data/product.jsonl"
    product_out = "D:/sales_agent/get_data/data/embedding/product_embedded.jsonl"
    vectorizer.vectorize_products(product_in, product_out)
    
    # 向量化标讯
    tender_in = "D:/sales_agent/get_data/data/output/etl/tenders_structured.jsonl"
    tender_out = "D:/sales_agent/get_data/data/embedding/tenders_embedded.jsonl"
    vectorizer.vectorize_tenders(tender_in, tender_out)
