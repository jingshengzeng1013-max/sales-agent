# 销售分析模块 (Analysis)

> 利用 LLM 结合项目需求与客户画像，生成智能销售切入点建议和客户 360° 画像分析。

## 目录结构

```
src/analysis/
├── sales_advisor.py              # AI 销售建议引擎
└── generate_customer_profiles.py # 客户画像生成器
```

## 核心功能

### 1. 销售建议引擎 (SalesAdvisor)

利用 LLM（大语言模型）自动分析招标项目，生成针对性的销售切入点建议。

**核心特性**：
- 支持本地 LLM（如 Qwen3.5-27B）和云端 LLM（DeepSeek）
- 自动过滤"思考过程"等干扰内容
- 输出结构化的 Markdown 格式建议
- **支持 JSONL 缓存，避免重复调用 LLM**

**使用示例**：

```python
from src.analysis.sales_advisor import SalesAdvisor

advisor = SalesAdvisor()

project_data = {
    "project_name_std": "智慧校园三期",
    "buyer_name": "某省重点大学",
    "total_budget": 5000000,
    "content_summary": "采购智慧黑板、录播系统等",
    "technical_requirements_summary": "需要支持国产化替代",
    "application_scenario": "教育信息化",
    "product_keywords": ["智慧黑板", "录播主机"]
}

customer_profile = {
    "value_profile": {
        "tender_count": 5,
        "avg_opportunity_score": 85
    },
    "demand_profile": {
        "tech_keywords": ["智慧教育", "多媒体"]
    },
    "competitive_landscape": {
        "past_winners": ["华为", "海康威视"]
    }
}

suggestions = advisor.generate_suggestions(project_data, customer_profile)
print(suggestions)
```

**缓存功能**：

生成的建议会自动缓存到 `data/output/sales_suggestions/suggestions.jsonl`，相同项目再次查询时直接返回缓存结果，无需重复调用 LLM。

```python
# 禁用缓存（测试用）
advisor = SalesAdvisor(use_cache=False)

# 单次禁用
suggestions = advisor.generate_suggestions(project_data, customer_profile, use_cache=False)
```

**缓存格式**：
```json
{"cache_key": "a1b2c3...", "project_name": "xxx", "buyer_name": "xxx", "customer_name": "xxx", "suggestions": "### 1. ..."}
```

**输出结构**：

建议内容包含以下四个标准章节：
- ### 1. 需求匹配度分析
- ### 2. 竞争策略建议
- ### 3. 关键切入点
- ### 4. 风险提示

### 2. 客户画像生成器 (generate_customer_profiles)

从结构化标讯数据中聚合生成客户 360° 全景画像。

**画像维度**：

| 维度 | 内容 |
|------|------|
| 基础信息 | 客户名称、地区、类型 |
| 价值评估 | 历史招标次数、总预算、平均机会评分 |
| 需求特征 | 核心技术关键词、应用场景偏好 |
| 竞争态势 | 历史中标单位、中标率分析 |
| 联系方式 | 联系人、电话、邮箱 |

**使用示例**：

```python
from src.analysis.generate_customer_profiles import generate_profiles

# 生成客户画像
generate_profiles()

# 指定输出路径
generate_profiles(output_path="data/output/customer/my_profiles.jsonl")
```

**输出格式** (JSONL)：

```json
{
    "customer_name": "某省政府办公厅",
    "basic_info": {
        "province": "广东省",
        "city": "广州市"
    },
    "value_profile": {
        "tender_count": 12,
        "total_budget": 85000000,
        "avg_opportunity_score": 82.5
    },
    "demand_profile": {
        "tech_keywords": ["路由器", "交换机", "网络安全"],
        "application_scenarios": ["政务网络", "数据中心"]
    },
    "competitive_landscape": {
        "past_winners": ["华为", "新华三"],
        "win_rates": {"华为": 0.6, "新华三": 0.3, "其他": 0.1}
    },
    "contact_info": {
        "persons": ["张三", "李四"],
        "phones": ["138xxxxxxx", "139xxxxxxx"]
    },
    "last_updated": "2026-04-20"
}
```

## API 接口

### `POST /api/analysis/sales-suggestions`

获取 AI 销售建议

**请求参数**：

```json
{
    "project_data": {
        "project_name_std": "智慧校园三期",
        "buyer_name": "某省重点大学",
        "total_budget": 5000000,
        "content_summary": "采购智慧黑板、录播系统等",
        "product_keywords": ["智慧黑板"]
    },
    "customer_name": "某省重点大学"
}
```

**返回格式**：

```json
{
    "suggestions": "### 1. 需求匹配度分析\n\n..."
}
```

### `GET /api/customer/profile/{customer_name}`

获取客户画像详情

## LLM 配置

在 `src/config.py` 中配置 LLM：

```python
# 本地 LLM（默认）
LOCAL_LLM_CONFIG = {
    "base_url": "http://10.210.10.51:8001/v1",
    "model": "/models/Qwen3.5-27B",
}

# DeepSeek 云端 LLM
DEEPSEEK_CONFIG = {
    "api_key": "sk-xxx",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
}
```

## 数据依赖

| 模块 | 依赖数据 |
|------|---------|
| SalesAdvisor | `data/output/customer/customer_profiles.jsonl` |
| generate_profiles | `tender_structured` 表 + `tenders` 表 |

## 流水线集成

完整的分析流水线：

```bash
# 1. 爬取数据
python src/crawler/ccgp_crawler.py
python src/crawler/crawl_detail.py

# 2. 结构化抽取
python src/etl/extract_structured.py --all
python src/etl/import_structured_db.py

# 3. 生成客户画像
python src/analysis/generate_customer_profiles.py

# 4. 生成销售建议（通过 Web API）
# POST /api/analysis/sales-suggestions
```
