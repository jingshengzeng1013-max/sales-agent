# 混合检索系统技术报告

> FAISS + BM25 实现招标数据检索
> 版本：v2.0（DualRetriever）
> 更新时间：2026-04-27

---

## 1. 系统概述

### 1.1 背景

招标数据具有以下特点：
- 文本内容长（招标公告通常数千字）
- 关键词重要（如"卫星通信"、"交换机"）
- 需要语义理解（如"应急"与"抢险救灾"的关联）

单一的向量检索或关键词检索都无法完全满足需求。

### 1.2 目标

实现 **FAISS 向量检索 + BM25 关键词检索** 的混合检索：
1. 语义理解能力（向量检索）
2. 精确关键词匹配（BM25）
3. 按项目汇总多条公告

---

## 2. 技术架构

### 2.1 核心类：DualRetriever

```python
# 文件：src/retrieval/retriever.py

class DualRetriever:
    def __init__(self, data_type: str = "product"):
        """
        :param data_type: "product" 或 "tender"
        """
        self.vectorizer = Vectorizer()
        self.dimension = 1024
        self.load_resources()

    def hybrid_search(self, query_text: str, top_k: int = 10,
                      vector_weight: float = 0.5,
                      bm25_weight: float = 0.5,
                      province: str = None,
                      notice_type: str = None,
                      aggregate_by_project: bool = True,
                      exclude_won: bool = False,
                      sort_by: str = "score",
                      client_value_weight: float = 0.0) -> List[Dict]:
        """双路检索 + RRF 融合 + 可选的项目汇总"""
```

### 2.2 数据流

```
1. 初始化
   └─> 加载 FAISS 索引 (index_path)
   └─> 加载 ID 映射 (id_map_path)
   └─> 加载原始数据 + 构建 BM25 索引 (raw_data_path)

2. 检索流程
   ├─> 向量检索
   │   └─> get_embeddings() → FAISS.search() → 取 top_k * 50
   │
   ├─> BM25 检索
   │   └─> jieba.cut() → get_scores() → 取 top_k * 50
   │
   └─> RRF 融合
       └─> combined_score = vector_weight/(k+rank_v) + bm25_weight/(k+rank_b)

3. 可选：按项目汇总
   └─> 加载 projects_aggregated.jsonl
   └─> 按 project_name_std + buyer_name 汇总
   └─> 计算平均分 + 客户价值加权

4. 返回结果
   └─> sorted by score, limit top_k
```

---

## 3. 索引构建

### 3.1 向量化

```bash
# 文件：src/vectorization/vectorize_data.py
python -m src.vectorization.vectorize_data --type tender
```

**输出：** `data/embedding/tenders_embedded.jsonl`

### 3.2 构建索引

```bash
# 文件：src/vectorization/build_index.py
python -m src.vectorization.build_index --type tender
```

**输出：**
- `data/index_tenders/tenders.index` (FAISS 索引)
- `data/index_tenders/tenders_ids.json` (ID 映射)

---

## 4. 核心技术

### 4.1 文本嵌入（Embedding）

使用 **Qwen3-Embedding-0.6B** 模型：

```python
# 配置：src/config.py
EMBEDDING_CONFIG = {
    "base_url": "http://10.210.10.51:8022/v1",
    "model": "/models/Qwen3-Embedding-0.6B",
    "dimension": 1024,
}
```

### 4.2 FAISS 向量检索

```python
import faiss

# 创建 Flat 索引（内积相似度）
index = faiss.IndexFlatIP(1024)

# 查询
faiss.normalize_L2(query_vector)
distances, indices = index.search(query_vector, top_k)
```

### 4.3 BM25 关键词检索

```python
from rank_bm25 import BM25Okapi
import jieba

# 中文分词
def tokenize(text):
    return list(jieba.cut(text))

corpus = [tokenize(doc) for doc in documents]
bm25 = BM25Okapi(corpus)

# 查询
query_words = tokenize(query)
scores = bm25.get_scores(query_words)
```

### 4.4 RRF 分数融合

```python
def _rrf_fusion(self, vector_scores, bm25_scores, k=60):
    vector_ranks = np.argsort(np.argsort(-vector_scores)) + 1
    bm25_ranks = np.argsort(np.argsort(-bm25_scores)) + 1

    return (
        self.vector_weight / (k + vector_ranks) +
        self.bm25_weight / (k + bm25_ranks)
    )
```

---

## 5. 项目汇总功能

当 `aggregate_by_project=True` 时，系统会将同一项目的多条公告汇总显示：

```python
# 按项目汇总得分
project_scores = {}
for item_id, scores in combined_scores.items():
    proj_key = f"{project_module['project_name_std']}@{project_module['buyer_name']}"
    project_scores[proj_key]["rrf_scores"].append(scores["rrf_score"])

# 计算项目平均分
avg_rrf = sum(info["rrf_scores"]) / len(info["rrf_scores"])
```

**示例输出：**
```
[1] 85.32 - 某省应急管理系统采购项目 (3条公告关联)
    - 招标: 应急管理系统采购公告
    - 中标: 应急管理系统中标公告
    - 招标: 应急管理系统监理服务
```

---

## 6. 客户价值加权

当 `client_value_weight > 0` 时，系统会基于客户历史评分进行加权：

```python
if client_value_weight > 0:
    avg_score = info["project_data"].get("opportunity_score", 0)
    boost_val = 0.8 + (avg_score / 100.0) * 0.4
    client_boost = 1.0 + (boost_val - 1.0) * client_value_weight
```

---

## 7. 性能指标

| 阶段 | 时间 |
|------|------|
| 索引加载 | <0.5 秒 |
| 单次查询 | ~100-200ms |

---

## 8. 参考文档

- [FAISS 官方文档](https://faiss.ai/)
- [jieba 分词](https://github.com/fxsjy/jieba)
- [rank-bm25](https://github.com/dorianbrown/rank_bm25)
- [Qwen3-Embedding](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)

---

*报告完*
