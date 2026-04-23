# 政府采购招投标数据系统 - 完整使用指南

## 目录

- [一、快速开始（5 分钟上手）](#一快速开始 5 分钟上手)
- [二、环境准备](#二环境准备)
- [三、配置说明](#三配置说明)
- [四、核心功能使用](#四核心功能使用)
- [五、LLM 多模型测试](#五 llm 多模型测试)
- [六、常见问题](#六常见问题)

---

## 一、快速开始（5 分钟上手）

### 1.1 完整流程（一条命令搞定）

```bash
# 步骤 1: 重置数据库（清空旧数据）
python src/utils/reset_db.py

# 步骤 2: 爬取招标公告列表（约 1-3 分钟）
python src/crawler/ccgp_crawler.py

# 步骤 3: 爬取详情页面并提取附件链接（约 5-10 分钟）
python src/crawler/crawl_detail.py

# 步骤 4: 使用 LLM 抽取结构化字段（可选，约 2-5 分钟）
python src/etl/extract_structured.py --limit 50
```

### 1.2 各步骤说明

| 步骤 | 命令 | 作用 | 耗时 |
|------|------|------|------|
| 重置数据库 | `python src/utils/reset_db.py` | 清空旧数据，创建新表 | 1 秒 |
| 爬取列表 | `python src/crawler/ccgp_crawler.py` | 爬取招标公告列表 | 1-3 分钟 |
| 爬取详情 | `python src/crawler/crawl_detail.py` | 爬取详情、提取附件 | 5-10 分钟 |
| 结构化抽取 | `python src/etl/extract_structured.py --all` | LLM 抽取关键字段 | 视数据量 |
| 项目聚合 | `python src/etl/aggregate_projects.py` | 聚合项目生命周期 | < 2 分钟 |
| 客户画像 | `python src/analysis/generate_customer_profiles.py` | 生成客户画像 | < 1 分钟 |
| 向量化 | `python src/vectorization/vectorize_data.py --type tender` | 生成向量嵌入 | 5-10 分钟 |
| 构建索引 | `python src/vectorization/build_index.py --type tender` | 构建 FAISS+BM25 索引 | 2-5 分钟 |

### 1.3 数据流向

```
中国政府采购网 → 爬虫 → SQLite 数据库 → LLM 抽取 → 结构化 JSON
```

---

## 二、环境准备

### 2.1 系统要求

- **操作系统**: Windows 10/11, macOS, Linux
- **Python 版本**: Python 3.8 或更高
- **网络**: 需要能访问中国政府采购网 (www.ccgp.gov.cn)

### 2.2 安装依赖

```bash
# 进入项目目录
cd D:\sales_agent\get_data

# 安装所有依赖
pip install curl_cffi tqdm openai
```

### 2.3 验证安装

```bash
# 检查 Python 版本
python --version

# 检查依赖是否安装成功
python -c "import curl_cffi; import tqdm; import openai; print('OK')"
```

如果输出 `OK`，说明环境准备完成。

---

## 三、配置说明

### 3.1 配置文件位置

所有配置在 `src/config.py` 文件中。

### 3.2 爬虫配置

```python
CRAWLER_CONFIG = {
    "base_url": "https://search.ccgp.gov.cn/bxsearch",
    "keyword": "通信",           # 搜索关键词
    "delay_min": 2,              # 请求间隔最小值（秒）
    "delay_max": 5,              # 请求间隔最大值（秒）
    "max_pages": 3,              # 爬取页数（每页约 30 条）
    "timeout": 30,               # 请求超时时间（秒）
    "searchtype": "1",           # 搜索类型：1=公告，2=采购，3=结果
    "bidSort": "0",              # 排序方式：0=时间，1=相关性
    "time_type": "2",            # 时间范围：0=今日，1=近三日，2=近一周，3=近一月，4=近三月
    "start_time": "2026:02:24",  # 起始日期（格式：YYYY:MM:DD）
    "end_time": None,            # 结束日期（None 表示当天）
}
```

### 3.3 修改关键词

编辑 `src/config.py`，修改 `keyword` 参数：

```python
CRAWLER_CONFIG = {
    "keyword": "芯片",    # 改成你想搜索的关键词
}
```

### 3.4 LLM API 配置

#### DeepSeek 配置（推荐）

```python
DEEPSEEK_CONFIG = {
    "api_key": "sk-xxx",  # 替换为你的 DeepSeek API Key
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "timeout": 120,
}
```

**获取 DeepSeek API Key:**
1. 访问 https://platform.deepseek.com/
2. 注册账号并充值
3. 创建 API Key
4. 复制到 config.py 中

**价格参考**（2026 年 3 月）:
- 输入（缓存命中）: ¥0.2/1M tokens
- 输入（缓存未命中）: ¥2.0/1M tokens
- 输出：¥3.0/1M tokens
- 单条记录花费：约 ¥0.002-0.005 元

#### 阿里云通义千问配置

```python
DASHSCOPE_CONFIG = {
    "api_key": "sk-xxx",  # 替换为你的阿里云 API Key
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen-plus",
    "timeout": 60,
}
```

**获取阿里云 API Key:**
1. 访问 https://dashscope.console.aliyun.com/
2. 开通服务并创建 API Key
3. 复制到 config.py 中

**价格参考**（2026 年 3 月）:
- qwen-plus: 输入 ¥4.0/1M tokens, 输出 ¥12.0/1M tokens
- qwen-max: 输入 ¥20.0/1M tokens, 输出 ¥60.0/1M tokens

---

## 四、核心功能使用

### 4.1 重置数据库

**作用**: 清空所有旧数据，重新开始爬取。

```bash
python src/utils/reset_db.py
```

**输出示例**:
```
[DELETE] Removed old database: D:/get_data/data/ccgp_data.db
[CREATE] New database created: D:/get_data/data/ccgp_data.db
```

### 4.2 爬取招标公告列表

**作用**: 爬取中国政府采购网的招标公告列表，保存基本信息到数据库。

```bash
python src/crawler/ccgp_crawler.py
```

**参数说明**:
- 默认爬取 `max_pages` 页（在 config.py 中配置）
- 每页约 30 条公告

**输出示例**:
```
============================================================
CCGP Crawler - Full Version
============================================================
[DB] Initialized: D:/get_data/data/ccgp_data.db

============================================================
[PAGE 1]
============================================================
[FETCH] https://search.ccgp.gov.cn/bxsearch?...
  [OK] Status: 200, Length: 12345
  [INFO] Found 30 list items
  [FOUND] 30 tenders
    1. 某某通信设备采购项目...
    2. 某某系统建设项目...
  [SAVED] 25 items, [SKIPPED] 5 duplicates

============================================================
Done!
New: 25 items
Total: 25 items
============================================================
```

### 4.3 爬取详情页面

**作用**: 根据列表中的详情链接，爬取完整公告内容，提取附件下载链接。

```bash
python src/crawler/crawl_detail.py
```

**输出示例**:
```
============================================================
Crawl Detail - Full Version
============================================================
[INFO] Found 25 tenders with detail_url

[FETCH] http://www.ccgp.gov.cn/xxx...
  [OK] Status: 200, Length: 15678
  [INFO] No attachments found
  [WAIT] 3.2s...

[FETCH] http://www.ccgp.gov.cn/yyy...
  [OK] Status: 200, Length: 23456
  [FOUND] 2 attachment(s)
  [SAVE] Updated attachment_urls
  [WAIT] 2.8s...

============================================================
Done! Repaired 25/25 tenders
============================================================
```

#### 4.3.1 修复附件链接

如果之前爬取失败，可以单独修复附件链接：

```bash
python src/crawler/crawl_detail.py repair-att-url
```

#### 4.3.2 导出异常 HTML

如果详情内容爬取失败，可以导出异常 HTML 进行检查：

```bash
python src/crawler/crawl_detail.py export-bad-html
```

#### 4.3.3 修复内容

重新爬取内容为空或非中文的记录：

```bash
python src/crawler/crawl_detail.py repair-content
```

### 4.4 结构化字段抽取

**作用**: 使用 LLM 从公告内容中抽取结构化字段，如采购人、预算金额、省份等。

#### 基础用法

```bash
# 抽取前 50 条记录
python src/etl/extract_structured.py --limit 50

# 抽取所有记录
python src/etl/extract_structured.py --all

# 仅测试第一条
python src/etl/extract_structured.py --test-first
```

#### 高级用法

```bash
# 不使用 LLM（仅保存原始数据）
python src/etl/extract_structured.py --limit 50 --no-llm

# 指定输出文件后缀（用于区分不同模型结果）
python src/etl/extract_structured.py --limit 50 --output-suffix test1
```

#### 输出文件

- **结构化数据**: `output/tenders_structured.json`
- **日志文件**: `logs/extract_YYYYMMDD_HHMMSS.log`

#### 抽取结果示例

```json
[
  {
    "tender_id": 1,
    "project_name": "某某通信设备采购项目",
    "announce_type": "招标公告",
    "buyer_name_std": "中国移动通信集团",
    "province": "广东省",
    "city": "深圳市",
    "budget_amount": 5000000,
    "product_keywords": ["通信设备", "路由器", "交换机"],
    "opportunity_score": 85,
    "extracted_json": {...}
  }
]
```

### 4.5 查询数据

**作用**: 查询数据库中的招标公告数据。

```bash
python src/etl/query_tenders.py
```

### 4.6 批量保存 HTML

**作用**: 将所有已爬取的详情页面 HTML 保存到本地文件，便于离线分析。

```bash
python src/utils/save_all_html.py
```

---

## 五、LLM 多模型测试

系统支持多种 LLM 模型，可以对比不同模型的抽取效果。

### 5.1 支持的模型

| 模型标识 | 模型名称 | 描述 | 价格（元/1M tokens） |
|----------|----------|------|---------------------|
| `deepseek-chat` | DeepSeek V3 | DeepSeek 最新版 | 输入 0.2-2，输出 3 |
| `deepseek-reasoner` | DeepSeek R1 | DeepSeek 推理版 | 输入 4，输出 8 |
| `qwen-max` | 通义千问 Max | 阿里云最强模型 | 输入 20，输出 60 |
| `qwen-plus` | 通义千问 Plus | 阿里云性价比模型 | 输入 4，输出 12 |

### 5.2 使用不同模型

```bash
# 使用 DeepSeek V3
python src/etl/extract_structured.py --model deepseek-chat --limit 10

# 使用 DeepSeek R1
python src/etl/extract_structured.py --model deepseek-reasoner --limit 10

# 使用通义千问 Max
python src/etl/extract_structured.py --model qwen-max --limit 10

# 使用通义千问 Plus
python src/etl/extract_structured.py --model qwen-plus --limit 10
```

### 5.3 批量测试所有模型

Windows 用户可以直接运行测试脚本：

```bash
test_models.bat
```

该脚本会依次使用 4 个模型各抽取 10 条记录，结果分别保存到：
- `output/tenders_structured_deepseek-v3.json`
- `output/tenders_structured_deepseek-r1.json`
- `output/tenders_structured_qwen-max.json`
- `output/tenders_structured_qwen-plus.json`

### 5.4 对比模型效果

可以通过以下方式对比不同模型的效果：

1. **查看 JSON 文件**: 比较不同模型抽取的字段完整度
2. **查看日志**: 比较 token 花费和成功率
3. **人工评估**: 随机抽样检查抽取准确性

---

## 六、常见问题

### 6.1 爬取失败/被拦截

**问题**: 爬取时返回"频繁访问"或"请稍后再试"

**解决方法**:
1. 增加请求间隔：修改 `config.py` 中的 `delay_min` 和 `delay_max`
2. 检查网络连接
3. 稍后再试，避免短时间内大量请求

### 6.2 API Key 无效

**问题**: LLM 调用时报错"Invalid API Key"

**解决方法**:
1. 检查 `config.py` 中的 API Key 是否正确
2. 确认账户余额充足
3. 检查 API Key 是否已激活

### 6.3 数据库文件不存在

**问题**: 运行时提示数据库文件不存在

**解决方法**:
```bash
# 重新创建数据库
python src/utils/reset_db.py
```

### 6.4 附件链接提取失败

**问题**: 部分公告的附件链接未被提取

**原因**: 不同网站的附件链接格式不同

**解决方法**:
1. 检查 HTML 文件确认是否有附件
2. 如确实有但未提取，可手动补充或修改提取逻辑

### 6.5 Token 花费过高

**问题**: LLM 抽取时 token 花费超出预期

**解决方法**:
1. 减少抽取条数（使用 `--limit` 参数）
2. 使用缓存命中（相同内容重复抽取）
3. 切换更便宜的模型（如 qwen-plus）

### 6.6 中文乱码

**问题**: 输出内容出现乱码

**解决方法**:
1. 确保终端编码为 UTF-8
2. Windows 用户运行：`chcp 65001`
3. 检查日志文件获取详细错误信息

### 6.7 查看日志

**查看所有日志文件**:
```bash
python src/utils/manage_logs.py list --days 7
```

**清理旧日志**:
```bash
python src/utils/manage_logs.py clean --days 30 --execute
```

详细日志使用说明请参阅：[日志系统说明](../03_工具使用/日志系统说明.md)

### 6.8 Web 前端使用

**启动 Web 界面**:
```bash
# 一键启动
run.bat

# 或手动启动
# 1. 启动 API 后端
python src/api/main.py
# 2. 启动 Web 前端（新终端）
streamlit run src/main_app.py --server.port 8501
```

**访问地址**:
- Web 界面：http://localhost:8501
- API 文档：http://localhost:8000/docs

详细前端使用说明请参阅：[Web 前端使用指南](Web 前端使用指南.md)

---

## 附录：数据库表结构

### tenders 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| project_name | TEXT | 项目名称 |
| publish_date | TEXT | 发布日期 |
| detail_url | TEXT | 详情链接 |
| content | TEXT | 公告内容 |
| attachment_urls | TEXT | 附件链接列表（JSON 数组） |
| status | TEXT | 状态（new/processed） |
| created_at | TIMESTAMP | 创建时间 |

---

## 技术支持

如遇问题，请查看日志文件：
- 爬取日志：`logs/` 目录
- 抽取日志：`logs/extract_*.log`
