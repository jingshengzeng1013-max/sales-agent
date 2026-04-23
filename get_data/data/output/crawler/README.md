# 爬虫架构说明

## 目录结构

```
get_data/
├── data/
│   ├── output/
│   │   └── crawler/         # 爬虫输出目录（JSON 文件）
│   │       ├── tenders_list.json    # 招标列表数据
│   │       ├── tenders_detail.json  # 招标详情数据
│   │       └── tenders_attachments.json  # 附件下载链接数据
│   ├── attachment/          # 附件文件存储目录
│   │   ├── 1/               # 按 tender_id 分目录
│   │   │   ├── 文件 1.pdf
│   │   │   └── 文件 2.docx
│   │   └── 2/
│   └── ccgp_data.db         # SQLite 数据库
├── src/
│   ├── crawler/             # 爬虫模块（只负责爬取和保存 JSON）
│   │   ├── ccgp_crawler.py      # 列表页爬取
│   │   ├── crawl_detail.py      # 详情页爬取
│   │   ├── batch_crawl_attachments.py  # 附件链接爬取
│   │   └── download_attachments.py   # 附件文件下载
│   ├── storage/             # 入库模块（只负责从 JSON 导入数据库）
│   │   ├── import_tenders.py    # 入库逻辑
│   │   └── cli.py               # 命令行工具
│   └── crawler_graph.py     # 工作流编排
```

## 设计原则

1. **爬取与入库分离** - `crawler/` 只负责爬取数据并保存为 JSON，不涉及数据库操作
2. **JSON 作为中间格式** - 所有爬取结果先保存为 JSON 文件，便于检查和调试
3. **独立入库模块** - `storage/` 专门负责将 JSON 数据导入数据库

## 使用方法

### 1. 爬取数据（不入库）

```bash
# 爬取列表页（默认 3 页）
python -m src.crawler.ccgp_crawler --pages 5

# 爬取详情页（最多处理 10 条）
python -m src.crawler.crawl_detail

# 爬取附件链接
python -m src.crawler.batch_crawl_attachments
```

### 2. 导入数据库

```bash
# 初始化数据库表
python -m src.storage.cli init

# 导入招标列表
python -m src.storage.cli list

# 更新招标详情
python -m src.storage.cli detail

# 导入附件
python -m src.storage.cli attachment

# 一次性导入所有数据
python -m src.storage.cli all
```

### 3. 下载附件文件

```bash
# 从 JSON 文件下载附件
python -m src.crawler.download_attachments --json data/output/crawler/tenders_attachments.json
```

### 4. 通过 API 调用工作流

```bash
# 启动 Web 服务后，调用 API
curl -X POST http://localhost:8000/api/crawl/workflow/stream \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "通信",
    "max_pages": 3,
    "run_list": true,
    "run_detail": true,
    "run_attachment": false,
    "detail_limit": 10
  }'
```

## 输出文件说明

### tenders_list.json
```json
[
  {
    "project_name": "项目名称",
    "detail_url": "https://...",
    "content": ""
  }
]
```

### tenders_detail.json
```json
[
  {
    "url": "https://...",
    "title": "标题",
    "publish_date": "2024-01-01",
    "buyer": "采购人",
    "agency": "代理机构",
    "budget": "预算金额",
    "content": "正文内容",
    "crawl_time": "2024-01-01T12:00:00"
  }
]
```

### tenders_attachments.json
```json
[
  {
    "tender_id": 1,
    "tender_name": "项目名称",
    "file_name": "文件名称.pdf",
    "download_url": "https://...",
    "uuid": "xxx",
    "source_html_file": "https://..."
  }
]
```
