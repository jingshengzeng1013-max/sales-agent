# 双路检索模块 (Retrieval)

> 基于 FAISS 向量检索 + BM25 关键词检索的混合搜索实现，支持产品检索和招标检索两种模式。

## 目录结构

```
src/retrieval/
├── retriever.py      # 双路检索器核心实现
└── __init__.py
```

## 核心功能

### DualRetriever 双路检索器

支持两种数据类型的检索：
- **产品检索 (product)**：基于产品画像搜索相关招标机会
- **招标检索 (tender)**：基于招标需求搜索潜在客户

## 技术架构

### 1. 向量检索 (FAISS)

使用预训练的中文 Embedding 模型将文本映射为高维向量，通过 FAISS 索引实现高效的相似度搜索。

**配置** (`src/config.py`)：
```python
EMBEDDING_CONFIG = {
    "base_url": "http://10.210.10.51:8022/v1",
    "model": "/models/Qwen3-Embedding-0.6B",
    "dimension": 1024,
}
```

### 2. 关键词检索 (BM25)

基于经典 TF-IDF 改进的 BM25 算法，利用 jieba 分词处理中文文本，提供精确的关键词匹配。

### 3. RRF 融合算法

使用 Reciprocal Rank Fusion 融合两路搜索结果：
```
RRF_score(d) = Σ 1/(k + rank_i(d))
```
其中 k 通常取 60，确保两路结果都能适当加权。

## 使用方法

### 初始化检索器

```python
from src.retrieval.retriever import DualRetriever

# 产品检索器
product_retriever = DualRetriever(data_type="product")

# 招标检索器
tender_retriever = DualRetriever(data_type="tender")
```

### 执行检索

```python
results = tender_retriever.search(
    query="交换机 网络设备",
    top_k=20,
    vector_weight=0.5,      # 向量权重
    bm25_weight=0.5,        # BM25 权重
    min_score=0.0,          # 最低综合分过滤
    province="北京",        # 省份过滤
    notice_type="招标公告", # 公告类型过滤
    exclude_won=False,      # 是否排除已中标项目
    sort_by="score"         # 排序方式: score 或 date
)
```

### 返回结果格式

```python
{
    "tender_id": "xxx",
    "score": 85.5,           # 综合评分
    "vector_score": 0.92,    # 向量相似度
    "bm25_score": 78.3,     # BM25 分数
    "bm25_norm_score": 0.78, # BM25 归一化分数
    "rrf_raw_score": 0.0167, # RRF 原始融合分数
    "data": {
        "project_name": "xxx",
        "buyer_name": "xxx",
        "budget_amount": 500000,
        # ... 更多字段
    }
}
```

## API 接口

FastAPI 服务提供以下检索接口：

### `POST /api/retrieval/search-tenders`

按产品检索招标库

**请求参数**：
```json
{
    "product_id": "prod_001",
    "top_k": 20,
    "vector_weight": 0.5,
    "bm25_weight": 0.5,
    "min_score": 0.0,
    "province": null,
    "notice_type": null,
    "exclude_won": false,
    "sort_by": "score",
    "client_value_weight": 0.0
}
```

### `GET /api/retrieval/filter-options`

获取筛选选项（省份、公告类型）

### `GET /api/retrieval/product-options`

获取产品列表

## 数据依赖

检索器依赖以下数据文件：

| 数据类型 | 向量索引 | ID 映射 | 原始数据 |
|---------|---------|--------|---------|
| product | `data/index/product.index` | `data/index/product_ids.json` | `data/embedding/product_embedded.jsonl` |
| tender | `data/index_tenders/tenders.index` | `data/index_tenders/tenders_ids.json` | `data/embedding/tenders_embedded.jsonl` |

## 构建索引

首次使用或数据更新后，需要重新构建索引：

```bash
# 1. 向量化数据
python src/vectorization/vectorize_data.py

# 2. 构建 FAISS + BM25 索引
python src/vectorization/build_index.py
```
