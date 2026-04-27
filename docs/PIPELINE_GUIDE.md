# 数据处理流水线指南

## 完整工作流程

```
招标网列表页 → 详情页爬取 → 结构化抽取 → 项目聚合 → 向量化建索引 → 智能检索
```

---

## 一、数据采集（爬虫）

### 1.1 采集招标公告列表

```bash
cd D:\sales_agent\get_data

python -m src.crawler.ccgp_crawler
```

**输出：** `data/output/crawler/` 目录下的 JSON 文件

### 1.2 爬取详情页内容

```bash
python -m src.crawler.crawl_detail
```

**输出：** 详情页 HTML 内容和附件链接

### 1.3 下载附件

```bash
# 单条附件下载
python -m src.crawler.download_attachments

# 批量下载
python -m src.crawler.batch_crawl_attachments
```

**输出：** `data/attachment/` 目录

---

## 二、数据处理（ETL）

### 2.1 LLM 结构化抽取

```bash
# 抽取所有数据
python -m src.etl.core.extract_structured --all

# 抽取单条
python -m src.etl.core.extract_structured --id <tender_id>

# 指定模型
python -m src.etl.core.extract_structured --all --model deepseek
```

**输出：** `data/output/etl/tenders_structured*.json`

### 2.2 导入结构化数据到数据库

```bash
python -m src.etl.core.import_structured_db
```

### 2.3 项目聚合

将同一项目的多条招标/中标公告汇总：

```bash
python -m src.etl.core.aggregate_projects
```

**输出：** `data/output/etl/projects_aggregated.jsonl`

---

## 三、向量化与索引

### 3.1 向量化文本数据

```bash
# 向量化招标数据
python -m src.vectorization.vectorize_data --type tender

# 向量化产品数据
python -m src.vectorization.vectorize_data --type product
```

**输出：** `data/embedding/tenders_embedded.jsonl` 或 `product_embedded.jsonl`

### 3.2 构建检索索引

```bash
# 构建招标索引
python -m src.vectorization.build_index --type tender

# 构建产品索引
python -m src.vectorization.build_index --type product
```

**输出：**
- `data/index_tenders/tenders.index` (FAISS 索引)
- `data/index_tenders/tenders_ids.json` (ID 映射)
- `data/index/product.index` (产品 FAISS 索引)
- `data/index/product_ids.json` (产品 ID 映射)

---

## 四、智能分析

### 4.1 生成客户画像

```bash
python -m src.analysis.generate_customer_profiles
```

**输出：** `data/output/customer/customer_profiles.jsonl`

### 4.2 销售建议分析

```bash
python -m src.analysis.sales_advisor --tender-id <id>
```

---

## 五、Web 服务

### 5.1 启动 API 服务

```bash
cd D:\sales_agent\get_data
python webapp/server_fastapi.py
```

服务地址：`http://127.0.0.1:8103`

### 5.2 访问前端

```
http://127.0.0.1:8103/static/demo.html  # 轻量演示版
http://127.0.0.1:8103/static/index.html # 完整功能版
```

---

## 六、检索接口调用

### 6.1 Python 调用示例

```python
from src.retrieval.retriever import DualRetriever

# 初始化检索器
retriever = DualRetriever(data_type="tender")

# 执行混合检索
results = retriever.hybrid_search(
    query="交换机 采购 北京",
    top_k=10,
    province="北京",
    aggregate_by_project=True
)

for r in results:
    print(f"{r['score']:.2f} - {r['data'].get('project_name_std')}")
```

### 6.2 API 调用示例

```bash
curl -X POST "http://127.0.0.1:8103/api/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "交换机", "top_k": 10, "province": "北京"}'
```

---

## 七、配置说明

关键配置位于 `src/config.py`：

| 配置项 | 说明 |
|--------|------|
| `DB_PATH` | SQLite 数据库路径 |
| `CRAWLER_CONFIG` | 爬虫关键词、代理、页数 |
| `EMBEDDING_CONFIG` | 向量化 API 地址 |
| `DEEPSEEK_CONFIG` | DeepSeek API 配置 |
| `LOCAL_LLM_CONFIG` | 本地 LLM 配置 |

---

## 八、故障排除

### 8.1 爬取被拦截

- 增加 `CRAWLER_CONFIG` 中的 `delay_min` / `delay_max`
- 检查代理是否有效
- 确认 `base_url` 是否可访问

### 8.2 LLM 抽取失败

- 检查 API Key 配置
- 确认网络代理设置
- 查看 `logs/` 目录下的错误日志

### 8.3 索引加载失败

- 确认 `data/embedding/` 目录下是否有 `.jsonl` 文件
- 确认 `data/index_tenders/` 和 `data/index/` 目录下是否有索引文件

---

## 九、输出目录结构

```
data/
├── ccgp_data.db              # SQLite 数据库
├── attachment/                # 下载的附件
├── html/                      # 爬取的 HTML
├── embedding/                 # 向量化数据
│   ├── tenders_embedded.jsonl
│   └── product_embedded.jsonl
├── index/                     # 产品检索索引
├── index_tenders/             # 招标检索索引
└── output/
            ├── crawler/        # 爬虫输出
            ├── etl/           # ETL 输出
            │   └── projects_aggregated.jsonl  # 聚合后的项目
            └── customer/      # 客户画像
```

---

*文档更新时间：2026-04-27*
