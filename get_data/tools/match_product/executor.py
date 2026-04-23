# -*- coding: utf-8 -*-
"""
产品匹配检索执行器：按招标搜产品的混合检索
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.config import DATA_DIR, INDEX_DIR, EMBEDDING_CONFIG

logger = logging.getLogger("get_data.tools.match_product")

# 索引目录
PRODUCT_INDEX_DIR = INDEX_DIR

# 全局检索器
_hybrid_searcher = None


class ProductHybridSearcher:
    """产品混合检索器（FAISS + BM25）"""

    def __init__(self, index_dir: Path):
        self.index_dir = Path(index_dir)
        self.faiss_index = None
        self.bm25_index = None
        self.product_docs = []  # 产品文档
        self.product_ids = []   # 产品 ID
        self.product_data = {}  # 产品元数据
        self.metadata = {}      # 索引元数据

        self._load_index()

    def _load_index(self):
        """加载索引"""
        try:
            # 加载 FAISS 索引
            faiss_path = self.index_dir / "faiss.index"
            if faiss_path.is_file():
                import faiss
                self.faiss_index = faiss.read_index(str(faiss_path))
                logger.info(f"FAISS 索引加载成功：{faiss_path}")

            # 加载 BM25 索引和文档
            bm25_path = self.index_dir / "bm25.json"
            if bm25_path.is_file():
                from rank_bm25 import BM25Okapi
                with open(bm25_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.product_docs = data.get("docs", [])
                    self.product_ids = data.get("ids", [])
                    self.product_data = data.get("product_data", {})
                    # 构建 BM25 索引
                    tokenized_docs = [self._tokenize(doc) for doc in self.product_docs]
                    self.bm25_index = BM25Okapi(tokenized_docs)
                logger.info(f"BM25 索引加载成功：{bm25_path}")

            # 加载元数据
            meta_path = self.index_dir / "metadata.json"
            if meta_path.is_file():
                with open(meta_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                logger.info(f"元数据加载成功：{meta_path}")

        except Exception as e:
            logger.warning(f"加载索引失败：{e}")

    def _tokenize(self, text: str) -> List[str]:
        """简单的中文分词（按字符）"""
        return list(text.lower())

    def search(
        self,
        query: str,
        top_k: int = 20,
        use_vector: bool = True,
        use_bm25: bool = True,
        min_score: float = 0.0,
        vector_weight: float = 0.5,
        bm25_weight: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        混合检索产品

        Args:
            query: 查询文本
            top_k: 返回数量
            use_vector: 是否使用向量检索
            use_bm25: 是否使用 BM25 检索
            min_score: 最低分数阈值
            vector_weight: 向量权重
            bm25_weight: BM25 权重

        Returns:
            检索结果列表
        """
        results = []

        # 向量检索
        vector_scores = None
        if use_vector and self.faiss_index is not None:
            try:
                from src.retrieval.embedding_api import get_embedding_client
                client = get_embedding_client()
                query_embedding = client.embed_query(query)

                import numpy as np
                import faiss
                query_vector = np.array([query_embedding], dtype=np.float32)
                faiss.normalize_L2(query_vector)

                D, I = self.faiss_index.search(query_vector, min(top_k * 2, len(self.product_ids)))
                vector_scores = np.zeros(len(self.product_ids))
                for i, idx in enumerate(I[0]):
                    if idx < len(self.product_ids):
                        vector_scores[idx] = D[0][i]

                logger.debug(f"向量检索完成，最高分：{vector_scores.max():.4f}")
            except Exception as e:
                logger.warning(f"向量检索失败：{e}")
                vector_scores = None

        # BM25 检索
        bm25_scores = None
        if use_bm25 and self.bm25_index is not None:
            try:
                tokenized_query = self._tokenize(query)
                scores = self.bm25_index.get_scores(tokenized_query)
                # 归一化到 0-1
                max_score = scores.max() if scores.max() > 0 else 1
                bm25_scores = scores / max_score
                logger.debug(f"BM25 检索完成，最高分：{bm25_scores.max():.4f}")
            except Exception as e:
                logger.warning(f"BM25 检索失败：{e}")
                bm25_scores = None

        # 融合分数
        if vector_scores is not None and bm25_scores is not None:
            combined_scores = vector_weight * vector_scores + bm25_weight * bm25_scores
        elif vector_scores is not None:
            combined_scores = vector_scores
        elif bm25_scores is not None:
            combined_scores = bm25_scores
        else:
            logger.warning("没有可用的检索方法")
            return []

        # 收集结果
        for i, score in enumerate(combined_scores):
            if score >= min_score:
                product_id = str(self.product_ids[i]) if i < len(self.product_ids) else None
                product_info = self.product_data.get(product_id) or self.product_data.get(str(self.product_ids[i]) if i < len(self.product_ids) else None) or {}
                results.append({
                    "product_id": product_id,
                    "score": float(score),
                    "vector_score": float(vector_scores[i]) if vector_scores is not None else None,
                    "bm25_score": float(bm25_scores[i]) if bm25_scores is not None else None,
                    "rrf_raw_score": float(combined_scores[i]),
                    "data": product_info
                })

        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def search_size(self) -> int:
        """返回索引大小"""
        return len(self.product_ids)


def get_hybrid_searcher() -> ProductHybridSearcher:
    """获取检索器单例"""
    global _hybrid_searcher
    if _hybrid_searcher is None:
        _hybrid_searcher = ProductHybridSearcher(PRODUCT_INDEX_DIR)
    return _hybrid_searcher


def rebuild_product_index(products: List[Dict[str, Any]]) -> None:
    """
    重建产品索引

    Args:
        products: 产品列表，每个元素包含 id, name, description 等字段
    """
    import json
    import numpy as np

    # 确保目录存在
    PRODUCT_INDEX_DIR.mkdir(parents=True, exist_ok=True)

    # 提取文档和 ID
    docs = []
    ids = []
    product_data = {}
    for p in products:
        if isinstance(p, dict):
            pid = p.get("id")
            name = p.get("name", "")
            desc = p.get("description", "")
            tags = p.get("tags") or p.get("keywords") or []
            if isinstance(tags, list):
                tags = " ".join(tags)

            # 构建检索文档
            doc_parts = [name, desc, tags]
            doc = " ".join(filter(None, doc_parts))
            if doc and pid:
                docs.append(doc)
                ids.append(int(pid))
                product_data[str(pid)] = p

    # 保存 BM25 索引
    bm25_data = {"docs": docs, "ids": ids, "product_data": product_data}
    bm25_path = PRODUCT_INDEX_DIR / "bm25.json"
    with open(bm25_path, "w", encoding="utf-8") as f:
        json.dump(bm25_data, f, ensure_ascii=False)

    # 构建 FAISS 索引
    try:
        from src.retrieval.embedding_api import get_embedding_client
        client = get_embedding_client()

        # 批量计算向量（分批处理避免 OOM）
        batch_size = 100
        all_embeddings = []
        for i in range(0, len(docs), batch_size):
            batch = docs[i:i + batch_size]
            embeddings = client.embed(batch)
            all_embeddings.extend(embeddings)

        # 转换为 numpy 数组
        embeddings_array = np.array(all_embeddings, dtype=np.float32)

        # 归一化
        import faiss
        faiss.normalize_L2(embeddings_array)

        # 构建索引
        dimension = embeddings_array.shape[1]
        index = faiss.IndexFlatIP(dimension)  # 内积相似度
        index.add(embeddings_array)

        # 保存索引
        faiss_path = PRODUCT_INDEX_DIR / "faiss.index"
        faiss.write_index(index, str(faiss_path))

        logger.info(f"FAISS 索引构建完成：{len(ids)} 个产品")

    except Exception as e:
        logger.error(f"构建 FAISS 索引失败：{e}")
        raise

    # 保存元数据
    meta = {
        "product_count": len(ids),
        "product_ids": ids,
        "product_data": product_data,
        "created_at": str(__import__("datetime").datetime.now().isoformat())
    }
    meta_path = PRODUCT_INDEX_DIR / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)

    logger.info(f"产品索引重建完成：{len(ids)} 个产品")
