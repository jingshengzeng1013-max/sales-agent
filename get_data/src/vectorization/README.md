# 向量化与索引模块 (Vectorization)

> 将文本数据转换为高维向量，构建 FAISS 索引和 BM25 索引，支持高效的相似度搜索。

## 目录结构

```
src/vectorization/
├── vectorize_data.py   # 文本向量化（调用 Embedding API）
├── build_index.py      # 构建 FAISS 索引和 BM25 索引
├── repair_ids.py       # 修复 ID 映射文件
└── test_search.py      # 检索测试脚本
```

## 核心功能

### 1. 文本向量化 (vectorize_data.py)

调用 Embedding 服务将文本转换为高维向量。

**配置** (`src/config.py`)：

```python
EMBEDDING_CONFIG = {
    "base_url": "http://10.210.10.51:8022/v1",
    "model": "/models/Qwen3-Embedding-0.6B",
    "dimension": 1024,
}
```

**使用示例**：

```bash
# 向量化招标数据
python src/vectorization/vectorize_data.py --type tender

# 向量化产品数据
python src/vectorization/vectorize_data.py --type product

# 指定输入文件
python src/vectorization/vectorize_data.py --type tender --input data/output/etl/tenders_structured.jsonl
```

**输出文件**：

- `data/embedding/tenders_embedded.jsonl` - 带向量数据的招标记录
- `data/embedding/product_embedded.jsonl` - 带向量数据的产品记录

### 2. 构建索引 (build_index.py)

构建 FAISS 向量索引和 BM25 关键词索引。

**使用示例**：

```bash
# 构建招标索引
python src/vectorization/build_index.py --type tender

# 构建产品索引
python src/vectorization/build_index.py --type product

# 构建所有索引
python src/vectorization/build_index.py --type all
```

**输出文件**：

| 数据类型 | FAISS 索引 | ID 映射 |
|---------|-----------|--------|
| tender | `data/index_tenders/tenders.index` | `data/index_tenders/tenders_ids.json` |
| product | `data/index/product.index` | `data/index/product_ids.json` |

## 完整流水线

```bash
# 1. 结构化数据（ETL 模块）
python src/etl/extract_structured.py --all
python src/etl/import_structured_db.py

# 2. 向量化
python src/vectorization/vectorize_data.py --type tender

# 3. 构建索引
python src/vectorization/build_index.py --type tender

# 4. 启动服务
python webapp/server_fastapi.py
```

## 索引格式

### FAISS 索引

使用 `faiss.IndexFlatIP`（内积索引），适用于归一化向量的余弦相似度搜索。

```python
import faiss
index = faiss.read_index("data/index_tenders/tenders.index")
```

### ID 映射

JSON 格式，与 FAISS 索引顺序对应：

```json
[
    {"tender_id": "1001", "project_name": "xxx", "buyer_name": "xxx"},
    {"tender_id": "1002", "project_name": "yyy", "buyer_name": "yyy"}
]
```

## 常见问题

**Q: 向量化失败**
```bash
# 检查 Embedding 服务
curl http://10.210.10.51:8022/v1/models
```

**Q: 索引构建后检索结果为空**
```bash
# 修复 ID 映射
python src/vectorization/repair_ids.py --type tender
```
