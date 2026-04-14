# 政府采购招投标数据系统 - 文档索引

## 新手入门

| 文档 | 说明 | 适合人群 |
|------|------|----------|
| [README.md](../README.md) | 项目首页，快速了解功能 | 所有人 |
| [docs/README.md](README.md) | **完整使用指南** | 新用户必读 |
| [LLM 抽取新手指南.md](LLM 抽取新手指南.md) | LLM 结构化抽取详细教程 | 需要使用 LLM 功能 |
| [Web 前端使用指南.md](Web 前端使用指南.md) | Web 界面使用教程 | 使用 Web 界面 |
| [日志系统说明.md](../03_工具使用/日志系统说明.md) | 日志管理和查看 | 需要查看日志 |

## 快速操作

### 一键开始（推荐）

Windows 用户直接运行：

```bash
# 全自动流程（约 15 分钟）
quick_start.bat

# 测试不同 LLM 模型效果
test_models.bat
```

### 手动执行

```bash
# 1. 重置数据库
python src/utils/reset_db.py

# 2. 爬取列表
python src/crawler/ccgp_crawler.py

# 3. 爬取详情
python src/crawler/crawl_detail.py

# 4. LLM 抽取
python src/etl/extract_structured.py --limit 50
```

## 文档列表

### 基础文档

| 文档 | 说明 |
|------|------|
| [README.md](README.md) | 完整使用指南（新用户必读） |
| [LLM 抽取新手指南.md](LLM 抽取新手指南.md) | LLM 结构化抽取详细教程 |

### 高级文档

| 文档 | 说明 |
|------|------|
| [ALIYUN_LLM_SETUP.md](ALIYUN_LLM_SETUP.md) | 阿里云 LLM 配置说明 |
| [MVP_RAG_实施方案.md](MVP_RAG_实施方案.md) | MVP 实施方案详细设计 |
| [项目架构说明.md](项目架构说明.md) | 系统架构设计文档 |
| [项目详细流程.md](项目详细流程.md) | 项目开发流程记录 |

## 常用命令速查

### 数据爬取

```bash
# 爬取列表页
python src/crawler/ccgp_crawler.py

# 爬取详情页
python src/crawler/crawl_detail.py

# 修复附件链接
python src/crawler/crawl_detail.py repair-att-url

# 导出异常 HTML
python src/crawler/crawl_detail.py export-bad-html

# 修复内容
python src/crawler/crawl_detail.py repair-content
```

### LLM 抽取

```bash
# 测试第一条
python src/etl/core/extract_structured.py --test-first

# 抽取前 50 条
python src/etl/core/extract_structured.py --limit 50

# 抽取所有
python src/etl/core/extract_structured.py --all

# 使用不同模型
python src/etl/core/extract_structured.py --model deepseek-chat --limit 10
python src/etl/core/extract_structured.py --model qwen-max --limit 10

# 导入数据库
python src/etl/core/import_structured_db.py --file output/tenders_structured.json

# 批量测试所有模型
test_models.bat
```

### RAG 分块

```bash
# 生成 chunks
python src/etl/chunks/generate_chunks.py --all --replace

# 导入附件 chunks
python src/etl/chunks/import_attachment_chunks.py --import
```

### 附件处理

```bash
# 一键执行
python src/etl/attachments/run_attachment_pipeline.py --verify

# 解析附件
python src/etl/attachments/parse_attachments.py
```

### 工具命令

```bash
# 重置数据库
python src/utils/reset_db.py

# 查询数据
python src/etl/query_tenders.py

# 批量保存 HTML
python src/utils/save_all_html.py
```

## 配置说明

编辑 `src/config.py` 修改配置：

```python
# 搜索关键词
CRAWLER_CONFIG = {
    "keyword": "通信",      # 修改关键词
    "max_pages": 3,        # 爬取页数
}

# DeepSeek API 配置
DEEPSEEK_CONFIG = {
    "api_key": "sk-xxx",   # 填入你的 API Key
}
```

## 数据说明

### 数据库表结构

**tenders 表**（招标项目）:

| 字段 | 说明 |
|------|------|
| id | 主键 |
| project_name | 项目名称 |
| publish_date | 发布日期 |
| detail_url | 详情链接 |
| content | 公告内容 |
| attachment_urls | 附件链接（JSON 数组） |
| status | 状态 |
| created_at | 创建时间 |

### 输出文件

| 文件 | 说明 | 位置 |
|------|------|------|
| `ccgp_data.db` | SQLite 数据库 | `data/` |
| `tenders_structured.json` | LLM 抽取结果 | `output/` |
| `extract_*.log` | 抽取日志 | `logs/` |

## 依赖安装

```bash
pip install curl_cffi tqdm openai
```

## 技术栈

- **爬虫**: curl_cffi（绕过反爬）
- **数据库**: SQLite
- **结构化抽取**: DeepSeek / 通义千问
- **语言**: Python 3

## 相关链接

- 中国政府采购网：https://www.ccgp.gov.cn/
- DeepSeek 平台：https://platform.deepseek.com/
- 阿里云 DashScope: https://dashscope.console.aliyun.com/
