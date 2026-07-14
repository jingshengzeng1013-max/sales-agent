# 爬虫模块 (Crawler)

> 从中国政府采购网 (ccgp.gov.cn) 抓取招标公告列表和详情数据，支持列表页爬取、详情页爬取、附件下载等功能。

## 目录结构

```
src/crawler/
├── ccgp_crawler.py              # 列表页爬虫（公告列表采集）
├── smart_web_fetch.py           # Smart Web Fetch 五层降级抓取适配器
├── ccgp_smart_fetch.py          # CCGP 首页 Smart Web Fetch 示例采集器
├── ccgp_smart_search.py         # Smart Web Fetch 搜全文列表与详情采集器
├── crawl_detail.py              # 详情页爬虫（正文内容采集）
├── download_attachments.py      # 附件下载器
├── batch_crawl_attachments.py  # 批量附件下载
├── proxy_manager.py             # 代理管理器
├── test_proxy_api.py            # 代理 API 测试
└── __init__.py
```

## 核心功能

### 1. 列表页爬虫 (ccgp_crawler.py)

从政府采购网搜索结果页面抓取招标公告列表。

**使用示例**：

```bash
# 使用默认配置爬取（关键词：通信）
python src/crawler/ccgp_crawler.py

# 指定关键词和页数
python src/crawler/ccgp_crawler.py --keyword "交换机" --max_pages 50

# 禁用代理
python src/crawler/ccgp_crawler.py --no-proxy
```

**输出**：
- `data/output/crawler/tenders_list.jsonl` - 招标公告列表

### 2. 详情页爬虫 (crawl_detail.py)

爬取每条招标公告的详细信息，包括正文内容、附件链接等。

**使用示例**：

```bash
# 爬取详情（基于列表数据）
python src/crawler/crawl_detail.py

# 限制数量
python src/crawler/crawl_detail.py --limit 100

# 测试模式（仅处理第一条）
python src/crawler/crawl_detail.py --test-first
```

**输出**：
- `data/output/crawler/tenders_detail.jsonl` - 招标详情

### 3. Smart Web Fetch 兜底采集 (smart_web_fetch.py / ccgp_smart_fetch.py / ccgp_smart_search.py)

基于虾评 Skill「Smart Web Fetch」公开说明新增的采集技术栈。适合在传统 `curl_cffi + 代理池` 抓取失败时，用第三方 Markdown Reader 和可选浏览器层获取公开网页内容。

**降级顺序**：

1. `markdown.new`
2. `defuddle.md`
3. `r.jina.ai`
4. `Scrapling`（可选依赖）
5. `Playwright`（显式启用 `--include-browser`）

**使用示例**：

```bash
# 抓取中国政府采购网首页链接
python src/crawler/ccgp_smart_fetch.py --max-items 50 --print-items

# 在采购公告栏按“搜全文”搜索通信，并抓取列表和详情
python src/crawler/ccgp_smart_search.py \
  --keyword 通信 \
  --pages 1 \
  --crawl-details \
  --detail-limit 3 \
  --print-items

# 直接使用 CCGP 已构造好的搜索页 URL
python src/crawler/ccgp_smart_search.py \
  --search-url "https://search.ccgp.gov.cn/bxsearch?searchtype=2&page_index=1&start_time=&end_time=&timeType=2&searchparam=&searchchannel=0&dbselect=bidx&kw=%E9%80%9A%E4%BF%A1&bidSort=0&pinMu=0&bidType=0&buyerName=&projectId=&displayZone=&zoneId=&agentName=" \
  --crawl-details \
  --detail-limit 3 \
  --print-items

# 指定目标 URL 和输出文件
python src/crawler/ccgp_smart_fetch.py \
  --url https://www.ccgp.gov.cn/ \
  --output data/output/crawler/ccgp_home_smart_fetch.jsonl

# 如需接入既有 ETL，可把 Smart 搜索输出写到标准文件名
python src/crawler/ccgp_smart_search.py \
  --keyword 通信 \
  --pages 1 \
  --crawl-details \
  --list-output data/output/crawler/tenders_list.jsonl \
  --detail-output data/output/crawler/tenders_detail.jsonl
```

**输出**：
- `data/output/crawler/ccgp_home_smart_fetch.jsonl` - 首页链接采集结果
- `data/output/crawler/tenders_list_smart_fetch.jsonl` - 搜全文采购公告列表
- `data/output/crawler/tenders_detail_smart_fetch.jsonl` - 搜全文详情正文解析结果

**注意**：
- `markdown.new`、`defuddle.md`、`r.jina.ai` 会接收目标 URL，请仅用于公开网页采集。
- 当前 Skill 下载接口需要虾评平台 API Key；本项目实现基于公开技能说明和公开 Reader 文档。

### 4. 附件下载 (download_attachments.py / batch_crawl_attachments.py)

下载招标公告中的附件文件（PDF、DOC、XLS 等）。

**使用示例**：

```bash
# 单条下载
python src/crawler/download_attachments.py --url "http://xxx.gov.cn/attachment.pdf"

# 批量下载
python src/crawler/batch_crawl_attachments.py --input data/output/crawler/tenders_detail.jsonl
```

## 配置参数

在 `src/config.py` 中配置：

```python
CRAWLER_CONFIG = {
    "base_url": "https://search.ccgp.gov.cn/bxsearch",
    "keyword": "通信",                    # 搜索关键词
    "delay_min": 0.5,                     # 请求间隔最小值（秒）
    "delay_max": 1.5,                     # 请求间隔最大值（秒）
    "page_index": 100,                    # 起始页码
    "max_pages": 100,                     # 最大页数（0=爬取所有）
    "timeout": 10,                         # 请求超时（秒）
    # 代理配置
    "use_proxy": True,
    "proxy_api_url": "https://share.proxy.qg.net/get?key=xxx",
    "proxy_num": 5,                       # 提取代理数量
    "proxy_ttl": 60,                      # 代理有效期（秒）
    # 搜索参数
    "searchtype": "2",                    # 1=标题，2=全文
    "bidSort": "0",                       # 0=时间，1=相关性
    "timeType": "4",                      # 时间范围
    "start_time": "2025:10:14",          # 开始时间
}
```

## 反爬策略

### 1. 代理轮换

使用代理池自动轮换 IP，避免被封禁：

```python
from src.crawler.proxy_manager import ProxyManager

proxy_mgr = ProxyManager()
proxy = proxy_mgr.get_proxy()  # 获取一个可用代理
```

### 2. 请求延迟

随机延迟模拟人工访问：

```python
import random
import time
time.sleep(random.uniform(delay_min, delay_max))
```

### 3. TLS 指纹绕过

使用 `curl_cffi` 模拟浏览器 TLS 指纹：

```python
from curl_cffi import requests
response = requests.get(url, impersonate="chrome")
```

## 数据流程

```
政府采购网
    │
    ├──→ [ccgp_crawler.py] → tenders_list.jsonl
    │                           │
    │                           └──→ [crawl_detail.py] → tenders_detail.jsonl
    │                                                       │
    │                                                       └──→ [download_attachments.py] → data/attachment/
    │
    ├──→ [ccgp_smart_search.py] → tenders_list_smart_fetch.jsonl
    │                                  │
    │                                  └──→ tenders_detail_smart_fetch.jsonl
    │
    └──→ [ETL 模块] → 结构化数据
            │
            └──→ [检索模块] → 索引构建 → 前端展示
```

## 常见问题

**Q: 爬虫被拦截**

```bash
# 1. 检查代理是否可用
python src/crawler/test_proxy_api.py

# 2. 增加请求间隔
# 修改 config.py 中 delay_min/delay_max

# 3. 更换代理 API
```

**Q: 数据为空**

```bash
# 1. 检查网络连接
curl -I "https://search.ccgp.gov.cn/bxsearch?searchtype=2&bidSort=0&timeType=4&displayZone=..."

# 2. 验证关键词配置
# 修改 config.py 中 keyword 为更通用的词

# 3. 检查页数限制
# max_pages=0 表示爬取所有页
```
