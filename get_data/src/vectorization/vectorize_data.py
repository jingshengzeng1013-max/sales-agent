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
        """将 product.json 向量化并保存"""
        print(f"\n[INFO] 正在向量化产品数据: {product_path}")
        
        if not os.path.exists(product_path):
            print(f"[ERROR] 文件不存在: {product_path}")
            return

        with open(product_path, 'r', encoding='utf-8') as f:
            products = json.load(f)
        
        # 构建用于向量化的文本内容（聚焦产品能力与匹配）
        texts_to_embed = []
        for p in products:
            # 采用“功能-特性-场景”三位一体拼接，去掉泛化的“领域/分类”
            # 这种格式最有利于与标讯中的“技术要求”和“采购内容”进行语义对齐
            name = p.get('name', '')
            desc = p.get('description', '')
            features = " ".join(p.get('features', []))
            use_cases = " ".join(p.get('use_cases', []))
            keywords = " ".join(p.get('keywords', []))
            
            content = f"产品名称: {name} | "
            content += f"核心功能: {desc} | "
            content += f"关键特性: {features} | "
            content += f"解决场景: {use_cases} | "
            content += f"技术关键词: {keywords}"
            
            texts_to_embed.append(content)
        
        # 使用进度条处理
        embeddings = []
        batch_size = 10 # 产品通常不多，批次可以小一点
        for i in tqdm(range(0, len(texts_to_embed), batch_size), desc="产品向量化"):
            batch = texts_to_embed[i:i+batch_size]
            embeddings.extend(self.get_embeddings(batch))
        
        # 将向量存回对象
        for i, p in enumerate(products):
            p['embedding'] = embeddings[i]
            
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        print(f"[SUCCESS] 产品向量化完成，保存至: {output_path}")

    def vectorize_tenders(self, tender_path: str, output_path: str):
        """将 tenders_structured.json 向量化并保存"""
        print(f"\n[INFO] 正在向量化标讯数据: {tender_path}")
        if not os.path.exists(tender_path):
            print(f"[ERROR] 文件不存在: {tender_path}")
            return

        with open(tender_path, 'r', encoding='utf-8') as f:
            tenders = json.load(f)
        
        # 构建用于向量化的文本内容（聚焦需求匹配）
        texts_to_embed = []
        for t in tenders:
            # 采用“项目-关键词-需求-技术”拼接，去掉泛化的“领域”
            # 这种格式最有利于与产品中的“功能-特性-场景”进行语义对齐
            project = t.get('project_name', '')
            keywords = ", ".join(t.get('product_keywords', []))
            scenario = t.get('application_scenario', '')
            tech = t.get('technical_requirements_summary', '')
            
            content = f"采购项目: {project} | "
            content += f"采购关键词: {keywords} | "
            content += f"应用需求: {scenario} | "
            content += f"具体技术要求: {tech}"
            
            # 提取中标信息（如果有）
            if t.get('winning_bidder'):
                content += f" | 中标人: {t['winning_bidder']}"
            
            texts_to_embed.append(content)
        
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
            
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(tenders, f, ensure_ascii=False, indent=2)
        print(f"[SUCCESS] 标讯向量化完成，保存至: {output_path}")

if __name__ == "__main__":
    # 使用统一配置初始化
    vectorizer = Vectorizer()
    
    # 向量化产品
    product_in = "D:/sales_agent/get_data/data/product.json"
    product_out = "D:/sales_agent/get_data/data/embedding/product_embedded.json"
    vectorizer.vectorize_products(product_in, product_out)
    
    # 向量化标讯
    tender_in = "D:/sales_agent/get_data/data/output/etl/tenders_structured.json"
    tender_out = "D:/sales_agent/get_data/data/embedding/tenders_embedded.json"
    vectorizer.vectorize_tenders(tender_in, tender_out)
