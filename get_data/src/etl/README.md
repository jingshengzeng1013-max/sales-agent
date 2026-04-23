# ETL 模块说明

## 目录结构

```
src/etl/
├── 核心抽取/
│   ├── extract_structured.py    # LLM 结构化字段抽取（主流程）
│   ├── import_structured_db.py  # 导入结构化数据到数据库
│   └── prompt_extract.md        # LLM 抽取 Prompt 模板
│
├── RAG 分块/
│   ├── generate_chunks.py       # 生成 tender_chunks 分块数据
│   └── import_attachment_chunks.py  # 导入附件解析结果到 chunks
│
├── 附件处理/
│   ├── run_attachment_pipeline.py  # 附件处理完整流程（一键执行）
│   ├── parse_attachments.py     # 解析附件文件（PDF/DOC 等）
│   └── parse_pages_with_llm.py  # 使用 LLM 解析详情页 HTML
│
└── 工具/
    └── llm_client.py            # LLM 客户端封装（阿里云/DeepSeek）
```

---

## 模块分类

### 1. 核心抽取模块

| 文件 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `extract_structured.py` | LLM 结构化字段抽取 | tenders 表 | `tenders_structured.json` |
| `import_structured_db.py` | 导入结构化数据 | JSON 文件 | `tender_structured` 表 |

**典型用法**：
```bash
# 抽取所有数据
python src/etl/extract_structured.py --all --model deepseek-chat

# 导入数据库
python src/etl/import_structured_db.py --file output/tenders_structured.json
```

**抽取字段**：
- 基础信息：公告类型、采购单位、地区
- 预算信息：预算金额、单位
- 技术信息：产品关键词、技术要求
- 联系信息：三方联系人
- RAG 分块：contact_chunk, requirement_chunks
- 机会评估：opportunity_score, next_action

---

### 2. RAG 分块模块

| 文件 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `generate_chunks.py` | 生成检索分块 | tender_structured 表 | `tender_chunks` 表 |
| `import_attachment_chunks.py` | 导入附件解析结果 | parsed_attachments | `tender_chunks` 表 |

**Chunk 类型**：
- `title` - 项目标题
- `content_summary` - 公告摘要
- `contact_chunk` - 联系人信息整合
- `requirement_chunk` - 技术要求分块
- `attachment_summary` - 附件摘要

**典型用法**：
```bash
# 生成所有 chunks
python src/etl/generate_chunks.py --all --replace

# 导入附件 chunks
python src/etl/import_attachment_chunks.py --import
```

---

### 3. 附件处理模块

| 文件 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `run_attachment_pipeline.py` | 一键执行完整流程 | - | 数据库 |
| `parse_attachments.py` | 解析附件文件 | attachments/ | parsed_attachments/ |
| `parse_pages_with_llm.py` | LLM 解析详情页 | tenders 表 | tenders 表 |

**完整流程**：
```bash
# 一键执行（推荐）
python src/etl/run_attachment_pipeline.py --verify

# 分步执行
# 1. 爬取链接（crawler 模块）
# 2. 下载附件（crawler 模块）
# 3. 解析附件
python src/etl/parse_attachments.py
# 4. 导入 chunks
python src/etl/import_attachment_chunks.py --import
```

**支持格式**：PDF, DOC, DOCX, TXT, CSV, XLS, XLSX, ZIP 等

---

### 4. 工具模块

| 文件 | 功能 |
|------|------|
| `llm_client.py` | LLM 客户端封装，支持阿里云 DashScope、DeepSeek |

**功能**：
- 统一的 chat_completion 接口
- JSON 抽取辅助函数
- 预定义 Prompt 模板

---

## 数据流程图

```
tenders 表
    │
    ├──→ [extract_structured.py] → tenders_structured.json → [import_structured_db.py] → tender_structured 表
    │                                                                 ↓
    │                                                                 [generate_chunks.py] → tender_chunks 表
    │
    └──→ [parse_pages_with_llm.py] → tenders 表 (content 字段增强)

attachments/
    │
    └──→ [parse_attachments.py] → parsed_attachments/ → [import_attachment_chunks.py] → tender_chunks 表
```

---

## 数据库表关系

```
tenders 表
    │
    ├── 1:1 → tender_structured 表 (tender_id FK)
    │
    └── 1:N → tender_chunks 表 (tender_id FK)
             ↑
             └── 附件解析结果也汇入此表
```

---

## 快速参考

### 新手上路（标准流程）

```bash
# 1. 爬取数据
python src/crawler/ccgp_crawler.py
python src/crawler/crawl_detail.py

# 2. LLM 结构化抽取
python src/etl/extract_structured.py --all --model deepseek-chat

# 3. 导入数据库
python src/etl/import_structured_db.py --file output/tenders_structured.json

# 4. 生成 RAG 分块
python src/etl/generate_chunks.py --all --replace
```

### 附件处理

```bash
# 一键执行
python src/etl/run_attachment_pipeline.py --verify
```

### 常用参数

| 参数 | 说明 |
|------|------|
| `--all` | 处理所有记录 |
| `--limit N` | 处理前 N 条记录 |
| `--test-first` | 仅测试第一条 |
| `--replace` | 替换已存在数据 |
| `--model` | 指定 LLM 模型 |
| `--import-only` | 仅导入模式 |
