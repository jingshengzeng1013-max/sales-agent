# 政府采购招投标数据系统 - 快速开始指南

## 目录

- [一、快速开始（5 分钟上手）](#一快速开始-5-分钟上手)
- [二、环境准备](#二环境准备)
- [三、配置说明](#三配置说明)
- [四、核心功能使用](#四核心功能使用)
- [五、常见问题](#五常见问题)

---

## 一、快速开始（5 分钟上手）

### 1.1 完整流程

```bash
cd D:\sales_agent\get_data

# 步骤 1: 爬取招标公告列表（约 1-3 分钟）
python -m src.crawler.ccgp_crawler

# 步骤 2: 爬取详情页面（约 5-10 分钟）
python -m src.crawler.crawl_detail

# 步骤 3: LLM 结构化抽取（约 2-5 分钟）
python -m src.etl.core.extract_structured --limit 50

# 步骤 4: 项目聚合（可选）
python -m src.etl.aggregate_projects

# 步骤 5: 向量化与建索引（可选）
python -m src.vectorization.vectorize_data --type tender
python -m src.vectorization.build_index --type tender

# 步骤 6: 启动 Web 服务
python webapp/server_fastapi.py
```

### 1.2 各步骤说明

| 步骤 | 命令 | 作用 | 耗时 |
|------|------|------|------|
| 爬取列表 | `python -m src.crawler.ccgp_crawler` | 爬取招标公告列表 | 1-3 分钟 |
| 爬取详情 | `python -m src.crawler.crawl_detail` | 爬取详情、提取附件 | 5-10 分钟 |
| 结构化抽取 | `python -m src.etl.core.extract_structured --all` | LLM 抽取关键字段 | 视数据量 |
| 项目聚合 | `python -m src.etl.aggregate_projects` | 聚合项目生命周期 | < 2 分钟 |
| 客户画像 | `python -m src.analysis.generate_customer_profiles` | 生成客户画像 | < 1 分钟 |
| 向量化 | `python -m src.vectorization.vectorize_data --type tender` | 生成向量嵌入 | 5-10 分钟 |
| 构建索引 | `python -m src.vectorization.build_index --type tender` | 构建 FAISS+BM25 索引 | 2-5 分钟 |

### 1.3 数据流向

```
中国政府采购网 → 爬虫 → SQLite 数据库 → LLM 抽取 → 结构化 JSON → 向量索引
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
pip install -r requirements.txt
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
    "delay_min": 0.5,            # 请求间隔最小值（秒）
    "delay_max": 1.5,            # 请求间隔最大值（秒）
    "max_pages": 100,            # 爬取页数
    "timeout": 10,               # 请求超时时间（秒）
    "timeType": "4",            # 时间范围：0=今日，1=近三日，2=近一周，3=近一月，4=近三月
    "start_time": "2025:10:14", # 起始日期（格式：YYYY:MM:DD）
    "end_time": None,            # 结束日期（None 表示当天）
}
```

### 3.3 修改关键词

编辑 `src/config.py`，修改 `CRAWLER_CONFIG["keyword"]` 参数：

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

#### 本地 LLM 配置

系统支持使用本地部署的 LLM（需配置环境变量）：

```bash
set LOCAL_LLM_BASE_URL=http://10.210.10.51:8002/v1
set LOCAL_LLM_MODEL=/models/Kimi-K2.5
```

---

## 四、核心功能使用

### 4.1 爬取招标公告列表

**作用**: 爬取中国政府采购网的招标公告列表，保存基本信息到数据库。

```bash
python -m src.crawler.ccgp_crawler
```

**输出示例**:
```
============================================================
CCGP Crawler - Full Version
============================================================
[DB] Initialized: D:/sales_agent/get_data/data/ccgp_data.db
[PAGE 1]
[FETCH] https://search.ccgp.gov.cn/bxsearch...
  [OK] Status: 200, Length: 12345
  [FOUND] 30 tenders
============================================================
Done! New: 25 items, Total: 25 items
============================================================
```

### 4.2 爬取详情页面

**作用**: 根据列表中的详情链接，爬取完整公告内容，提取附件下载链接。

```bash
python -m src.crawler.crawl_detail
```

### 4.3 结构化字段抽取

**作用**: 使用 LLM 从公告内容中抽取结构化字段，如采购人、预算金额、省份等。

#### 基础用法

```bash
# 抽取前 50 条记录
python -m src.etl.core.extract_structured --limit 50

# 抽取所有记录
python -m src.etl.core.extract_structured --all

# 仅测试第一条
python -m src.etl.core.extract_structured --test-first

# 指定模型
python -m src.etl.core.extract_structured --all --model deepseek
```

#### 输出文件

- **结构化数据**: `data/output/etl/tenders_structured.jsonl`
- **日志文件**: `logs/extract_*.log`

### 4.4 客户画像生成

```bash
python -m src.analysis.generate_customer_profiles
```

**输出**: `data/output/customer/customer_profiles.jsonl`

### 4.5 Web 服务启动

**启动 API 服务**:

```bash
cd D:\sales_agent\get_data
python webapp/server_fastapi.py
```

服务地址：`http://127.0.0.1:8103`

**访问前端**:
- 轻量演示版：http://127.0.0.1:8103/static/demo.html
- 完整功能版：http://127.0.0.1:8103/static/index.html

---

## 五、常见问题

### 5.1 爬取失败/被拦截

**问题**: 爬取时返回"频繁访问"或"请稍后再试"

**解决方法**:
1. 增加请求间隔：修改 `config.py` 中的 `delay_min` 和 `delay_max`
2. 检查网络连接
3. 稍后再试，避免短时间内大量请求

### 5.2 API Key 无效

**问题**: LLM 调用时报错"Invalid API Key"

**解决方法**:
1. 检查 `config.py` 中的 API Key 是否正确
2. 确认账户余额充足
3. 检查 API Key 是否已激活

### 5.3 数据库文件不存在

**问题**: 运行时提示数据库文件不存在

**解决方法**:
```bash
# 爬虫会自动创建数据库
python -m src.crawler.ccgp_crawler
```

### 5.4 附件链接提取失败

**问题**: 部分公告的附件链接未被提取

**原因**: 不同网站的附件链接格式不同

**解决方法**:
1. 检查 HTML 文件确认是否有附件
2. 如确实有但未提取，可手动补充或修改提取逻辑

### 5.5 Token 花费过高

**问题**: LLM 抽取时 token 花费超出预期

**解决方法**:
1. 减少抽取条数（使用 `--limit` 参数）
2. 使用缓存命中（相同内容重复抽取）
3. 切换更便宜的模型

### 5.6 中文乱码

**问题**: 输出内容出现乱码

**解决方法**:
1. 确保终端编码为 UTF-8
2. Windows 用户运行：`chcp 65001`
3. 检查日志文件获取详细错误信息

### 5.7 查看日志

**日志目录**: `logs/`

详细日志使用说明请参阅：[日志系统说明](../03_工具使用/日志系统说明.md)

---

## 技术支持

如遇问题，请查看日志文件：
- 爬取日志：`logs/` 目录
- 抽取日志：`logs/extract_*.log`
