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

### 2. 数据采集

```bash
cd get_data

# 采集招标公告列表
python -m src.crawler.ccgp_crawler

# 爬取详情页
python -m src.crawler.crawl_detail

# AI 结构化抽取
python -m src.etl.core.extract_structured --limit 50

# 项目聚合
python -m src.etl.aggregate_projects
```

### 3. 构建索引

```bash
# 向量化数据
python -m src.vectorization.vectorize_data --type tender

# 构建检索索引
python -m src.vectorization.build_index --type tender
```

### 4. 启动服务

```bash
python webapp/server_fastapi.py
```

访问地址：
- 本地：`http://127.0.0.1:8103/static/demo.html`
- 完整版：`http://127.0.0.1:8103/static/index.html`

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

## 文档目录

### 入门指南
| 文档 | 说明 |
|------|------|
| [快速开始指南](get_data/docs/01_入门指南/README.md) | 5 分钟快速上手 |
| [LLM 抽取新手指南](get_data/docs/01_入门指南/LLM%20抽取新手指南.md) | 结构化抽取入门 |
| [LLM API 配置指南](get_data/docs/01_入门指南/LLM%20API%20配置指南.md) | DeepSeek/本地 LLM 配置 |
| [Web 前端使用指南](get_data/docs/01_入门指南/Web%20前端使用指南.md) | 界面功能说明 |

### RAG 与检索
| 文档 | 说明 |
|------|------|
| [MVP RAG 实施方案](get_data/docs/02_RAG%20方案/MVP_RAG_实施方案.md) | RAG 系统设计 |
| [向量检索方案设计](get_data/docs/02_RAG%20方案/向量检索方案设计.md) | FAISS + BM25 混合检索 |
| [混合检索技术报告](../../docs/hybrid_search_technical_report.md) | 检索技术细节 |
| [混合检索方案](../../docs/hybrid_search_plan.md) | 检索方案概览 |

### 架构与流程
| 文档 | 说明 |
|------|------|
| [项目架构说明](get_data/docs/03_架构设计/项目架构说明.md) | 系统架构概述 |
| [项目详细流程](get_data/docs/03_架构设计/项目详细流程.md) | 数据处理流程 |
| [数据流水线指南](../../docs/PIPELINE_GUIDE.md) | 完整数据处理流程 |

### 工具使用
| 文档 | 说明 |
|------|------|
| [日志系统说明](get_data/docs/03_工具使用/日志系统说明.md) | 日志配置与使用 |

### 技术文档
| 文档 | 说明 |
|------|------|
| [附件下载与解析流程](get_data/docs/04_技术文档/附件下载与解析流程.md) | 附件处理说明 |
| [附件链接修复说明](get_data/docs/04_技术文档/附件链接修复说明.md) | 链接修复指南 |
| [阿里云 LLM 配置](get_data/docs/04_技术文档/ALIYUN_LLM_SETUP.md) | 阿里云模型配置 |

### 部署运维
| 文档 | 说明 |
|------|------|
| [部署指南](get_data/docs/05_部署运维/部署指南.md) | 生产环境部署 |
| [运维手册](get_data/docs/05_部署运维/运维手册.md) | 日常运维操作 |
| [常见问题排查](get_data/docs/05_部署运维/常见问题排查.md) | 问题诊断与解决 |

### 开发指南
| 文档 | 说明 |
|------|------|
| [项目结构说明](get_data/docs/06_开发指南/项目结构说明.md) | 代码结构详解 |
| [代码规范](get_data/docs/06_开发指南/代码规范.md) | 开发规范与约定 |
| [模块开发教程](get_data/docs/06_开发指南/模块开发教程.md) | 新模块开发指南 |

### 业务方案
| 文档 | 说明 |
|------|------|
| [客户画像与智能拓客方案](docs/客户画像与智能拓客方案.md) | 客户画像设计 |
| [客户画像参数说明](docs/客户画像参数说明.md) | 画像字段定义 |
| [招标搜索关键词指南](docs/招标搜索关键词指南.md) | 爬虫关键词参考 |
| [客服接口文档](docs/客服接口文档.md) | 微信客服 API |

### 交接文档
| 文档 | 说明 |
|------|------|
| [项目交接说明](get_data/docs/项目交接说明.md) | 项目交接清单 |

---

## 模块文档

| 模块 | 文档 |
|------|------|
| 爬虫 | [get_data/src/crawler/README.md](get_data/src/crawler/README.md) |
| ETL | [get_data/src/etl/README.md](get_data/src/etl/README.md) |
| 检索 | [get_data/src/retrieval/README.md](get_data/src/retrieval/README.md) |
| 向量化 | [get_data/src/vectorization/README.md](get_data/src/vectorization/README.md) |
| 分析 | [get_data/src/analysis/README.md](get_data/src/analysis/README.md) |
| Web 服务 | [get_data/webapp/README.md](get_data/webapp/README.md) |

---

*Last Updated: 2026-04-27*
