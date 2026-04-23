# 招标检索系统 API 对接文档

## 概述

本文档描述招标检索系统的对外 API 接口。系统基于 FastAPI 构建，支持按产品检索匹配招标项目，返回结构化的招标数据。

**服务地址**：http://10.175.1.209:8103/

---

## 一、获取产品列表

获取可检索的产品列表，用于展示给用户选择或系统间流转产品 ID。

### 请求

```
GET /api/retrieval/product-options
```

### 响应

```json
{
  "rows": [
    {
      "id": "uuid-xxx-001",
      "name": "智慧城市综合管理平台",
      "description": "面向城市治理的综合性管理平台..."
    },
    {
      "id": "uuid-xxx-002",
      "name": "视频监控系统",
      "description": "基于AI的智能视频监控解决方案..."
    }
  ]
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 产品唯一标识（UUID），作为搜索接口的 `product_id` |
| `name` | string | 产品名称 |
| `description` | string | 产品描述 |

---

## 二、招标项目搜索

根据选定的产品检索匹配的招标项目，支持丰富的筛选和排序参数。

### 请求

```
POST /api/retrieval/direct-search
Content-Type: application/json
```

### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `product_id` | string | **是** | - | 产品ID，从产品列表接口获取 |
| `top_k` | integer | 否 | 10 | 返回结果数量，范围 1~100 |
| `use_vector` | boolean | 否 | true | 是否启用向量检索 |
| `use_bm25` | boolean | 否 | true | 是否启用关键词检索 |
| `vector_weight` | float | 否 | 0.5 | 向量检索权重，范围 0.0~1.0 |
| `bm25_weight` | float | 否 | 0.5 | 关键词检索权重，范围 0.0~1.0 |
| `province` | string | 否 | null | 省份筛选，如"广东"、"北京" |
| `city` | string | 否 | null | 城市筛选（精确匹配） |
| `min_budget` | float | 否 | null | 最低预算金额，单位：万元 |
| `max_budget` | float | 否 | null | 最高预算金额，单位：万元 |
| `exclude_won` | boolean | 否 | false | 是否排除已中标的招标 |
| `sort_by` | string | 否 | "score" | 排序方式：`"score"` 按相关性，`"date"` 按发布时间 |
| `client_value_weight` | float | 否 | 0.0 | 客户价值权重，范围 0.0~1.0 |
| `aggregate_by_project` | boolean | 否 | true | 是否按项目汇总多条公告 |

**注意**：`min_budget` 和 `max_budget` 的单位为**万元**。例如 `min_budget: 50` 表示筛选预算≥50万元的项目。

### 响应

```json
{
  "success": true,
  "query": "智慧城市综合管理平台 面向城市治理的综合性管理平台...",
  "total": 5,
  "results": [
    {
      "tender_id": "proj-uuid-001",
      "score": 0.8542,
      "is_aggregated": true,
      "match_count": 3,
      "scores": {
        "vector_score": 0.9123,
        "bm25_score": 0.7561,
        "rrf_raw_score": 0.0523
      },
      "data": {
        "buyer_name_std": "深圳市政务服务数据管理局",
        "project_name_std": "深圳市智慧城市综合管理平台建设项目",
        "province": "广东",
        "city": "深圳",
        "budget_amount": 15000000,
        "budget_display": "1500.00万元",
        "publish_date": "2026-03-15",
        "content_summary": "建设智慧城市综合管理平台，涵盖城市治理、应急指挥...",
        "technical_requirements_summary": "要求采用微服务架构，支持弹性扩展...",
        "application_scenario": "城市治理、应急指挥、城市管理",
        "product_keywords": ["智慧城市", "大数据", "物联网", "视频监控"],
        "opportunity_score": 85,
        "opportunity_reason": "预算充足，项目规模大，需求匹配度高",
        "contact_person": "张先生",
        "contact_phone": "0755-xxxxxxxx",
        "status": "进行中",
        "winning_info": null,
        "detail_url": "https://www.ccgp.gov.cn/xxxxx"
      }
    }
  ],
  "product_info": {
    "product_id": "uuid-xxx-001",
    "name": "智慧城市综合管理平台",
    "description": "面向城市治理的综合性管理平台...",
    "query_preview": "智慧城市综合管理平台 面向城市治理的综合性管理平台..."
  },
  "params": {
    "use_vector": true,
    "use_bm25": true,
    "vector_weight": 0.5,
    "bm25_weight": 0.5,
    "province": null,
    "city": null,
    "min_budget": null,
    "max_budget": null,
    "exclude_won": false,
    "sort_by": "score",
    "client_value_weight": 0.0,
    "aggregate_by_project": true
  }
}
```

### 响应字段说明

| 字段 | 说明 |
|------|------|
| `success` | 请求是否成功 |
| `query` | 实际用于检索的查询文本（由产品自动生成） |
| `total` | 返回结果数量 |
| `results` | 招标列表，每条字段说明见下表 |

**results 数组中每个元素的字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `tender_id` | string | 招标/项目唯一标识 |
| `score` | float | 综合相关度得分（0~1） |
| `is_aggregated` | boolean | 是否为项目汇总模式 |
| `match_count` | int | 汇总模式下匹配到的公告条数 |
| `scores.vector_score` | float | 向量检索得分 |
| `scores.bm25_score` | float | BM25关键词检索得分 |
| `scores.rrf_raw_score` | float | RRF融合原始得分 |
| `data.buyer_name_std` | string | 采购单位（标准化） |
| `data.project_name_std` | string | 项目名称（标准化） |
| `data.province` | string | 省份 |
| `data.city` | string | 城市 |
| `data.budget_amount` | float | 预算金额（元），`budget_display` 为格式化显示 |
| `data.publish_date` | string | 发布时间（YYYY-MM-DD） |
| `data.content_summary` | string | 采购内容摘要 |
| `data.technical_requirements_summary` | string | 技术要求摘要 |
| `data.application_scenario` | string | 应用场景 |
| `data.product_keywords` | string[] | 产品关键词列表 |
| `data.opportunity_score` | int | 机会评分（0~100） |
| `data.opportunity_reason` | string | 评分原因 |
| `data.contact_person` | string | 联系人 |
| `data.contact_phone` | string | 联系电话 |
| `data.status` | string | 项目状态 |
| `data.winning_info` | object/null | 中标信息（如已中标） |
| `data.detail_url` | string | 公告原文链接 |

---

## 三、错误响应

接口错误时返回标准 HTTP 状态码和错误信息：

```json
{
  "detail": "Product uuid-not-found not found"
}
```

| 状态码 | 说明 |
|--------|------|
| 404 | 产品ID不存在 |
| 422 | 请求参数校验失败 |
| 500 | 服务器内部错误 |

---

## 四、调用示例

### 1. 获取产品列表（Python）

```python
import requests

response = requests.get("http://10.210.10.51:8103/api/retrieval/product-options")
products = response.json()["rows"]
print(products[0]["id"], products[0]["name"])
```

### 2. 执行搜索（Python）

```python
import requests

payload = {
    "product_id": "uuid-xxx-001",
    "top_k": 10,
    "province": "广东",
    "min_budget": 100,
    "max_budget": 5000,
    "exclude_won": False,
    "use_vector": True,
    "use_bm25": True,
    "vector_weight": 0.6,
    "bm25_weight": 0.4,
    "sort_by": "score",
    "aggregate_by_project": True
}

response = requests.post(
    "http://10.210.10.51:8103/api/retrieval/direct-search",
    json=payload
)

data = response.json()
print(f"找到 {data['total']} 条招标")
for item in data["results"]:
    print(item["data"]["project_name_std"],
          item["data"]["budget_display"],
          item["score"])
```

### 3. 前端对接建议

```javascript
// 1. 页面加载时获取产品列表
fetch('/api/retrieval/product-options')
  .then(res => res.json())
  .then(data => {
    // 渲染产品下拉选择框
    renderProductSelect(data.rows);
  });

// 2. 用户选择产品后执行搜索
function searchWithProduct(productId) {
  fetch('/api/retrieval/direct-search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      product_id: productId,
      top_k: 20,
      province: null,
      aggregate_by_project: true
    })
  })
  .then(res => res.json())
  .then(data => {
    // 渲染招标列表
    renderTenderList(data.results);
  });
}
```

---

## 五、其他可用接口

### 获取客户画像

```
GET /api/customer/profile/{customer_name}
```

根据客户名称获取该客户的详细画像数据（历史招标记录、采购偏好、竞争态势等）。

### 生成销售建议

```
POST /api/analysis/sales-suggestions
Content-Type: application/json

{
  "project_data": {
    "project_name_std": "...",
    "buyer_name": "...",
    "total_budget": 15000000,
    "content_summary": "...",
    "technical_requirements_summary": "...",
    "application_scenario": "...",
    "product_keywords": ["智慧城市", "大数据"]
  },
  "customer_name": "深圳市政务服务数据管理局"
}
```

返回 AI 生成的销售切入点建议（Markdown 格式）。

### 查看数据库表

```
GET /api/db/tables                    # 获取所有表
GET /api/db/table/{table_name}        # 获取表数据
```

---

## 六、微信客服推送接口

系统支持通过微信客服接口推送招标通知，支持单用户发送、批量广播等场景。

**基础信息**：

| 项目 | 说明 |
|------|------|
| 路径前缀 | `/api/wechat` |
| 说明 | 对接外部客服系统，可向已关注用户发送模板消息，不受48小时窗口限制 |

---

### 6.1 查询用户列表

获取已关注的微信用户列表。

#### 请求

```
GET /api/wechat/users
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | int | 否 | 1 | 页码（从1开始） |
| size | int | 否 | 10 | 每页条数（最大100） |
| subscribe | int | 否 | 不传=全部 | 关注状态：1=已关注，0=已取关 |

#### 响应

```json
{
  "users": [
    {
      "openid": "obdHZ3ABq00vMKnXEMwQfFK-gOaQ",
      "nickname": "南拥",
      "sex": 0,
      "province": "",
      "city": "",
      "subscribe": 1,
      "subscribe_time": 1776762927,
      "last_interact_time": "2026-04-21T17:16:39",
      "phone": "17604895944",
      "real_name": "左佳利",
      "is_subscribed": true
    }
  ],
  "total": 4,
  "size": 10,
  "current": 1,
  "pages": 1
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `openid` | string | 用户唯一标识，用于发送消息 |
| `nickname` | string | 用户昵称 |
| `subscribe` | int | 关注状态：1=已关注，0=已取关 |
| `last_interact_time` | string | 最后一次与公众号互动时间 |
| `is_subscribed` | bool | 是否已关注 |

---

### 6.2 发送模板消息（单用户）

向指定用户发送模板消息。

#### 请求

```
POST /api/wechat/template/send
Content-Type: application/json
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| openid | string | **是** | - | 接收消息的用户openid |
| first | string | **是** | - | 模板首行（如：新招标通知） |
| keyword1 | string | **是** | - | 关键词1（如：采购单位） |
| keyword2 | string | **是** | - | 关键词2（如：预算金额） |
| keyword3 | string | **是** | - | 关键词3（如：发布时间） |
| remark | string | 否 | "点击查看详情" | 备注 |
| template_id | string | 否 | 默认模板 | 模板消息ID |
| url | string | 否 | 无 | 点击跳转链接 |

#### 请求示例

```json
POST /api/wechat/template/send
{
  "openid": "obdHZ3ABq00vMKnXEMwQfFK-gOaQ",
  "first": "新招标项目：智慧城市综合管理平台",
  "keyword1": "深圳市政务服务数据管理局",
  "keyword2": "1500万元",
  "keyword3": "2026-04-22",
  "remark": "点击查看详情，获取更多商业机会",
  "url": "https://www.ccgp.gov.cn/xxxxx"
}
```

#### 响应

```json
{
  "success": true,
  "errcode": 0,
  "errmsg": "ok"
}
```

#### 错误码

| errcode | 说明 |
|---------|------|
| 0 | 发送成功 |
| 400 | 参数校验失败 |
| 40003 | 无效的openid |
| 43101 | 用户未关注，无法发送模板消息 |
| -1 | 系统内部异常 |

---

### 6.3 广播模板消息（多用户）

向多个用户同时发送相同的模板消息。

#### 请求

```
POST /api/wechat/template/broadcast
Content-Type: application/json
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| user_openids | string[] | **是** | - | 用户openid列表 |
| first | string | **是** | - | 模板首行 |
| keyword1 | string | **是** | - | 关键词1 |
| keyword2 | string | **是** | - | 关键词2 |
| keyword3 | string | **是** | - | 关键词3 |
| remark | string | 否 | "点击查看详情" | 备注 |
| template_id | string | 否 | 默认模板 | 模板消息ID |
| url | string | 否 | 无 | 点击跳转链接 |

#### 请求示例

```json
POST /api/wechat/template/broadcast
{
  "user_openids": [
    "obdHZ3ABq00vMKnXEMwQfFK-gOaQ",
    "obdHZ3ABq00vMKnXEMwQfFK-gOaQ2"
  ],
  "first": "新招标项目：智慧城市综合管理平台",
  "keyword1": "深圳市政务服务数据管理局",
  "keyword2": "1500万元",
  "keyword3": "2026-04-22",
  "remark": "点击查看详情"
}
```

#### 响应

```json
{
  "success": true,
  "success_count": 2,
  "fail_count": 0,
  "total": 2,
  "errors": []
}
```

---

### 6.4 招标更新广播通知

当有新招标项目时，广播通知所有已关注用户。

#### 请求

```
POST /api/wechat/tender-notify
```

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| first | string | **是** | - | 通知标题/首行 |
| keyword1 | string | **是** | - | 采购单位 |
| keyword2 | string | **是** | - | 预算金额 |
| keyword3 | string | **是** | - | 发布时间 |
| url | string | 否 | 无 | 跳转链接 |
| template_id | string | 否 | 默认模板 | 模板ID |
| page | int | 否 | 1 | 从第几页用户开始通知 |
| size | int | 否 | 50 | 每页通知多少用户 |

#### 请求示例

```
POST /api/wechat/tender-notify?first=新招标发布&keyword1=深圳市政务服务数据管理局&keyword2=1500万元&keyword3=2026-04-22
```

或 JSON body：

```json
POST /api/wechat/tender-notify
{
  "first": "新招标发布",
  "keyword1": "深圳市政务服务数据管理局",
  "keyword2": "1500万元",
  "keyword3": "2026-04-22",
  "url": "https://www.ccgp.gov.cn/xxxxx",
  "size": 50
}
```

#### 响应

```json
{
  "success": true,
  "total_success": 150,
  "total_fail": 3,
  "errors": [
    {"openid": "obdHZ3xxx", "error": "invalid openid"},
    {"openid": "obdHZ3yyy", "error": "用户未关注"}
  ]
}
```

---

### 6.5 微信推送调用示例

#### 单用户推送（Python）

```python
import requests

response = requests.post(
    "http://10.175.1.209:8103/api/wechat/template/send",
    json={
        "openid": "obdHZ3ABq00vMKnXEMwQfFK-gOaQ",
        "first": "新招标项目：智慧城市综合管理平台",
        "keyword1": "深圳市政务服务数据管理局",
        "keyword2": "1500万元",
        "keyword3": "2026-04-22",
        "remark": "点击查看详情，获取更多商业机会",
        "url": "https://www.ccgp.gov.cn/xxxxx"
    }
)
print(response.json())
```

#### 广播通知（Python）

```python
import requests

response = requests.post(
    "http://10.175.1.209:8103/api/wechat/tender-notify",
    params={
        "first": "新招标发布",
        "keyword1": "深圳市政务服务数据管理局",
        "keyword2": "1500万元",
        "keyword3": "2026-04-22",
        "url": "https://www.ccgp.gov.cn/xxxxx"
    }
)
result = response.json()
print(f"成功发送: {result['total_success']}, 失败: {result['total_fail']}")
```

#### 查询已关注用户（Python）

```python
import requests

response = requests.get(
    "http://10.175.1.209:8103/api/wechat/users",
    params={"page": 1, "size": 100, "subscribe": 1}
)
data = response.json()
for user in data["users"]:
    print(f"{user['nickname']} ({user['openid']}) - 是否关注: {user['is_subscribed']}")
```

---

### 6.6 注意事项

1. **模板消息不受48小时窗口限制**：可随时向已关注用户发送
2. **openid 获取**：先调用 `/api/wechat/users` 获取用户列表
3. **推送限额**：大规模广播时建议分批进行，避免瞬时请求过多
4. **错误处理**：部分用户发送失败不影响其他用户，可通过响应中的 `errors` 字段查看详情

---

## 六、检索参数调优建议

| 场景 | 建议参数 |
|------|----------|
| 通用检索 | `vector_weight=0.5, bm25_weight=0.5, aggregate_by_project=true` |
| 关键词强匹配 | `use_vector=false, use_bm25=true` |
| 语义相似优先 | `use_vector=true, use_bm25=true, vector_weight=0.8` |
| 大额项目筛选 | `min_budget=500, sort_by=score` |
| 最新项目优先 | `sort_by=date, exclude_won=true` |

---

## 七、注意事项

1. **产品ID不可为空**：`product_id` 是必填参数，系统根据产品关联的 `embedded_content` 自动生成检索query。
2. **预算单位**：前端传入的 `min_budget/max_budget` 单位为**万元**，响应中 `budget_amount` 单位为**元**。
3. **项目汇总**：`aggregate_by_project=true` 时，多条相关公告会汇总为一个项目，`match_count` 表示匹配条数。
4. **机会评分**：`opportunity_score` 是 AI 综合预算、需求匹配度等因素给出的机会指数（0~100）。

---

**更新时间**：2026-04-21
