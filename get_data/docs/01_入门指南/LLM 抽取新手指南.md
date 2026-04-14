# LLM 结构化抽取 - 新手指南

## 什么是结构化抽取？

结构化抽取是将**非结构化的招标公告文本**转换为**结构化的 JSON 数据**的过程。

### 抽取前后对比

**抽取前（原始文本）**:
```
中国移动通信集团广东有限公司就"2026 年通信设备采购项目"进行公开招标，
项目预算 500 万元，投标文件递交截止时间为 2026 年 4 月 15 日...
```

**抽取后（结构化数据）**:
```json
{
  "tender_id": 1,
  "project_name": "2026 年通信设备采购项目",
  "announce_type": "招标公告",
  "buyer_name_std": "中国移动通信集团广东有限公司",
  "province": "广东省",
  "city": "",
  "budget_amount": 5000000,
  "budget_text": "500 万元",
  "deadline": "2026-04-15",
  "product_keywords": ["通信设备"],
  "opportunity_score": 85
}
```

---

## 快速开始

### 前提条件

1. **已爬取数据到数据库**
   ```bash
   # 如果还没有数据，先执行爬取
   python src/utils/reset_db.py
   python src/crawler/ccgp_crawler.py
   python src/crawler/crawl_detail.py
   ```

2. **配置 LLM API Key**

   编辑 `src/config.py`，填入你的 API Key：
   ```python
   DEEPSEEK_CONFIG = {
       "api_key": "sk-xxx",  # 替换为你的 DeepSeek API Key
   }
   ```

### 第一步：测试抽取

先测试第一条数据，确保配置正确：

```bash
python src/etl/extract_structuted.py --test-first
```

**预期输出**:
```
============================================================
开始抽取任务：limit=1, use_llm=True, model=deepseek-chat
============================================================
从数据库获取 1 条记录
未找到已有数据文件，从头开始

抽取进度：100%|████████| 1/1 [00:03<00:00,  3.2s/条, 状态=成功 跳过=0 成功=1 LLM=1]

[TOKEN] input=1234 output=567 total=1801 cost=0.0027 元 (0.0011-0.0043)

============================================================
完成！成功处理 1/1 条，跳过 0 条
============================================================
```

### 第二步：批量抽取

测试成功后，可以批量抽取：

```bash
# 抽取前 50 条
python src/etl/extract_structured.py --limit 50

# 抽取所有记录
python src/etl/extract_structured.py --all
```

---

## 输出文件

### JSON 文件位置

抽取结果保存在：
```
output/tenders_structured_deepseek-chat.json
```

### JSON 文件内容示例

```json
[
  {
    "tender_id": 1,
    "project_name": "2026 年通信设备采购项目",
    "announce_type": "招标公告",
    "buyer_name_std": "中国移动通信集团广东有限公司",
    "province": "广东省",
    "budget_amount": 5000000,
    "product_keywords": ["通信设备", "路由器"],
    "opportunity_score": 85
  },
  {
    "tender_id": 2,
    "project_name": "某某系统建设项目",
    "announce_type": "中标公告",
    "buyer_name_std": "中国电信集团",
    "province": "北京市",
    "budget_amount": 3000000,
    "product_keywords": ["系统集成", "软件开发"],
    "opportunity_score": 72
  }
]
```

---

## 使用不同模型

系统支持 4 种 LLM 模型，可以对比效果：

### 模型对比

| 模型 | 优点 | 缺点 | 适合场景 |
|------|------|------|----------|
| DeepSeek V3 | 性价比高，速度快 | 复杂推理稍弱 | 日常批量抽取 |
| DeepSeek R1 | 推理能力强 | 价格较高 | 复杂公告抽取 |
| 通义千问 Max | 中文理解最强 | 价格最贵 | 高精度要求 |
| 通义千问 Plus | 性价比高 | 能力中等 | 日常使用 |

### 切换模型

```bash
# DeepSeek V3（默认推荐）
python src/etl/extract_structured.py --model deepseek-chat --limit 10

# DeepSeek R1（推理版）
python src/etl/extract_structured.py --model deepseek-reasoner --limit 10

# 通义千问 Max
python src/etl/extract_structured.py --model qwen-max --limit 10

# 通义千问 Plus
python src/etl/extract_structured.py --model qwen-plus --limit 10
```

### 批量测试所有模型

运行测试脚本，自动对比 4 个模型的效果：

```bash
test_models.bat
```

测试完成后，会生成 4 个 JSON 文件：
- `output/tenders_structured_deepseek-v3.json`
- `output/tenders_structured_deepseek-r1.json`
- `output/tenders_structured_qwen-max.json`
- `output/tenders_structured_qwen-plus.json`

---

## 费用说明

### DeepSeek 定价（2026 年 3 月）

| 项目 | 价格（元/1M tokens） |
|------|---------------------|
| 输入（缓存命中） | ¥0.2 |
| 输入（缓存未命中） | ¥2.0 |
| 输出 | ¥3.0 |

### 单条记录花费估算

```
输入：约 1000-2000 tokens
输出：约 500-800 tokens

花费范围：¥0.001 - ¥0.005 / 条
```

### 100 条记录总花费

```
约 ¥0.1 - ¥0.5 元
```

### 查看实时花费

每次抽取时都会显示 token 花费：

```
[TOKEN] input=1234 output=567 total=1801 cost=0.0027 元 (0.0011-0.0043)
```

---

## 常见问题

### Q1: 抽取失败怎么办？

**检查步骤**:
1. 确认 API Key 配置正确
2. 确认账户余额充足
3. 查看日志文件：`logs/extract_*.log`

### Q2: 抽取的字段不完整？

**可能原因**:
- 公告内容本身信息不全
- 模型理解有偏差

**解决方法**:
1. 尝试切换更强的模型（如 qwen-max）
2. 检查原始公告内容是否包含该信息

### Q3: 如何查看抽取结果？

**方法 1**: 直接打开 JSON 文件
```bash
# Windows
notepad output/tenders_structured_deepseek-chat.json

# macOS/Linux
cat output/tenders_structured_deepseek-chat.json
```

**方法 2**: 使用查询工具
```bash
python src/etl/query_tenders.py
```

### Q4: 抽取到一半出错了，需要重新开始吗？

**不需要**。程序会自动跳过已抽取的记录：

```bash
# 再次运行相同命令，会自动继续
python src/etl/extract_structured.py --limit 50
```

### Q5: 如何清空抽取结果重新开始？

**方法**: 删除 JSON 文件
```bash
# Windows
del output\tenders_structured_*.json

# macOS/Linux
rm output/tenders_structured_*.json
```

---

## 进阶使用

### 不使用 LLM（仅保存原始数据）

```bash
python src/etl/extract_structured.py --limit 50 --no-llm
```

### 指定输出文件后缀

```bash
python src/etl/extract_structured.py --limit 50 --output-suffix test1
```

输出文件：`output/tenders_structured_test1.json`

### 查看日志文件

日志文件位置：`logs/extract_YYYYMMDD_HHMMSS.log`

```bash
# Windows
notepad logs\extract_20260331_143022.log

# macOS/Linux
cat logs/extract_20260331_143022.log
```

---

## 抽取字段说明

| 字段名 | 说明 | 示例 |
|--------|------|------|
| `tender_id` | 数据库 ID | 1 |
| `project_name` | 项目名称 | "2026 年通信设备采购项目" |
| `announce_type` | 公告类型 | "招标公告" |
| `buyer_name_std` | 采购人标准名称 | "中国移动通信集团广东有限公司" |
| `province` | 省份 | "广东省" |
| `city` | 城市 | "深圳市" |
| `budget_amount` | 预算金额（元） | 5000000 |
| `budget_text` | 预算原文 | "500 万元" |
| `deadline` | 截止时间 | "2026-04-15" |
| `product_keywords` | 产品关键词（数组） | ["通信设备", "路由器"] |
| `opportunity_score` | 机会评分（0-100） | 85 |

---

## 技术支持

遇到问题请查看：
- 完整文档：`docs/README.md`
- 日志文件：`logs/extract_*.log`
