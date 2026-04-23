# Web 应用模块 (Webapp)

> 基于 FastAPI 框架构建的销售情报系统 Web 服务，提供招标检索、客户画像、AI 销售建议等核心功能。

## 目录结构

```
webapp/
├── server_fastapi.py   # FastAPI 后端主服务（当前使用）
├── server.py            # 旧版服务（保留兼容）
├── utils.py             # 工具函数
├── router/             # API 路由模块
│   ├── db.py           # 数据库操作
│   ├── crawl.py        # 爬虫控制
│   ├── extract.py      # LLM 抽取
│   ├── intel.py        # 招标下拉数据
│   ├── retrieval.py    # 混合检索
│   └── output.py       # 输出文件管理
└── static/             # 前端静态资源
    ├── index.html      # 完整版页面
    ├── demo.html       # 演示版页面（推荐）
    └── css/            # 样式文件
```

## 快速启动

```bash
cd get_data

# 启动后端服务
python webapp/server_fastapi.py

# 服务启动后访问
# 本地：http://127.0.0.1:8103/static/demo.html
# 局域网：http://<你的IP>:8103/static/demo.html
```

## 核心 API 接口

### 1. 招标检索 (`/api/retrieval/*`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/retrieval/search-tenders` | POST | 按产品检索招标库（核心接口） |
| `/api/retrieval/filter-options` | GET | 获取省份、公告类型筛选选项 |
| `/api/retrieval/product-options` | GET | 获取产品列表 |

**检索请求参数**：

```json
{
    "product_id": "prod_001",
    "top_k": 20,
    "min_score": 0.0,
    "use_vector": true,
    "use_bm25": true,
    "vector_weight": 0.5,
    "bm25_weight": 0.5,
    "province": "北京",
    "notice_type": "招标公告",
    "exclude_won": false,
    "sort_by": "score",
    "client_value_weight": 0.0
}
```

### 2. 客户画像 (`/api/customer/*`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/customer/profile/{name}` | GET | 获取客户画像详情 |

### 3. AI 销售建议 (`/api/analysis/*`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/analysis/sales-suggestions` | POST | 获取 AI 生成的销售建议 |

**请求示例**：

```json
{
    "project_data": {
        "project_name_std": "智慧校园三期",
        "buyer_name": "某省重点大学",
        "total_budget": 5000000,
        "content_summary": "采购智慧黑板、录播系统等"
    },
    "customer_name": "某省重点大学"
}
```

### 4. 数据库浏览 (`/api/db/*`)

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/db/tables` | GET | 获取数据库表列表 |
| `/api/db/table/{table_name}` | GET | 查询指定表数据 |

## 前端页面

### Demo 页面 (`/static/demo.html`)

轻量级演示页面，聚焦核心检索流程：

- 按产品检索招标库
- 查看招标详情（预算、评分、技术要求）
- AI 销售建议生成
- 客户画像查看

### 完整版页面 (`/static/index.html`)

功能完整的管理界面，包含爬虫控制、LLM 抽取等功能。

## 技术架构

### 双路检索引擎

底层使用 **FAISS 向量检索** + **BM25 关键词检索** 双路召回，通过 **RRF 算法** 融合排序：

```
RRF_score(d) = Σ 1/(k + rank_i(d)),  k=60
```

### 服务初始化

启动时自动：
1. 清理端口占用
2. 加载 FAISS 索引到内存
3. 预热向量化和 LLM 模型
4. 加载客户画像数据

## 服务配置

在 `server_fastapi.py` 中配置：

```python
# 服务地址和端口
HOST = "0.0.0.0"      # 监听所有网卡
PORT = 8103           # 端口

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 依赖服务

| 服务 | 地址 | 说明 |
|------|------|------|
| 向量 Embedding | `http://10.210.10.51:8022/v1` | 文本向量化 |
| 本地 LLM | `http://10.210.10.51:8001/v1` | AI 销售建议生成 |

## 数据缓存

服务启动时加载到内存的数据：

| 数据 | 路径 |
|------|------|
| 客户画像 | `data/output/customer/customer_profiles.jsonl` |
| 产品检索器 | `data/index/product.index` |
| 招标检索器 | `data/index_tenders/tenders.index` |
