# 政府采购招投标数据系统 (Sales Agent)

> 一键爬取中国政府采购网招标公告，自动提取结构化数据 + 附件解析 + 项目生命周期汇总 + 智能检索。旨在帮助销售团队快速发现高价值项目机会。

---

## 🌟 核心亮点 (2026-04 更新)

### 1. 项目生命周期全追踪 (Project Aggregation)
不再被零散的公告困扰！系统自动识别并聚合同一项目的**招标公告、中标公告、更正公告、终止公告**。
- **状态感知**：实时显示项目处于“进行中”还是“已中标”。
- **时间轴展示**：在搜索结果中以时间轴形式展现项目从发布到结束的全过程。
- **信息补全**：自动从多份公告中提取预算金额、中标金额、中标单位及联系方式。

### 2. 双路混合检索架构 (Hybrid Search)
结合了最先进的检索技术，确保“搜得准”且“搜得全”：
- **向量检索 (FAISS)**：基于语义理解，即使关键词不完全匹配也能找到相关项目（如搜索“交换机”能匹配到“网络设备采购”）。
- **关键词检索 (BM25)**：基于精确匹配，确保项目编号、特定品牌名等硬性指标不被遗漏。
- **RRF 融合算法**：智能合并两路搜索结果，提供最科学的相关性评分。

### 3. 企业级可视化看板
基于 FastAPI + Tailwind CSS 打造的现代化 UI：
- **项目卡片**：直观展示项目背景、技术摘要、应用场景。
- **智能评分**：LLM 自动为项目打分（Opportunity Score），并给出推荐理由。
- **快捷操作**：一键过滤已中标项目，支持按时间或相关性排序。
- **多端访问**：支持局域网访问，方便团队共享。

---

## 🚀 快速开始

### 1. 环境准备

建议使用 Python 3.10+ 环境。

```bash
# 克隆仓库并进入目录
cd sales_agent/get_data

# 安装依赖
pip install -r requirements.txt
```

### 2. 数据采集与处理流水线

按照以下顺序执行脚本，即可构建完整的本地标讯库：

| 步骤 | 命令 | 说明 | 耗时 |
|:---|:---|:---|:---|
| **1. 初始化** | `python src/utils/reset_db.py` | 清空并重置本地 SQLite 数据库 | < 1min |
| **2. 采集数据** | `python src/crawler/ccgp_crawler.py`<br>`python src/crawler/crawl_detail.py` | 爬取列表页及详情页内容，绕过反爬机制 | 10-20min |
| **3. AI 结构化** | `python src/etl/core/extract_structured.py --all` | 调用 DeepSeek 提取预算、关键词、联系人等 | 视数据量 |
| **4. 项目聚合** | `python src/etl/aggregate_projects.py` | 将散乱公告聚合为完整项目卡片 | < 2min |
| **5. 构建索引** | `python src/vectorization/vectorize_data.py`<br>`python src/vectorization/build_index.py` | 生成向量嵌入并构建 FAISS/BM25 索引 | 5-10min |

### 3. 启动搜索服务

```bash
# 启动后端 API 服务
python webapp/server_fastapi.py
```
启动后，控制台会打印出访问地址：
- **本地访问**：`http://127.0.0.1:8103/static/demo.html`
- **局域网访问**：`http://[你的IP]:8103/static/demo.html`

---

## 📂 项目结构

```text
D:\sales_agent\get_data\
├── src/
│   ├── crawler/            # 爬虫：支持列表、详情、附件采集
│   ├── etl/                # 数据处理：LLM 抽取、项目聚合、附件解析
│   ├── retrieval/          # 检索：混合检索器、RRF 融合算法
│   ├── vectorization/      # 向量化：文本转向量、索引构建
│   ├── analysis/           # 分析：AI 销售建议、客户画像生成
│   ├── storage/            # 存储：数据库操作、JSONL 读写
│   ├── utils/              # 工具：通用辅助函数
│   └── config.py           # 全局配置：API Key、关键词、数据库路径
├── webapp/                 # Web 服务：FastAPI 接口与前端静态页面
│   ├── server_fastapi.py   # 后端主服务
│   └── static/             # 前端：demo.html (Tailwind CSS 驱动)
├── data/                   # 数据存储：SQLite 数据库、向量索引、JSON 输出
├── docs/                   # 项目文档
└── requirements.txt        # 依赖清单
```

---

## 📖 模块文档

| 模块 | 文档 | 说明 |
|------|------|------|
| 爬虫 | [src/crawler/README.md](src/crawler/README.md) | 政府采购网数据采集 |
| ETL | [src/etl/README.md](src/etl/README.md) | LLM 结构化抽取与数据清洗 |
| 向量化 | [src/vectorization/README.md](src/vectorization/README.md) | 文本 Embedding 与索引构建 |
| 检索 | [src/retrieval/README.md](src/retrieval/README.md) | 双路混合检索 (FAISS + BM25) |
| 分析 | [src/analysis/README.md](src/analysis/README.md) | AI 销售建议与客户画像 |
| Web 服务 | [webapp/README.md](webapp/README.md) | FastAPI 后端与前端页面 |

---

## 🔗 相关文档

- [完整使用指南 (详细版)](docs/README.md)
- [MVP RAG 实施方案](docs/MVP_RAG_实施方案.md)
- [DeepSeek 结构化抽取报告](docs/02_RAG 方案/DeepSeek 结构化抽取报告.md)

---
*Last Updated: 2026-04-16*
