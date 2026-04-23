# 混合检索升级计划

## 项目背景

当前 `match_product` 模块使用基于规则的关键词匹配，存在以下局限：
- 无法理解语义相似性（如"车载互联"与"智能座舱"）
- 依赖精确关键词匹配
- 无法处理同义词、近义词

## 目标

用 **FAISS 向量检索 + BM25 关键词检索** 替换现有规则匹配，实现：
1. 语义理解能力
2. 更准确的匹配结果
3. 保持 API 兼容，不影响上层调用

---

## 技术选型

### MVP 阶段（当前）

| 组件 | 方案 | 说明 |
|------|------|------|
| 向量检索 | FAISS | Facebook 开源，零运维 |
| 关键词检索 | rank-bm25 | Python 原生实现 |
| 嵌入模型 | m3e-base / bge-m3 | 中文语义嵌入 |
| 存储 | 内存 Index | 启动时加载 |

### 规模化后（未来）

| 组件 | 方案 | 说明 |
|------|------|------|
| 向量 + 数据库 | Elasticsearch | 二合一，支持全文 + 向量 |
| 或 | Milvus | 专业向量数据库 |

---

## 架构设计

```
┌─────────────────────────────────────────────────────────┐
│  match_product/executor.py                               │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │              HybridSearch                          │ │
│  │  ┌──────────────────┐    ┌────────────────────┐   │ │
│  │  │   FAISS Index    │    │   BM25 Index       │   │ │
│  │  │   (向量相似度)    │    │   (关键词匹配)      │   │ │
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

## 文件结构

```
get_data/
├── src/
│   └── retrieval/
│       ├── __init__.py           # 新建
│       └── hybrid_search.py      # 新建 - 核心检索模块
├── tools/
│   └── match_product/
│       └── executor.py           # 重构 - 集成混合检索
├── tests/
│   └── match_product/
│       └── test_hybrid_search.py # 新建 - 测试用例
└── docs/
    └── hybrid_search_plan.md     # 本文档
```

---

## 实施步骤

### Step 1: 安装依赖

```bash
pip install faiss-cpu rank-bm25 sentence-transformers
```

### Step 2: 创建混合检索模块

**文件**: `src/retrieval/hybrid_search.py`

```python
class HybridSearch:
    """FAISS + BM25 混合检索"""
    
    def __init__(self, product_knowledge_base: dict)
    def add_documents(self, products: dict) -> None
    def search(self, query: str, top_k: int = 3) -> list
    def _build_faiss_index(self, embeddings: np.ndarray) -> faiss.Index
    def _build_bm25_index(self, documents: list) -> BM25Okapi
    def _rrf_fusion(self, faiss_scores: np.ndarray, bm25_scores: np.ndarray) -> np.ndarray
```

### Step 3: 重构产品知识库

**文件**: `tools/match_product/executor.py`

原结构：
```python
PRODUCT_MATCH_RULES = {
    "星闪芯片": {
        "customer_types": [...],
        "tech_keywords": [...]
    }
}
```

新结构：
```python
PRODUCT_KNOWLEDGE_BASE = {
    "星闪芯片": {
        "code": "STARFLASH",
        "description": "星闪芯片是一款短距无线通信芯片，支持 6Mbps 高速率，时延<100μs...",
        "customer_types": [...],
        "project_types": [...],
        "tech_keywords": [...],
        "talking_points": [...]
    }
}
```

### Step 4: 集成混合检索

修改 `calculate_match_score()` 函数：

```python
def calculate_match_score(product_name, product_rules, payload):
    # 构建查询文本
    query = f"""
    客户类型：{payload.get('customer_type_name', '')}
    项目类型：{payload.get('project_type_name', '')}
    技术关键词：{' '.join(payload.get('technical_keywords', []))}
    需求描述：{payload.get('requirement_text', '')}
    """
    
    # 调用混合检索
    searcher = HybridSearch.get_instance()
    matched_products, scores = searcher.search(query, top_k=3)
    
    return matched_products, scores
```

### Step 5: 测试验证

**文件**: `tests/match_product/test_hybrid_search.py`

测试用例：
1. 车厂客户 + 智能座舱 → 应匹配"星闪芯片"（高分）
2. 工控厂商 + 实时控制 → 应匹配"实时多核处理器"（高分）
3. 应急通信 + 抢险 → 应匹配"天通卫星基带"（高分）
4. 混合查询 vs 纯向量 vs 纯 BM25 对比

---

## 产品知识库描述模板

```python
"星闪芯片": {
    "description": """
    星闪芯片（NearLink）是一款高性能短距无线通信芯片，
    支持 6Mbps 传输速率（蓝牙的 6 倍），端到端时延低于 100 微秒，
    支持多设备同时连接。适用于智能座舱、穿戴设备、TWS 耳机、
    工业无线控制等场景。国产自主标准，供应链安全可控。
    """
}
```

---

## 分数融合算法

### RRF (Reciprocal Rank Fusion)

```python
def rrf_fusion(faiss_scores, bm25_scores, k=60):
    """
    RRF 分数融合公式：
    score = 1 / (k + rank_faiss) + 1 / (k + rank_bm25)
    """
    faiss_ranks = np.argsort(np.argsort(-faiss_scores))
    bm25_ranks = np.argsort(np.argsort(-bm25_scores))
    
    return 1 / (k + faiss_ranks) + 1 / (k + bm25_ranks)
```

### 加权融合（可选）

```python
final_score = 0.7 * normalized_faiss + 0.3 * normalized_bm25
```

---

## 测试计划

### 单元测试

```bash
python tests/match_product/test_hybrid_search.py
```

### 集成测试

```bash
python tools/match_product/executor.py << 'EOF'
{
    "customer_type": "AUTO_OEM",
    "customer_type_name": "车厂",
    "project_type": "SMART_COCKPIT",
    "project_type_name": "智能座舱",
    "technical_keywords": ["短距通信", "无线投屏"],
    "requirement_text": "需要车内多设备无线连接方案"
}
EOF
```

### 效果对比

| 测试用例 | 规则匹配 | 混合检索 | 改进 |
|----------|----------|----------|------|
| 车厂 + 座舱 | 星闪 (85 分) | 星闪 (0.92) | ✓ |
| 车厂 + 域控 | 多核 (80 分) | 多核 (0.89) | ✓ |
| 穿戴 + 手表 | 星闪 (75 分) | 星闪 (0.85) | ✓ |
| 应急 + 卫星 | 卫星 (90 分) | 卫星 (0.95) | ✓ |

---

## 验收标准

- [ ] 混合检索模块代码完成
- [ ] 产品知识库描述完善（3 款产品）
- [ ] 集成后 API 保持兼容
- [ ] 所有测试用例通过
- [ ] 匹配结果合理（符合业务预期）

---

## 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 嵌入模型加载失败 | 高 | 预下载模型到本地 |
| FAISS 索引构建错误 | 中 | 添加异常处理 |
| 匹配结果不合理 | 高 | 调整权重，添加日志 |
| 性能下降 | 中 | 缓存检索结果 |

---

## 时间估算

| 任务 | 预估时间 |
|------|----------|
| Step 1: 依赖安装 | 5 分钟 |
| Step 2: 混合检索模块 | 40 分钟 |
| Step 3: 产品知识库 | 20 分钟 |
| Step 4: 集成 | 30 分钟 |
| Step 5: 测试 | 25 分钟 |
| **总计** | **约 2 小时** |

---

## 后续优化

1. **嵌入模型微调** - 使用业务数据微调嵌入模型
2. **多向量索引** - 客户类型、项目类型分别建索引
3. **缓存层** - Redis 缓存高频查询
4. **异步检索** - 并发检索多款产品
5. **ES 迁移** - 数据量增长后迁移到 Elasticsearch

---

## 参考文档

- [FAISS 官方文档](https://faiss.ai/)
- [sentence-transformers](https://www.sbert.net/)
- [rank-bm25](https://github.com/dorianbrown/rank_bm25)
- [M3E 嵌入模型](https://huggingface.co/moka-ai/m3e-base)
- [BGE-M3 嵌入模型](https://huggingface.co/BAAI/bge-m3)
