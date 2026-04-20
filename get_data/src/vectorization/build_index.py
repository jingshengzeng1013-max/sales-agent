# -*- coding: utf-8 -*-
"""
使用 FAISS 构建产品和标讯的向量索引库
"""

import json
import os
import sys
import numpy as np
import faiss
from pathlib import Path

# 添加项目根目录到 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

from src.config import EMBEDDING_CONFIG, INDEX_DIR, TENDER_INDEX_DIR
from src.utils.jsonl_helper import load_jsonl

class IndexBuilder:
    def __init__(self):
        self.dimension = EMBEDDING_CONFIG.get("dimension", 1024)
        print(f"[INFO] 初始化索引构建器，向量维度: {self.dimension}")

    def build_index(self, data_path: str, index_save_dir: Path, index_name: str):
        """
        根据 JSONL 数据中的 embedding 构建 FAISS 索引
        """
        # 统一后缀
        data_path = str(data_path).replace(".json", ".jsonl") if not str(data_path).endswith(".jsonl") else str(data_path)
        
        print(f"\n[INFO] 正在从 {data_path} 加载数据...")
        if not os.path.exists(data_path):
            print(f"[ERROR] 数据文件不存在: {data_path}")
            return

        data_list = load_jsonl(data_path)

        if not data_list:
            print("[WARNING] 数据列表为空，跳过构建。")
            return

        # 提取向量并转换为 numpy 数组
        embeddings = []
        valid_ids = []
        
        for item in data_list:
            emb = item.get('embedding')
            # 优先使用 uuid，其次是 id
            item_id = item.get('uuid') or item.get('id')
            
            if emb and len(emb) == self.dimension and item_id:
                embeddings.append(emb)
                valid_ids.append(str(item_id))
            else:
                # 如果没有向量或ID，记录一下
                continue

        if not embeddings:
            print("[ERROR] 未找到有效的向量数据，请先运行 vectorize_data.py")
            return

        # 转换为 float32 numpy 数组
        embeddings_np = np.array(embeddings).astype('float32')
        
        # 归一化（用于计算余弦相似度，FAISS 的 Inner Product 在归一化后等同于余弦相似度）
        faiss.normalize_L2(embeddings_np)

        # 构建索引 (使用简单的暴力检索 IndexFlatIP，适合中小规模数据)
        index = faiss.IndexFlatIP(self.dimension)
        index.add(embeddings_np)

        # 确保目录存在
        index_save_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存索引文件
        index_file = index_save_dir / f"{index_name}.index"
        faiss.write_index(index, str(index_file))
        
        # 保存 ID 映射文件（因为 FAISS 只存向量，不存原始数据）
        id_map_file = index_save_dir / f"{index_name}_ids.json"
        with open(id_map_file, 'w', encoding='utf-8') as f:
            json.dump(valid_ids, f, ensure_ascii=False, indent=2)

        print(f"[SUCCESS] 索引构建完成！")
        print(f" - 向量数量: {len(valid_ids)}")
        print(f" - 索引文件: {index_file}")
        print(f" - ID映射文件: {id_map_file}")

if __name__ == "__main__":
    builder = IndexBuilder()
    
    # 1. 构建产品索引
    product_data = BASE_DIR / "data/embedding/product_embedded.jsonl"
    builder.build_index(str(product_data), INDEX_DIR, "product")
    
    # 2. 构建标讯索引
    tender_data = BASE_DIR / "data/embedding/tenders_embedded.jsonl"
    builder.build_index(str(tender_data), TENDER_INDEX_DIR, "tenders")
