# -*- coding: utf-8 -*-
"""
混合检索实现类 - 基于 Faiss (向量检索) + BM25 (关键词检索) + RRF (重排序融合)
"""
import json
import os
import numpy as np
import faiss
import jieba
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any, Tuple

class HybridRetriever:
    def __init__(self, data_path: str, vector_dim: int = 1024):
        """
        初始化检索器
        :param data_path: 包含向量的 JSON 数据文件路径 (如 tenders_embedded.json)
        :param vector_dim: 向量维度
        """
        self.data_path = data_path
        self.vector_dim = vector_dim
        self.items = []
        self.index = None
        self.bm25 = None
        self.corpus_tokenized = []
        
        self._load_data()
        self._build_faiss_index()
        self._build_bm25_index()

    def _load_data(self):
        """加载数据"""
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"数据文件不存在: {self.data_path}")
        
        with open(self.data_path, 'r', encoding='utf-8') as f:
            self.items = json.load(f)
        print(f"成功加载 {len(self.items)} 条数据进行索引")

    def _build_faiss_index(self):
        """构建 Faiss 向量索引"""
        # 提取所有向量
        embeddings = []
        for item in self.items:
            if 'embedding' in item and item['embedding']:
                embeddings.append(item['embedding'])
            else:
                # 如果没有向量，用零向量占位
                embeddings.append([0.0] * self.vector_dim)
        
        embeddings_np = np.array(embeddings).astype('float32')
        
        # 使用内积 (Inner Product) 索引，通常用于余弦相似度（如果向量已归一化）
        # 或者使用 L2 距离索引
        self.index = faiss.IndexFlatIP(self.vector_dim)
        
        # 归一化向量以实现余弦相似度
        faiss.normalize_L2(embeddings_np)
        self.index.add(embeddings_np)
        print("Faiss 向量索引构建完成")

    def _tokenize(self, text: str) -> List[str]:
        """中文分词"""
        return list(jieba.cut(text))

    def _build_bm25_index(self):
        """构建 BM25 关键词索引"""
        self.corpus_tokenized = []
        for item in self.items:
            # 组合关键文本字段用于关键词检索
            text_content = f"{item.get('title', '')} {item.get('buyer', '')} {item.get('purchase_items_description', '')}"
            self.corpus_tokenized.append(self._tokenize(text_content))
        
        self.bm25 = BM25Okapi(self.corpus_tokenized)
        print("BM25 关键词索引构建完成")

    def _rrf(self, faiss_results: List[int], bm25_results: List[int], k: int = 60) -> List[Tuple[int, float]]:
        """
        Reciprocal Rank Fusion (RRF) 算法融合两个检索列表
        Score = sum(1 / (k + rank))
        """
        scores = {}
        
        # 处理向量检索结果
        for rank, idx in enumerate(faiss_results):
            scores[idx] = scores.get(idx, 0) + 1.0 / (k + rank + 1)
            
        # 处理关键词检索结果
        for rank, idx in enumerate(bm25_results):
            scores[idx] = scores.get(idx, 0) + 1.0 / (k + rank + 1)
            
        # 按得分从高到低排序
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_results

    def search(self, query_text: str, query_vector: List[float], top_n: int = 10) -> List[Dict[str, Any]]:
        """
        混合检索
        :param query_text: 查询文本 (用于 BM25)
        :param query_vector: 查询向量 (用于 Faiss)
        :param top_n: 返回结果数量
        """
        # 1. Faiss 向量检索 (取两倍 top_n 以便融合)
        query_vector_np = np.array([query_vector]).astype('float32')
        faiss.normalize_L2(query_vector_np)
        search_k = min(len(self.items), top_n * 3)
        distances, faiss_indices = self.index.search(query_vector_np, search_k)
        faiss_indices = faiss_indices[0].tolist()
        
        # 2. BM25 关键词检索
        tokenized_query = self._tokenize(query_text)
        bm25_scores = self.bm25.get_scores(tokenized_query)
        # 获取得分最高的索引
        bm25_indices = np.argsort(bm25_scores)[::-1][:search_k].tolist()
        
        # 3. RRF 融合
        combined_results = self._rrf(faiss_indices, bm25_indices)
        
        # 4. 组装结果
        final_items = []
        for idx, score in combined_results[:top_n]:
            item = self.items[idx].copy()
            item['retrieval_score'] = score
            # 标记来源（可选）
            item['in_faiss'] = idx in faiss_indices
            item['in_bm25'] = idx in bm25_indices
            final_items.append(item)
            
        return final_items

if __name__ == "__main__":
    # 示例用法
    # 假设你已经运行了向量化脚本生成了 tenders_embedded.json
    TENDER_DATA = "D:/sales_agent/get_data/data/output/etl/tenders_embedded.json"
    
    if os.path.exists(TENDER_DATA):
        retriever = HybridRetriever(TENDER_DATA)
        
        # 模拟一个查询（实际应从产品向量中获取）
        # 这里仅作结构演示
        test_query_text = "卫星通信 终端 芯片"
        test_query_vector = [0.01] * 1024 # 模拟向量
        
        results = retriever.search(test_query_text, test_query_vector, top_n=5)
        
        print("\n检索结果:")
        for i, res in enumerate(results):
            print(f"{i+1}. [{res.get('retrieval_score', 0):.4f}] {res.get('title')}")
    else:
        print(f"请先运行向量化脚本生成: {TENDER_DATA}")
