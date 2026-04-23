# RAG 字段补充与 Chunks 生成完成报告

## 执行时间
2026-04-01

## 完成的工作

### 1. 新增字段定义

根据 `MVP_RAG_实施方案.md` 和 `向量检索方案设计.md`，补充了以下字段以支持 RAG 检索：

| 字段 | 类型 | 用途 | chunk_type |
|------|------|------|------------|
| `contact_chunk` | TEXT | 整合三方联系人信息为连贯文本 | contact_chunk |
| `requirement_chunks` | TEXT (JSON) | 技术要求分块数组 | requirement_chunk |
| `content_summary` | TEXT | 公告内容摘要（已完成） | content_summary |

### 2. 修改的文件

#### src/etl/prompt_extract.md
- 增强 `attachment_summary` 定义
- 新增 `contact_chunk` 字段定义
- 新增 `requirement_chunks` 字段定义

#### src/models.py
- `LLM_EXTRACT_TEMPLATE` 新增字段
- `STRUCTURED_RESULT_SCHEMA` 新增验证

#### src/etl/schema.sql
- `tender_structured` 新增 `contact_chunk`、`requirement_chunks` 列

#### src/etl/extract_structured.py
- `import_to_db()` 支持新字段导入

### 3. 测试抽取结果

抽取 5 条数据测试新字段效果：
- **总消耗**: 22,672 tokens (约 0.033 元)
- **成功率**: 5/5 (100%)
- **contact_chunk**: 5 条全部正确生成
- **requirement_chunks**: 平均每条 2-3 个分块

**示例数据** (tender_id=55):
```json
{
  "contact_chunk": "采购单位：周老师 025-52091654；张老师 025-83790587,52091170；无代理机构；项目联系人：陈工 025-83795552",
  "requirement_chunks": [
    {
      "type": "technical_params",
      "text": "需要采用先进的晶圆级扇出封装工艺完成 1 批定制化异质异构射频芯片封装设计..."
    },
    {
      "type": "qualification_requirements",
      "text": "满足《中华人民共和国政府采购法》第二十二条规定..."
    },
    {
      "type": "service_requirements",
      "text": "合同履行期限详见采购文件。本项目采用电子标..."
    }
  ]
}
```

### 4. Chunks 生成结果

执行 `generate_chunks.py` 生成 `tender_chunks` 表数据：

| tender_id | title | content_summary | contact_chunk | requirement_chunk | 合计 |
|-----------|-------|-----------------|---------------|-------------------|------|
| 54 | 1 | 1 | 1 | 1 | 4 |
| 55 | 1 | 1 | 1 | 3 | 6 |
| 56 | 1 | 1 | 1 | 3 | 6 |
| 57 | 1 | 1 | 1 | 3 | 6 |
| 58 | 1 | 1 | 1 | 2 | 5 |
| **合计** | 5 | 5 | 5 | 12 | **27** |

### 5. Chunk 类型分布

```
title:             5 条 (18.5%)
content_summary:   5 条 (18.5%)
contact_chunk:     5 条 (18.5%)
requirement_chunk: 12 条 (44.4%)
```

## 数据库状态

### tender_structured 表字段
```sql
-- 基础字段
announce_type, buyer_name_std, province, city,
budget_raw, budget_amount, budget_unit,
product_keywords, application_scenario,
technical_requirements_summary,
-- 三方联系人
buyer_contacts, agency_contacts, project_contacts,
-- RAG 检索块
content_summary, contact_chunk, requirement_chunks,
-- 其他
opportunity_score, opportunity_reason, next_action,
attachment_summary, extracted_json, llm_model, llm_version
```

### tender_chunks 表结构
```sql
chunk_id INTEGER PRIMARY KEY
tender_id INTEGER
chunk_type TEXT           -- title/content_summary/contact_chunk/requirement_chunk/attachment_summary
chunk_text TEXT NOT NULL
chunk_order INTEGER
metadata_json TEXT        -- 元数据（JSON）
embedding_id TEXT         -- 向量 ID（待填充）
created_at TIMESTAMP
```

## 下一步工作

### 1. 向量嵌入生成 (待实施)
```python
# 使用 bge-m3 模型生成向量
from FlagEmbedding import BGEM3FlagModel

model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)
# 为每个 chunk_text 生成 embedding
```

### 2. 混合检索实现 (待实施)
- 结构化过滤：SQL WHERE (province, budget, announce_type)
- 向量相似度：cosine similarity
- 结果排序：similarity + opportunity_score

### 3. Streamlit 前端 (待实施)
- 项目列表页（支持筛选）
- 项目详情页（结构化展示）
- 智能问答页（RAG）

## 文件清单

| 文件 | 说明 |
|------|------|
| `src/etl/prompt_extract.md` | Prompt 定义（已更新） |
| `src/models.py` | 数据模型（已更新） |
| `src/etl/schema.sql` | 数据库 schema（已更新） |
| `src/etl/extract_structured.py` | LLM 抽取脚本（已更新） |
| `src/etl/generate_chunks.py` | Chunks 生成脚本（新增） |
| `docs/RAG_字段补充说明.md` | 字段说明文档（新增） |
| `output/tenders_structured_rag_test.json` | 测试数据 |

## 命令参考

```bash
# 1. LLM 结构化抽取
python src/etl/extract_structured.py --limit 50 --output-suffix test

# 2. 导入到数据库
python src/etl/extract_structured.py --import-only --file output/tenders_structured_test.json

# 3. 生成 chunks（新）
python src/etl/generate_chunks.py --all --replace

# 4. 生成指定 tender 的 chunks
python src/etl/generate_chunks.py --tender-id 55
```

## 成本估算

按当前 5 条数据推算：
- 每条平均 tokens: ~4,500
- 每条平均成本：~0.0066 元
- 1000 条数据成本：~1.32 元
- 10000 条数据成本：~13.2 元

使用 DeepSeek 模型成本极低，适合批量处理历史数据。
