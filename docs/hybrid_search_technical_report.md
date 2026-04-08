# 混合检索系统技术报告

> FAISS + BM25 实现产品销售匹配  
> 生成时间：2026-04-07  
> 版本：v1.1（jieba 分词）

---

## 1. 系统概述

### 1.1 背景

原 `match_product` 模块使用基于规则的关键词匹配，存在以下局限：
- 无法理解语义相似性（如"车载互联"与"智能座舱"）
- 依赖精确关键词匹配
- 无法处理同义词、近义词

### 1.2 目标

用 **FAISS 向量检索 + BM25 关键词检索** 替换现有规则匹配，实现：
1. 语义理解能力
2. 更准确的匹配结果
3. 保持 API 兼容，不影响上层调用

### 1.3 技术选型

| 组件 | 方案 | 说明 |
|------|------|------|
| 向量检索 | FAISS | Facebook 开源，零运维 |
| 关键词检索 | rank-bm25 | Python 原生实现 |
| 嵌入模型 | Qwen3-Embedding-0.6B | 本地部署，1024 维 |
| 存储 | 磁盘 Index | 启动时加载，无需重建 |

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────┐
│  tools/match_product/executor.py                         │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │              HybridSearch                          │ │
│  │  ┌──────────────────┐    ┌────────────────────┐   │ │
│  │  │   FAISS Index    │    │   BM25 Index       │   │ │
│  │  │   (向量相似度)    │    │   (关键词匹配)      │   │ │
│  │  │   1024 维向量      │    │   中文分词          │   │ │
│  │  └──────────────────┘    └────────────────────┘   │ │
│  │              ↓                    ↓                │ │
│  │  ┌────────────────────────────────────────────┐   │ │
│  │  │         RRF 分数融合 (0.7:0.3)              │   │ │
│  │  └────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                            ↓
              ┌─────────────────────────────┐
              │  返回匹配产品列表 (Top-K)    │
              └─────────────────────────────┘
```

---

## 3. 核心模块

### 3.1 文件结构

```
get_data/
├── src/
│   └── retrieval/
│       ├── __init__.py           # 模块初始化
│       └── hybrid_search.py      # 核心检索模块 (约 350 行)
├── tools/
│   └── match_product/
│       └── executor.py           # 产品匹配执行器 (已重构)
└── docs/
    └── hybrid_search_*.md        # 文档
```

### 3.2 HybridSearch 类

```python
class HybridSearch:
    """FAISS + BM25 混合检索"""

    def __init__(
        self,
        model_name: str = r"D:\models\Qwen3-Embedding-0.6B",
        rrf_k: int = 60,
        vector_weight: float = 0.5,
        bm25_weight: float = 0.5
    )

    def add_documents(self, product_knowledge_base: Dict[str, dict]) -> None
    def load_index(self, index_dir: str) -> bool  # 从磁盘加载已保存的索引
    def search(self, query: str, top_k: int = 3) -> List[Dict]
```

### 3.3 方法说明

| 方法 | 功能 | 说明 |
|------|------|------|
| `__init__()` | 初始化 | 加载嵌入模型，设置参数 |
| `add_documents()` | 添加文档 | 构建 FAISS 和 BM25 索引 |
| `load_index()` | 加载索引 | 从磁盘加载已保存的索引（快速启动） |
| `search()` | 执行检索 | 返回 Top-K 匹配结果 |
| `_get_vector_scores()` | 向量分数 | FAISS 内积相似度 |
| `_get_bm25_scores()` | BM25 分数 | 关键词匹配分数 |
| `_rrf_fusion()` | 分数融合 | RRF 算法融合两种分数 |

---

## 4. 核心技术

### 4.1 文本嵌入（Embedding）

使用 **Qwen3-Embedding-0.6B** 模型将文本转换为 1024 维向量：

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer(r"D:\models\Qwen3-Embedding-0.6B")
query_vector = model.encode("需要车载短距无线通信方案", normalize_embeddings=True)
# 输出：shape=(1024,), L2 归一化
```

**模型特点：**
- 通义千问团队开源
- 1024 维向量
- 中文语义理解能力强
- 本地部署，无需网络

### 4.2 FAISS 向量检索

```python
import faiss
import numpy as np

# 创建 Flat 索引（余弦相似度用内积）
index = faiss.IndexFlatIP(1024)

# 添加产品向量
product_embeddings = model.encode(product_documents, normalize_embeddings=True)
index.add(np.array(product_embeddings, dtype=np.float32))

# 查询
query_emb = model.encode([query], normalize_embeddings=True)
scores, indices = index.search(query_emb.astype(np.float32), top_k)
```

**为什么用 IndexFlatIP？**
- Flat：精确搜索，无近似
- IP：内积（Inner Product），等价于余弦相似度（向量已归一化）
- 产品数量少（3 款），不需要近似搜索

### 4.3 BM25 关键词检索

```python
from rank_bm25 import BM25Okapi
import jieba

# 中文分词：使用 jieba 精确模式
def tokenize_chinese(text):
    return jieba.lcut(text)

# 构建索引
tokenized_docs = [tokenize_chinese(doc) for doc in documents]
bm25_index = BM25Okapi(tokenized_docs)

# 查询
query_tokens = tokenize_chinese(query)
bm25_scores = bm25_index.get_scores(query_tokens)
```

**jieba 分词效果对比：**

| 文本 | 简单分词 | jieba 分词 |
|------|----------|------------|
| 星闪芯片是一款高性能短距无线通信芯片 | 星/闪/芯/片/是/一/款... | 星闪/芯片/是/一款/高性能/短距/无线通信/芯片 |
| 需要车内多设备无线连接方案 | 需/要/车/内/多/设/备... | 需要/车内/多/设备/无线/连接/方案 |

**jieba 分词优势：**
- 正确识别专业术语（如"无线通信"、"高性能"、"短距"）
- BM25 分数更合理，避免出现负分
- 测试数据：星闪芯片 BM25 分数从 0.12 提升至 4.79

**BM25 公式：**

$$score(D, Q) = \sum_{t \in Q} IDF(t) \times \frac{TF(t, D) \times (k1 + 1)}{TF(t, D) + k1 \times (1 - b + b \times \frac{|D|}{avgdl})}$$

### 4.4 RRF 分数融合

**RRF (Reciprocal Rank Fusion)** 公式：

$$score(d) = \frac{w_1}{k + rank_{vector}(d)} + \frac{w_2}{k + rank_{bm25}(d)}$$

**代码实现：**

```python
def _rrf_fusion(self, vector_scores, bm25_scores):
    k = self.rrf_k  # 默认 60
    n = len(vector_scores)

    # 计算排名（分数越高排名越靠前）
    vector_ranks = np.argsort(np.argsort(-vector_scores)) + 1
    bm25_ranks = np.argsort(np.argsort(-bm25_scores)) + 1

    # RRF 融合
    rrf_scores = (
        self.vector_weight / (k + vector_ranks) +
        self.bm25_weight / (k + bm25_ranks)
    )
    return rrf_scores
```

**参数说明：**
- `k=60`：平滑参数，避免分母为零
- `vector_weight=0.5`：向量检索权重（平权）
- `bm25_weight=0.5`：关键词检索权重（平权）

---

## 5. 产品知识库

### 5.1 数据结构

```python
PRODUCT_KNOWLEDGE_BASE = {
    "starflash": {
        "name": "星闪芯片",
        "code": "STARFLASH",
        "description": "星闪芯片（NearLink）是一款高性能短距无线通信芯片...",
        "customer_types": ["AUTO_OEM", "PHONE_OEM", "WEARABLE_OEM"],
        "project_types": ["SMART_COCKPIT", "WEARABLE_DEVICE"],
        "tech_keywords": ["蓝牙", "WiFi", "短距", "无线", "NearLink", ...],
        "talking_points": ["6Mbps 高速率", "时延<100μs", ...],
        "applications": {"AUTO_OEM": "智能座舱 - 多设备无线互联", ...}
    },
    "multicore": { ... },  # 实时多核处理器
    "satellite": { ... }   # 天通卫星基带
}
```

### 5.2 文档构建

```python
def _build_document_text(self, info: dict) -> str:
    parts = []
    if "name" in info:
        parts.append(f"产品名称：{info['name']}")
    if "description" in info:
        parts.append(f"产品描述：{info['description']}")
    if "tech_keywords" in info:
        parts.append(f"技术关键词：{' '.join(info['tech_keywords'])}")
    if "customer_types" in info:
        parts.append(f"适用客户：{' '.join(info['customer_types'])}")
    if "project_types" in info:
        parts.append(f"适用项目：{' '.join(info['project_types'])}")
    return " | ".join(parts)
```

**示例输出：**
```
产品名称：星闪芯片 | 产品描述：星闪芯片（NearLink）是一款高性能短距无线通信芯片... | 技术关键词：蓝牙 WiFi 短距 无线 NearLink... | 适用客户：AUTO_OEM PHONE_OEM WEARABLE_OEM | 适用项目：SMART_COCKPIT WEARABLE_DEVICE
```

---

## 6. 匹配流程

### 6.1 查询构建

```python
def calculate_match_score(product_id, product_rules, payload):
    query_parts = []

    if payload.get("customer_type_name"):
        query_parts.append(f"客户类型：{payload['customer_type_name']}")
    if payload.get("project_type_name"):
        query_parts.append(f"项目类型：{payload['project_type_name']}")
    if payload.get("technical_keywords"):
        query_parts.append(f"技术关键词：{' '.join(payload['technical_keywords'])}")
    if payload.get("requirement_text"):
        query_parts.append(f"需求描述：{payload['requirement_text'][:500]}")

    query = " | ".join(query_parts)
```

**示例查询：**
```
客户类型：车厂 | 项目类型：智能座舱 | 技术关键词：短距通信 无线投屏 | 需求描述：需要车内多设备无线连接方案
```

### 6.2 检索执行

```python
searcher = get_hybrid_searcher()
results = searcher.search(query, top_k=3)

# 返回结果
[
    {
        "product_id": "starflash",
        "score": 1.0,          # 归一化后的综合分数
        "vector_score": 0.58,  # 向量相似度
        "bm25_score": 0.12,    # BM25 分数
        "data": {...}          # 产品详细信息
    },
    ...
]
```

### 6.3 分数转换

```python
# 0-1 → 0-100
score = int(result["score"] * 100)
reason = f"混合检索匹配（向量 {vector_score:.3f} + BM25 {bm25_score:.3f}）"
```

---

## 7. 测试验证

### 7.1 测试用例

```python
payload = {
    "customer_type": "AUTO_OEM",
    "customer_type_name": "车厂",
    "project_type": "SMART_COCKPIT",
    "project_type_name": "智能座舱",
    "technical_keywords": ["短距通信", "无线投屏"],
    "requirement_text": "需要车内多设备无线连接方案"
}
```

### 7.2 测试结果（加载磁盘索引）

**启动日志：**
```
[HybridSearch] 模型加载完成：D:\models\Qwen3-Embedding-0.6B
[HybridSearch] 向量维度：1024
[HybridSearch] FAISS 索引已加载：data/index/faiss.index
[HybridSearch] BM25 索引已加载：data/index/bm25.pkl
[HybridSearch] 索引加载完成：10 个产品
```

**匹配结果：**

| 产品 | 分数 | 向量分 | BM25 分 | 排名 |
|------|------|--------|---------|------|
| **星闪芯片** | 100 | 0.583 | 24.026 | 1 |
| 实时多核处理器 | 98 | 0.530 | 12.913 | 2 |
| DX-S702 高低轨双模芯片 | 95 | 0.382 | 12.673 | 3 |

**对比（jieba vs 简单分词）：**

| 产品 | BM25（简单分词） | BM25（jieba） | 改进 |
|------|------------------|---------------|------|
| 星闪芯片 | 0.123 | 4.795 | ⬆️ 39 倍 |
| 实时多核处理器 | -7.158 | 0.090 | ⬆️ 正常化 |
| 天通卫星基带 | -5.598 | 1.597 | ⬆️ 正常化 |

**分析：**
- jieba 正确识别了"无线通信"、"高性能"、"短距"等专业术语
- BM25 分数从负分变为正分，更符合预期
- 星闪芯片的 BM25 分数显著提升（4.795），与向量分数（0.580）共同作用，确保排名第一

**jieba 分词示例：**
```
输入：星闪芯片是一款高性能短距无线通信芯片
输出：星闪 / 芯片 / 是 / 一款 / 高性能 / 短距 / 无线通信 / 芯片
```

### 7.3 降级测试

当模型加载失败时，自动降级为规则匹配：

```python
try:
    searcher = get_hybrid_searcher()
    results = searcher.search(query, top_k=3)
except Exception as e:
    print(f"[WARN] 混合检索失败：{e}，降级为规则匹配")
    return _fallback_rule_match(product_id, product_rules, payload)
```

---

## 8. 性能指标

### 8.1 响应时间

| 阶段 | 时间 |
|------|------|
| 模型加载（冷启动） | ~2-3 秒 |
| 索引加载（磁盘） | <0.1 秒 |
| 单次查询 | ~50-100ms |

**对比：重建索引 vs 加载索引**

| 方式 | 时间 |
|------|------|
| 重建索引（10 个产品） | ~90 秒 |
| 加载磁盘索引 | <0.1 秒 |
| **提升** | **900 倍 +** |

### 8.2 资源占用

| 资源 | 占用 |
|------|------|
| 内存 | ~500MB（模型）+ ~1MB（索引） |
| CPU | 查询时短暂升高 |
| 磁盘 | ~1.2GB（模型文件） |

---

## 9. 优缺点分析

### 9.1 优点

1. **语义理解** - 能理解"车载互联"与"智能座舱"的语义关联
2. **快速启动** - 加载磁盘索引仅需 0.1 秒，无需每次重建
3. **降级容错** - 索引加载失败时自动降级为从 JSON 构建
4. **API 兼容** - 返回格式与原版一致，上层无感知

### 9.2 缺点

1. **磁盘占用** - 索引文件约 90KB（faiss.index + bm25.pkl）
2. **产品少优势不明显** - 仅 10 款产品，规则匹配也能工作
3. **无法解释** - 向量相似度是黑盒，不如规则透明

---

## 10. 后续优化方向

### 10.1 短期优化

| 优化项 | 说明 | 优先级 | 状态 |
|--------|------|--------|------|
| 索引持久化 | 将 FAISS 和 BM25 索引保存到磁盘 | 高 | ✅ 已完成 |
| 中文分词优化 | 集成 jieba 分词，提升 BM25 效果 | 中 | ✅ 已完成 |
| 权重调优 | 根据实际效果调整 vector_weight | 中 | 待实现 |

### 10.2 长期优化

| 优化项 | 说明 | 优先级 |
|--------|------|--------|
| 微调嵌入模型 | 使用业务数据微调，提升领域适配性 | 中 |
| 多向量索引 | 客户类型、项目类型分别建索引 | 低 |
| 缓存层 | Redis 缓存高频查询结果 | 低 |
| ES 迁移 | 数据量增长后迁移到 Elasticsearch | 低 |

---

## 11. 参考文档

- [FAISS 官方文档](https://faiss.ai/)
- [sentence-transformers](https://www.sbert.net/)
- [rank-bm25](https://github.com/dorianbrown/rank_bm25)
- [Qwen3-Embedding](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- [RRF 论文](https://plg.uwaterloo.ca/~gvcormack/cormacksigir09-rrf.pdf)

---

## 附录 A：核心代码清单

### A.1 混合检索主流程

```python
# 1. 初始化检索器
searcher = HybridSearch(model_name=r"D:\models\Qwen3-Embedding-0.6B")

# 2. 添加产品文档
searcher.add_documents(PRODUCT_KNOWLEDGE_BASE)

# 3. 执行查询
query = "客户类型：车厂 | 项目类型：智能座舱 | 技术关键词：短距通信"
results = searcher.search(query, top_k=3)

# 4. 处理结果
for r in results:
    print(f"{r['product_id']}: {r['score']:.2f}")
```

### A.2 RRF 融合公式实现

```python
def _rrf_fusion(self, vector_scores, bm25_scores):
    k = self.rrf_k  # 60
    vector_ranks = np.argsort(np.argsort(-vector_scores)) + 1
    bm25_ranks = np.argsort(np.argsort(-bm25_scores)) + 1
    return (
        self.vector_weight / (k + vector_ranks) +
        self.bm25_weight / (k + bm25_ranks)
    )
```

---

**报告完**
