# 混合检索方案

## 概述

本系统采用 **FAISS 向量检索 + BM25 关键词检索** 的双路混合检索架构，用于招标数据的智能匹配。

---

## 技术选型

| 组件 | 方案 | 说明 |
|------|------|------|
| 向量检索 | FAISS | Facebook 开源，零运维 |
| 关键词检索 | rank-bm25 | Python 原生实现 |
| 嵌入模型 | Qwen3-Embedding-0.6B | 本地部署，1024 维 |
| 分词 | jieba | 中文分词 |

---

## 架构设计

```
┌─────────────────────────────────────────────────────────┐
│           src/retrieval/retriever.py                     │
│                   DualRetriever 类                       │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │              hybrid_search()                        │ │
│  │  ┌──────────────────┐    ┌────────────────────┐   │ │
│  │  │   FAISS Index    │    │   BM25 Index       │   │ │
│  │  │   (向量相似度)    │    │   (关键词匹配)      │   │ │
│  │  └──────────────────┘    └────────────────────┘   │ │
│  │              ↓                    ↓                │ │
│  │  ┌────────────────────────────────────────────┐   │ │
│  │  │         RRF 分数融合 (默认 0.5:0.5)        │   │ │
│  │  └────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                            ↓
              ┌─────────────────────────────┐
              │  返回匹配结果 (支持按项目汇总) │
              └─────────────────────────────┘
```

---

## 核心文件

```
get_data/src/
├── retrieval/
│   ├── retriever.py          # 双路检索器 (DualRetriever)
│   └── README.md
├── vectorization/
│   ├── vectorize_data.py    # 向量化脚本
│   └── build_index.py        # 索引构建
└── config.py                 # 配置 (EMBEDDING_CONFIG)
```

---

## 使用示例

### Python 调用

```python
from src.retrieval.retriever import DualRetriever

# 初始化招标检索器
retriever = DualRetriever(data_type="tender")

# 执行混合检索
results = retriever.hybrid_search(
    query="交换机 采购 北京",
    top_k=10,
    province="北京",              # 可选：地区筛选
    notice_type="招标",           # 可选：公告类型
    aggregate_by_project=True,     # 按项目汇总
    exclude_won=False,            # 是否排除已中标
    vector_weight=0.5,            # 向量权重
    bm25_weight=0.5              # BM25 权重
)

# 打印结果
for r in results:
    print(f"{r['score']:.2f} - {r['data'].get('project_name_std')}")
```

### 命令行调用

```bash
cd D:\sales_agent\get_data
python -m src.retrieval.retriever
```

---

## RRF 分数融合

**公式：**

```
score(d) = vector_weight / (k + rank_vector(d)) + bm25_weight / (k + rank_bm25(d))
```

其中 `k=60` 为平滑参数。

---

## 后续优化方向

1. **权重调优** - 根据实际效果调整 `vector_weight` 和 `bm25_weight`
2. **缓存层** - Redis 缓存高频查询结果
3. **ES 迁移** - 数据量增长后迁移到 Elasticsearch

---

*文档更新时间：2026-04-27*
