# DeepSeek 结构化抽取完成报告

## 执行时间
2026-04-01 16:17 - 16:51（约 34 分钟）

## 执行结果

### 数据抽取统计

| 指标 | 数值 |
|------|------|
| 处理记录数 | 85 条 |
| 成功数量 | 85/85 (100%) |
| 失败数量 | 0 条 |
| 跳过数量 | 0 条 |

### Token 消耗统计

| 项目 | 数值 |
|------|------|
| 调用次数 | 85 次 |
| 输入 Token | 295,962 |
| 输出 Token | 57,701 |
| 总 Token | 353,663 |
| 估算成本 | ¥0.50 元 (范围：¥0.23-0.77) |
| 单条平均成本 | ¥0.0059 元 |

### 模型信息

- **模型**: DeepSeek-V3 (`deepseek-chat`)
- **Base URL**: https://api.deepseek.com
- **Temperature**: 0.1
- **Max Tokens**: 8000

## 抽取字段

LLM 从招标公告中抽取了以下结构化字段：

### 基础信息
- `announce_type` - 公告类型（招标公告/中标公告/单一来源/竞争性磋商等）
- `buyer_name_std` - 采购单位标准化名称
- `agency_name_std` - 代理机构标准化名称
- `province`, `city` - 所在地区

### 预算信息
- `budget_raw` - 原始预算文本
- `budget_amount` - 预算金额（数值）
- `budget_unit` - 预算单位（元/万元等）

### 技术信息
- `product_keywords` - 产品关键词（JSON 数组）
- `application_scenario` - 应用场景描述
- `technical_requirements_summary` - 技术要求摘要

### 联系人信息
- `buyer_contacts` - 采购单位联系人（JSON 数组）
- `agency_contacts` - 代理机构联系人（JSON 数组）
- `project_contacts` - 项目联系人（JSON 数组）
- `contact_person` - 联系人姓名
- `contact_phone` - 联系电话
- `contact_chunk` - 整合后的联系人信息文本

### 技术要求分块
- `requirement_chunks` - 技术要求分块数组，包含：
  - `technical_params` - 技术参数
  - `qualification_requirements` - 资格要求
  - `service_requirements` - 服务要求

### 机会评估
- `opportunity_score` - 机会评分（0-100）
- `opportunity_reason` - 评分理由
- `next_action` - 建议下一步行动

### 元数据
- `extracted_json` - 完整抽取结果（JSON）
- `llm_model` - 使用的模型
- `llm_version` - 模型版本

## 数据库导入

抽取的数据已导入到 `tender_structured` 表：

```sql
-- 数据库位置
D:/get_data/data/ccgp_data.db

-- 表结构
CREATE TABLE tender_structured (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id INTEGER NOT NULL,
    -- 26 个结构化字段...
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 导入结果

| 操作 | 数量 |
|------|------|
| 插入记录 | 80 条 |
| 更新记录 | 5 条 |
| 跳过记录 | 0 条 |

## 数据示例

### 记录示例 (tender_id=54)

```json
{
  "tender_id": 54,
  "announce_type": "单一来源",
  "buyer_name_std": "zycgr21071303",
  "province": "广东省",
  "budget_amount": null,
  "product_keywords": ["光模块", "光器件"],
  "opportunity_score": 80,
  "opportunity_reason": "单一来源采购，目标明确，竞争程度低",
  "next_action": "联系采购单位获取采购文件",
  "contact_chunk": "采购单位：王老师 020-xxxxxxx；无代理机构；项目联系人：李工 020-xxxxxxx"
}
```

### 公告类型分布

| 类型 | 数量 | 占比 |
|------|------|------|
| 招标公告 | ~30 | ~35% |
| 中标公告 | ~25 | ~30% |
| 单一来源 | ~15 | ~18% |
| 竞争性磋商/谈判 | ~15 | ~17% |

### 地区分布

| 省份 | 数量 | 占比 |
|------|------|------|
| 广东省 | ~25 | ~29% |
| 湖南省 | ~20 | ~24% |
| 江苏省 | ~15 | ~18% |
| 其他 | ~25 | ~29% |

## 输出文件

| 文件 | 位置 | 大小 |
|------|------|------|
| 结构化数据 | `output/tenders_structured.json` | ~500KB |
| 日志文件 | `logs/extract_20260401_161732.log` | ~200KB |

## 命令参考

### 完整流程

```bash
# 1. 结构化抽取（所有数据）
python src/etl/extract_structured.py --all --model deepseek-chat

# 2. 导入数据库
python src/etl/import_structured_db.py --file output/tenders_structured.json

# 3. 查询结果
python src/etl/query_tenders.py --score 80
```

### 测试模式

```bash
# 仅测试第一条
python src/etl/extract_structured.py --test-first

# 抽取前 50 条
python src/etl/extract_structured.py --limit 50

# 使用不同模型
python src/etl/extract_structured.py --model qwen-max --limit 10
```

## 成本分析

### 当前执行

- **单位成本**: ¥0.0059 / 条
- **总成本**: ¥0.50 元（85 条）

### 推算成本

| 数据量 | 预估成本 |
|--------|----------|
| 100 条 | ¥0.60 元 |
| 1,000 条 | ¥5.90 元 |
| 10,000 条 | ¥59.00 元 |
| 100,000 条 | ¥590.00 元 |

### 优化建议

1. **批量处理**: 使用 `--all` 参数批量处理，减少 API 调用开销
2. **缓存利用**: DeepSeek 支持缓存命中，重复内容成本可降低 90%
3. **模型选择**: 对于简单字段抽取，`deepseek-chat` 性价比最高

## 下一步工作

1. **向量嵌入生成**: 为 `contact_chunk` 和 `requirement_chunks` 生成向量
2. **混合检索实现**: 结构化过滤 + 向量相似度检索
3. **Streamlit 前端**: 开发项目列表和详情页

## 相关文件

| 文件 | 说明 |
|------|------|
| `src/etl/extract_structured.py` | LLM 抽取脚本 |
| `src/etl/import_structured_db.py` | 数据库导入脚本 |
| `src/etl/prompt_extract.md` | Prompt 模板 |
| `output/tenders_structured.json` | 抽取结果 |
