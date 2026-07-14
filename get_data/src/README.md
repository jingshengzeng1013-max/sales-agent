# 源码目录 (`src/`)

> 政府采购招投标销售智能助手 —— 核心源码。涵盖数据采集、结构化抽取、客户画像、混合检索、智能 Agent 及 API 服务等完整链路。

## 目录结构

```
src/
├── config.py                  # 全局配置中心（路径、LLM、爬虫、Embedding 等）
├── models.py                  # 结构化数据 Schema 定义（单一真相源）
│
├── agent/                     # Agentic RAG 销售助手
│   ├── sales_agent.py         #   核心 Agent（多轮对话 + 工具调用）
│   └── skills/                #   可插拔 Skill 架构
│       ├── base.py            #     Skill 基类 (BaseSkill + SkillResult)
│       ├── registry.py        #     Skill 注册中心（单例模式）
│       ├── customer_profile.py#     客户画像查询 Skill
│       ├── sales_suggestions.py#    销售建议 & 项目分析 Skill
│       └── search_tenders.py  #     招标搜索 Skill
│
├── analysis/                  # 客户画像 & 销售分析
│   ├── sales_advisor.py       #   AI 销售建议引擎（LLM + JSONL 缓存）
│   ├── generate_customer_profiles.py  # 客户画像聚合生成器
│   ├── crm_loader.py          #   CRM 数据加载器（Excel → 结构化）
│   ├── profile_enhancer.py    #   画像增强器（融合 CRM + 招标数据）
│   └── profile_unifier.py     #   画像格式统一器
│
├── api/                       # FastAPI Web 服务
│   ├── main.py                #   应用入口
│   ├── logging_config.py      #   日志配置
│   ├── routes/                #   路由层
│   │   ├── search.py          #     搜索路由
│   │   ├── stats.py           #     统计路由
│   │   └── tenders.py         #     招标详情路由
│   ├── schemas/               #   Pydantic 数据模型
│   │   └── tender.py
│   └── services/              #   数据库查询服务
│       └── db_service.py
│
├── crawler/                   # 政府采购网爬虫
│   ├── ccgp_crawler.py        #   列表页爬虫
│   ├── crawl_detail.py        #   详情页爬虫（串行/并发）
│   ├── download_attachments.py#   附件下载器
│   ├── batch_crawl_attachments.py  # 批量附件链接提取
│   ├── proxy_manager.py       #   代理管理器（青果网络）
│   └── test_proxy_api.py      #   代理可用性测试
│
├── etl/                       # ETL 数据处理
│   ├── schema.sql             #   数据库 Schema DDL
│   ├── aggregate_projects.py  #   项目聚合（多公告 → 单项目）
│   ├── core/                  #   核心抽取
│   │   ├── extract_structured.py  # LLM 结构化字段抽取
│   │   └── prompt_extract.md  #   LLM 抽取 Prompt 模板
│   ├── chunks/                #   RAG 分块
│   │   ├── generate_chunks.py #   分块数据生成
│   │   └── import_attachment_chunks.py  # 附件内容分块入库
│   ├── attachments/           #   附件处理
│   │   └── extract_attachment_specs.py  # 附件技术参数提取（PDF视觉+文本LLM）
│   └── utils/                 #   ETL 工具
│       └── llm_client.py      #   LLM 客户端封装
│
├── integration/               # 外部系统集成
│   └── wechat_service.py      #   微信客服服务（模板消息+用户查询）
│
├── retrieval/                 # 混合检索引擎
│   └── retriever.py           #   双路检索器（FAISS + BM25 + RRF 融合）
│
├── storage/                   # 数据入库模块
│   ├── cli.py                 #   CLI 入口
│   ├── import_tenders.py      #   招标数据入库
│   ├── import_structured.py   #   结构化数据入库
│   ├── import_customer_profiles.py  # 客户画像入库
│   └── migrate_uuids.py       #   UUID 迁移脚本
│
├── utils/                     # 通用工具模块
│   ├── jsonl_helper.py        #   JSONL 读写工具
│   ├── logger.py              #   日志配置模块
│   └── manage_logs.py         #   日志管理 CLI
│
└── vectorization/             # 向量化 & 索引构建
    ├── vectorize_data.py      #   文本 → 向量（Embedding API）
    └── build_index.py         #   FAISS 索引构建
```

---

## 模块说明

### 1. `config.py` — 全局配置中心

集中管理所有路径、LLM 提供商、爬虫、Embedding 等配置。

| 配置项 | 说明 |
|--------|------|
| `BASE_DIR` | 项目根路径 `get_data/` |
| `DB_PATH` | SQLite 数据库 `data/ccgp_data.db` |
| `LLM_PROVIDERS` | 统一模型配置映射（local / deepseek） |
| `CRAWLER_CONFIG` | 爬虫参数（URL、关键词、代理、时间范围等） |
| `EMBEDDING_CONFIG` | Embedding 服务地址与模型 |
| `get_llm_config()` | 按提供商获取 LLM 配置 |

### 2. `models.py` — 结构化数据 Schema

定义结构化抽取字段、SQLite 表结构和 JSON Schema 的**单一真相源**。

- `FINAL_RESULT_TEMPLATE` — 最终输出字段模板
- `LLM_EXTRACT_TEMPLATE` — LLM 抽取字段模板
- `STRUCTURED_RESULT_SCHEMA` — JSON Schema 校验定义
- `get_empty_structured_payload()` — 生成空骨架
- `validate_structured_payload()` — 轻量校验

### 3. `agent/` — Agentic RAG 销售助手

基于 Skill 架构的智能 Agent，支持多轮对话、工具自动调用、迭代检索和自我纠错。

| 组件 | 说明 |
|------|------|
| `SalesAgent` | 核心 Agent 类，管理对话历史与工具调度 |
| `BaseSkill` | Skill 抽象基类（定义 name、description、parameters、execute） |
| `SkillRegistry` | Skill 注册中心（单例模式） |
| `SearchTendersSkill` | 招标搜索（调用 DualRetriever） |
| `CustomerProfileSkill` | 客户画像查询（模糊匹配） |
| `SalesSuggestionsSkill` | 销售建议生成（调用 SalesAdvisor） |
| `ProjectAnalysisSkill` | 项目深度分析 |

```python
from src.agent import SalesAgent, create_agent

agent = SalesAgent()
result = agent.run("帮我找最近通信类的招标")
```

### 4. `analysis/` — 客户画像 & 销售分析

| 模块 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `SalesAdvisor` | AI 销售建议引擎 | 项目数据 + 客户画像 | Markdown 建议文档 |
| `generate_customer_profiles` | 客户画像聚合 | `tender_structured` 表 | `customer_profiles.jsonl` |
| `CRMLoader` | CRM 数据加载 | Excel（商机/线索） | 结构化字典列表 |
| `ProfileEnhancer` | 画像增强 | 招标画像 + CRM 数据 | 增强版画像 |
| `ProfileUnifier` | 画像格式统一 | 多源画像 | 统一格式画像 |

### 5. `api/` — FastAPI Web 服务

提供 RESTful API 接口，支持招标查询、搜索筛选、统计分析。

| 路由 | 方法 | 说明 |
|------|------|------|
| `GET /` | - | API 根路径 |
| `GET /health` | - | 健康检查 |
| `POST /api/search` | SearchRequest | 搜索招标项目（分页+筛选） |
| `GET /api/search/filters` | - | 获取筛选选项 |
| `GET /api/tenders/{id}` | - | 招标详情（含结构化数据） |
| `GET /api/tenders/{id}/chunks` | - | 招标 RAG 分块 |
| `GET /api/stats/overview` | - | 统计概览 |
| `GET /api/stats/by_province` | - | 按省份统计 |
| `GET /api/stats/by_type` | - | 按公告类型统计 |

启动方式：

```bash
cd src/api && python main.py
# 或
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

### 6. `crawler/` — 政府采购网爬虫

从中国政府采购网 (ccgp.gov.cn) 采集招标数据，支持代理轮换和 TLS 指纹绕过。

| 脚本 | 功能 |
|------|------|
| `ccgp_crawler.py` | 列表页爬取 → `tenders_list.jsonl` |
| `crawl_detail.py` | 详情页爬取（8通道并发） → `tenders_detail.jsonl` |
| `download_attachments.py` | 附件文件下载 → `data/attachment/` |
| `batch_crawl_attachments.py` | 批量附件链接提取 → `tenders_attachments.jsonl` |
| `proxy_manager.py` | 代理池管理（青果网络，自动刷新） |

```bash
# 完整爬取流程
python src/crawler/ccgp_crawler.py --pages 100
python src/crawler/crawl_detail.py
python src/crawler/batch_crawl_attachments.py
python src/crawler/download_attachments.py
```

### 7. `etl/` — ETL 数据处理

将原始招标数据转化为结构化信息，是系统的核心数据处理管道。

| 子模块 | 文件 | 功能 |
|--------|------|------|
| **核心抽取** | `core/extract_structured.py` | LLM 结构化字段抽取（支持 DeepSeek / 本地模型，48路并发） |
| | `core/prompt_extract.md` | LLM 抽取 Prompt 模板 |
| **RAG 分块** | `chunks/generate_chunks.py` | 生成 5 类 chunks：title / content_summary / contact / requirement / attachment |
| | `chunks/import_attachment_chunks.py` | 附件内容智能分块入库（1500字/块，10%重叠） |
| **附件处理** | `attachments/extract_attachment_specs.py` | PDF 视觉模型提取表格 + 文本 LLM 提取技术参数 |
| **项目聚合** | `aggregate_projects.py` | 多公告聚合一项目，关联客户画像 |
| **工具** | `utils/llm_client.py` | 统一 LLM 客户端封装 |

```bash
# 标准 ETL 流程
python src/etl/core/extract_structured.py --all --provider deepseek
python src/storage/import_structured.py --mode replace
python src/etl/chunks/generate_chunks.py --all --replace
python src/etl/aggregate_projects.py
```

### 8. `retrieval/` — 混合检索引擎

基于 FAISS 向量检索 + BM25 关键词检索的双路检索，使用 RRF 算法融合结果。

**核心类**：`DualRetriever`

| 参数 | 说明 |
|------|------|
| `data_type` | `"product"` 或 `"tender"` |
| `vector_weight` | 向量检索权重（默认 0.5） |
| `bm25_weight` | BM25 权重（默认 0.5） |
| `aggregate_by_project` | 是否按项目汇总（招标检索默认开启） |
| `exclude_won` | 排除已中标项目 |
| `client_value_weight` | 客户价值加权系数 |

```python
from src.retrieval.retriever import DualRetriever

retriever = DualRetriever(data_type="tender")
results = retriever.hybrid_search("交换机 网络设备", top_k=20)
```

### 9. `storage/` — 数据入库模块

将 JSON/JSONL 数据导入 SQLite 数据库。

| 脚本 | 功能 |
|------|------|
| `import_tenders.py` | 列表/详情/附件入库 + `import_all()` 一键导入 |
| `import_structured.py` | 结构化数据入库（自动建表+修复） |
| `import_customer_profiles.py` | 客户画像入库 |
| `migrate_uuids.py` | UUID 填充迁移 |
| `cli.py` | CLI 入口 |

```bash
# CLI 用法
python src/storage/cli.py init       # 初始化表结构
python src/storage/cli.py all        # 一键导入全部
python src/storage/cli.py list       # 仅导入列表
python src/storage/cli.py detail     # 仅更新详情
```

### 10. `utils/` — 通用工具模块

| 工具 | 说明 |
|------|------|
| `jsonl_helper.py` | JSONL 文件读写（`load_jsonl` / `save_jsonl` / `save_jsonl_single`） |
| `logger.py` | 统一日志配置（`setup_logger` / `get_logger` / `cleanup_old_logs`） |
| `manage_logs.py` | 日志管理 CLI（list / clean / tail） |

### 11. `vectorization/` — 向量化 & 索引构建

| 模块 | 功能 |
|------|------|
| `vectorize_data.py` | 调用 Embedding API 将文本转为向量 |
| `build_index.py` | 构建 FAISS `IndexFlatIP` 索引 |

```bash
# 向量化 + 构建索引
python src/vectorization/vectorize_data.py --type tender
python src/vectorization/build_index.py --type tender
```

### 12. `integration/` — 外部系统集成

| 模块 | 功能 |
|------|------|
| `wechat_service.py` | 微信客服服务（异步 httpx 客户端，支持模板消息发送、用户查询、招标通知广播） |

---

## 完整数据流水线

```
政府采购网
    │
    ├─→ [crawler] 爬取列表/详情/附件
    │       │
    │       └─→ JSONL 数据文件
    │               │
    │               ├─→ [storage] 导入 SQLite
    │               │
    │               └─→ [etl/core] LLM 结构化抽取
    │                       │
    │                       ├─→ [storage] 结构化数据入库
    │                       │
    │                       ├─→ [etl/chunks] RAG 分块生成
    │                       │
    │                       ├─→ [etl/attachments] 附件技术参数提取
    │                       │
    │                       └─→ [analysis] 客户画像生成 + CRM 增强
    │                               │
    │                               └─→ [storage] 画像入库
    │
    ├─→ [vectorization] 文本向量化 + FAISS 索引构建
    │
    ├─→ [retrieval] FAISS + BM25 双路混合检索
    │
    ├─→ [agent] Agentic RAG 销售助手（多轮对话 + Skill 调用）
    │
    └─→ [api] FastAPI 服务对外暴露接口
```

---

## 数据库表关系

```
tenders                    ← 原始招标数据
    │
    ├── 1:1 → tender_structured   ← LLM 结构化抽取结果
    │
    ├── 1:N → tender_chunks      ← RAG 检索分块
    │
    └── 1:N → tender_attachments ← 附件链接

customer_profiles          ← 客户画像数据
```

---

## LLM 配置

在 `config.py` 中统一管理，支持多提供商切换：

| 提供商 | 配置键 | 默认模型 | 用途 |
|--------|--------|----------|------|
| Local | `LOCAL_LLM_CONFIG` | Kimi-K2.5 | Agent、销售建议、附件提取 |
| DeepSeek | `DEEPSEEK_CONFIG` | deepseek-chat | 结构化抽取（推荐） |
| DashScope | `DASHSCOPE_CONFIG` | qwen3.5-plus | 备用 |
| Embedding | `EMBEDDING_CONFIG` | Qwen3-Embedding-0.6B | 向量化检索 |

环境变量切换：

```bash
# 切换抽取用 LLM
export LLM_PROVIDER=deepseek   # 或 local
export EXTRACT_LLM_PROVIDER=deepseek
```

---

## 快速开始

```bash
# 1. 爬取数据
python src/crawler/ccgp_crawler.py
python src/crawler/crawl_detail.py

# 2. 入库
python src/storage/cli.py all

# 3. LLM 结构化抽取
python src/etl/core/extract_structured.py --all --provider deepseek

# 4. 结构化数据入库
python src/storage/import_structured.py --mode replace

# 5. 生成 RAG 分块
python src/etl/chunks/generate_chunks.py --all --replace

# 6. 生成客户画像
python src/analysis/generate_customer_profiles.py

# 7. 向量化 & 构建索引
python src/vectorization/vectorize_data.py --type tender
python src/vectorization/build_index.py --type tender

# 8. 启动 API 服务
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```
