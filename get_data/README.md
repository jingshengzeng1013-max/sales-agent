# 政府采购招投标数据系统

> 一键爬取中国政府采购网招标公告，自动提取结构化数据 + 附件解析

## 快速开始

### 5 分钟上手

```bash
# 1. 重置数据库
python src/utils/reset_db.py

# 2. 爬取列表（1-3 分钟）
python src/crawler/ccgp_crawler.py

# 3. 爬取详情（5-10 分钟）
python src/crawler/crawl_detail.py

# 4. LLM 结构化抽取（可选）
python src/etl/core/extract_structured.py --limit 50
```

### 附件下载与解析（新增）

```bash
# 一键执行：爬取链接 → 下载 → 解析 → 导入
python src/etl/attachments/run_attachment_pipeline.py --verify

# 或分步执行
# 1. 爬取附件链接
python -m src.crawler.batch_crawl_attachments
python -m src.crawler.batch_crawl_attachments --import

# 2. 下载附件
python -m src.crawler.download_attachments --db

# 3. 解析附件文本
python -m src.etl.attachments.parse_attachments

# 4. 导入数据库
python -m src.etl.chunks.import_attachment_chunks --import
```

### 结构化数据导入（新增）

```bash
# 使用 DeepSeek 抽取所有数据（约 30 分钟）
python src/etl/core/extract_structured.py --all --model deepseek-chat

# 导入到数据库
python src/etl/core/import_structured_db.py

# 生成 RAG 分块
python src/etl/chunks/generate_chunks.py --all --replace
```

### 完整文档

详细使用指南请参阅：**[docs/README.md](docs/README.md)**

---

## 项目结构

```
D:\get_data\
├── docs/                  # 文档目录
│   ├── README.md          # 完整使用指南
│   ├── ALIYUN_LLM_SETUP.md  # 阿里云 LLM 配置
│   └── MVP_RAG_实施方案.md  # MVP 实施方案
│
├── src/                   # 源代码
│   ├── config.py          # 配置文件
│   ├── crawler/           # 爬虫模块
│   │   ├── ccgp_crawler.py    # 列表页爬虫
│   │   └── crawl_detail.py    # 详情页爬虫
│   ├── etl/               # 数据抽取模块（新增子目录）
│   │   ├── README.md          # ETL 模块说明
│   │   ├── core/              # 核心抽取
│   │   │   ├── extract_structured.py
│   │   │   ├── import_structured_db.py
│   │   │   └── prompt_extract.md
│   │   ├── chunks/            # RAG 分块
│   │   │   ├── generate_chunks.py
│   │   │   └── import_attachment_chunks.py
│   │   ├── attachments/       # 附件处理
│   │   │   ├── run_attachment_pipeline.py
│   │   │   ├── parse_attachments.py
│   │   │   └── parse_pages_with_llm.py
│   │   └── utils/             # 工具
│   │       └── llm_client.py
│   └── utils/             # 工具模块
│       └── reset_db.py          # 数据库重置
│
├── data/                  # 数据目录
│   └── ccgp_data.db       # SQLite 数据库
│
├── output/                # 输出目录
│   └── tenders_structured.json  # 结构化数据
│
└── logs/                  # 日志目录
    └── extract_*.log      # 抽取日志
```

---

## 核心功能

| 功能 | 命令 | 说明 |
|------|------|------|
| 重置数据库 | `python src/utils/reset_db.py` | 清空旧数据 |
| 爬取列表 | `python src/crawler/ccgp_crawler.py` | 爬取招标公告列表 |
| 爬取详情 | `python src/crawler/crawl_detail.py` | 爬取详情、提取附件 |
| 结构化抽取 | `python src/etl/core/extract_structured.py --all` | LLM 抽取关键字段 |
| 导入数据库 | `python src/etl/core/import_structured_db.py` | 将 JSON 导入 SQLite |
| 生成 RAG 分块 | `python src/etl/chunks/generate_chunks.py --all` | 生成检索分块 |
| 多模型测试 | `test_models.bat` | 批量测试不同 LLM 效果 |

---

## 依赖安装

```bash
pip install curl_cffi tqdm openai
```

---

## 配置说明

编辑 `src/config.py` 修改以下配置：

```python
# 搜索关键词
CRAWLER_CONFIG = {
    "keyword": "通信",    # 改成你想搜索的关键词
    "max_pages": 3,      # 爬取页数
}

# DeepSeek API（结构化抽取）
DEEPSEEK_CONFIG = {
    "api_key": "sk-xxx",  # 替换为你的 API Key
}
```

---

## LLM 多模型支持

系统支持多种 LLM 模型进行结构化数据抽取：

| 模型 | 命令参数 | 说明 | 价格 |
|------|----------|------|------|
| DeepSeek V3 | `--model deepseek-chat` | 推荐，性价比高 | ¥0.2-2/1M tokens |
| DeepSeek R1 | `--model deepseek-reasoner` | 推理能力强 | ¥4-8/1M tokens |
| 豆包 Seed 2.0 Lite | `--model doubao` | 免费额度，测试首选 | 免费 |
| 通义千问 Max | `--model qwen-max` | 最强中文模型 | ¥20-60/1M tokens |
| 通义千问 Plus | `--model qwen-plus` | 性价比高 | ¥4-12/1M tokens |

**测试不同模型效果：**

```bash
# 单模型测试
python src/etl/core/extract_structured.py --model deepseek-chat --limit 10

# 测试豆包（免费）
python src/etl/core/extract_structured.py --model doubao --limit 10

# 批量测试所有模型
test_models.bat
```

**实际执行案例（2026-04-01）：**

```bash
# 抽取 85 条数据，使用 DeepSeek-V3 模型
python src/etl/core/extract_structured.py --all --model deepseek-chat

# 执行结果
- 处理数量：85/85 (100%)
- 总 Token：353,663 (输入 295,962 + 输出 57,701)
- 估算成本：约 0.50 元
- 执行时间：约 34 分钟
```

---

## 数据示例

### 原始数据（tenders 表）

```json
{
  "id": 1,
  "project_name": "某某通信设备采购项目",
  "publish_date": "2026-03-24",
  "detail_url": "http://www.ccgp.gov.cn/xxx",
  "content": "...",
  "attachment_urls": ["http://download.ccgp.gov.cn/xxx.pdf"]
}
```

### 结构化数据（抽取后）

```json
{
  "tender_id": 1,
  "project_name": "某某通信设备采购项目",
  "announce_type": "招标公告",
  "buyer_name_std": "中国移动通信集团",
  "province": "广东省",
  "city": "深圳市",
  "budget_amount": 5000000,
  "product_keywords": ["通信设备", "路由器", "交换机"],
  "opportunity_score": 85
}
```

---

## 技术栈

- **爬虫**: curl_cffi（绕过反爬）
- **数据库**: SQLite
- **结构化抽取**: DeepSeek / 通义千问
- **语言**: Python 3

---

## 相关链接

- [完整使用文档](docs/README.md)
- [阿里云 LLM 配置](docs/ALIYUN_LLM_SETUP.md)
- [MVP 实施方案](docs/MVP_RAG_实施方案.md)
- [ETL 模块说明](src/etl/README.md)
- [DeepSeek 抽取报告](docs/02_RAG 方案/DeepSeek 结构化抽取报告.md)
