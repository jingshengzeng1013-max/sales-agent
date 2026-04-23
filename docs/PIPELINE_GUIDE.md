# 销售情报工作流使用指南

## 完整工作流程

```
招标网 URL → 爬取详情 → 结构化提取 → 客户识别 → 产品匹配 → 输出报告
```

## 方式一：端到端工作流（推荐新数据）

适用于从招标网 URL 开始的全流程处理：

```bash
cd D:\sales_agent\get_data

# 使用招标网详情页 URL
python scripts/pipeline_end_to_end.py --url "https://www.ccgp.gov.cn/notice/detail/xxxxx"

# 指定 LLM 模型
python scripts/pipeline_end_to_end.py --url "https://..." --model "qwen-plus"
```

**输出：**
- 数据库中保存结构化数据
- `output/sales_reports/` 目录生成销售报告

## 方式二：测试工作流（使用现有数据）

适用于测试或处理已爬取的数据：

```bash
cd D:\sales_agent\get_data

# 使用最新一条已爬取的数据
python scripts/pipeline_test_with_db.py

# 指定招标 ID
python scripts/pipeline_test_with_db.py --tender-id 145
```

## 分步执行工具

每个步骤也可以单独执行：

### 1. 爬取招标网详情页

```bash
python -c "
from tools.crawl_detail.executor import execute
result = execute({'limit': 10, 'save_html': True})
print(result)
"
```

### 2. 结构化提取（LLM）

```bash
python -c "
from tools.extract_structured.executor import execute
result = execute({'limit': 5, 'model': 'deepseek-chat'})
print(result)
"
```

### 3. 产品匹配

```bash
python -c "
from tools.match_product.executor import execute
result = execute({
    'customer_type': 'GOVERNMENT',
    'customer_type_name': '政府/事业单位',
    'technical_keywords': ['移动通信', '测试系统'],
    'requirement_text': '用于移动通信领域的测试环境系统',
    'use_llm': False
})
print(result)
"
```

### 4. 生成销售报告

```bash
python -c "
from tools.generate_report.executor import execute
result = execute({
    'leads': [{
        'customer_name': '中国科学院计算技术研究所',
        'customer_type': 'GOVERNMENT',
        'customer_type_name': '政府/事业单位',
        'project_name': '移动通信测试系统',
        'matched_products': ['DX-S701 天通基带芯片'],
        'match_score': 100,
        'match_reason': '混合检索匹配',
        'requirement_text': '用于移动通信领域的测试',
        'budget': '280 万元'
    }],
    'format': 'markdown',
    'min_score': 60,
    'report_title': '销售机会报告'
})
print(result)
"
```

## 查询招标数据库

```bash
python -c "
from tools.query_tenders.executor import execute
result = execute({
    'keyword': '通信',
    'province': '',
    'min_budget': 1000000,
    'max_budget': 10000000,
    'limit': 20,
    'include_structured': True
})
print(result)
"
```

## 工作流输出示例

**输入：** 招标网详情页 URL

**输出报告内容：**
- 客户名称
- 客户类型（车厂/手机厂/政府/工控等）
- 匹配产品（星闪芯片/DX-S701/天通卫星基带等）
- 匹配度评分（0-100）
- 预算金额
- 需求点摘要
- 切入建议

## 产品匹配规则

| 客户类型 | 匹配产品 |
|---------|---------|
| 车厂 (AUTO_OEM) | 星闪芯片、实时多核处理器、车联网卫星终端 |
| 手机厂商 (PHONE_OEM) | 星闪芯片、DX-S702 高低轨双模芯片、DX-T502 射频模组 |
| 穿戴设备商 (WEARABLE_OEM) | 星闪芯片、DX-S702、DX-T502 |
| 政府/事业单位 (GOVERNMENT) | 天通卫星基带、DX-S701、IoT 卫星模组 |
| 工控厂商 (INDUSTRIAL) | 实时多核处理器、边缘 AI 处理器、5G RedCap |
| 三防设备商 (RUGGED) | 天通卫星基带、DX-S701、DX-T502 |

## 依赖检查

```bash
# 检查数据库
python -c "import sqlite3; print('SQLite OK')"

# 检查 FAISS 索引
python -c "
from pathlib import Path
index_dir = Path('data/index')
assert (index_dir / 'faiss.index').exists()
assert (index_dir / 'bm25.pkl').exists()
print('FAISS 索引 OK')
"

# 检查 LLM 配置
python -c "
from src.llm.invoke import invoke_chat_messages
print('LLM 配置 OK')
"
```

## 故障排除

**问题 1: 爬取被拦截**
- 增加随机延迟时间
- 使用代理 IP
- 减少并发请求

**问题 2: LLM 提取失败**
- 检查 API key 配置
- 查看 `src/llm/invoke.py` 中的模型配置
- 确保有足够的 token 余额

**问题 3: 产品匹配度低**
- 检查关键词提取是否准确
- 调整客户类型识别规则
- 考虑启用 LLM 增强匹配 (`use_llm: true`)

## 输出目录

```
get_data/
├── data/
│   └── index/           # FAISS 索引文件
│       ├── faiss.index
│       ├── bm25.pkl
│       └── metadata.json
├── output/
│   ├── sales_reports/   # 销售报告
│   └── tenders_structured.json
└── scripts/
    ├── pipeline_end_to_end.py
    └── pipeline_test_with_db.py
```
