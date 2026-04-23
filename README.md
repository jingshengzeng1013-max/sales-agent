# Sales Agent

> 政府采购招投标数据智能销售助手 — 基于 Agentic RAG 架构的招标情报系统

---

## 项目简介

Sales Agent 是一款面向销售团队的智能招标情报系统，自动化采集中国政府采购网数据，融合向量检索与关键词检索技术，帮助团队快速发现高价值项目机会。

**核心能力**：数据爬取 → AI 结构化提取 → 项目生命周期聚合 → 双路混合检索 → 销售建议生成

---

## 核心架构

### 技术栈

| 层级 | 技术 |
|------|------|
| 数据采集 | Python 爬虫 + 代理池 |
| 数据处理 | DeepSeek LLM 结构化抽取 |
| 向量数据库 | FAISS + BM25 混合检索 |
| 后端服务 | FastAPI |
| 前端 | Tailwind CSS + Vanilla JS |

### 项目模块

```
sales_agent/
├── get_data/               # 数据采集与处理核心模块
│   ├── src/
│   │   ├── crawler/        # 爬虫模块
│   │   ├── etl/            # 数据清洗与项目聚合
│   │   ├── retrieval/      # 双路检索器 (FAISS + BM25)
│   │   ├── vectorization/  # 向量化与索引构建
│   │   ├── analysis/       # AI 销售建议与客户画像
│   │   └── storage/        # 数据存储
│   └── webapp/             # Web 服务与前端
├── docs/                   # 项目文档
└── README.md              # 本文件
```

---

## 快速开始

### 1. 安装依赖

```bash
cd get_data
pip install -r requirements.txt
```

### 2. 初始化与数据采集

```bash
# 重置数据库
python src/utils/reset_db.py

# 采集数据
python src/crawler/ccgp_crawler.py
python src/crawler/crawl_detail.py

# AI 结构化抽取
python src/etl/core/extract_structured.py --all

# 项目聚合
python src/etl/aggregate_projects.py

# 构建索引
python src/vectorization/vectorize_data.py
python src/vectorization/build_index.py
```

### 3. 启动服务

```bash
python webapp/server_fastapi.py
```

访问地址：
- 本地：`http://127.0.0.1:8103/static/demo.html`
- 局域网：`http://[你的IP]:8103/static/demo.html`

---

## 核心功能

### 项目生命周期全追踪
自动聚合同一项目的招标公告、中标公告、更正公告、终止公告，实时显示项目状态与时间轴。

### 双路混合检索
- **向量检索 (FAISS)**：语义理解搜索
- **关键词检索 (BM25)**：精确匹配
- **RRF 融合**：智能合并结果

### AI 销售建议
基于客户历史数据与项目特征，LLM 自动生成个性化销售建议与报价策略。

---

## 文档

- [数据采集说明](get_data/src/crawler/README.md)
- [ETL 处理说明](get_data/src/etl/README.md)
- [检索模块说明](get_data/src/retrieval/README.md)
- [Web 服务说明](get_data/webapp/README.md)

---

*Last Updated: 2026-04-21*
