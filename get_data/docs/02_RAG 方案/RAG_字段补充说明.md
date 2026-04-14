# RAG 字段补充说明

## 背景

根据 `MVP_RAG_实施方案.md` 和 `向量检索方案设计.md`，当前 LLM 抽取的字段需要补充以支持 RAG 检索功能。

## tender_chunks 表设计的 chunk_type

| chunk_type | 说明 | 对应字段 |
|------------|------|----------|
| `title` | 项目标题 | `project_name` |
| `content_summary` | 公告内容摘要 | `content_summary` |
| `requirement_chunk` | 技术要求分块 | `requirement_chunks` |
| `contact_chunk` | 联系方式块 | `contact_chunk` |
| `attachment_summary` | 附件摘要 | `attachment_summary` |

## 本次补充的字段

### 1. contact_chunk（联系方式块）

**用途**：将三方联系人信息整合为一段连贯文本，用于向量检索联系人信息。

**格式**：
```
采购单位：陈老师 0755-85902242；代理机构：中国远东国际招标有限公司 0755-83004312；项目联系人：陈工 025-83795552
```

**Prompt 更新**：
```markdown
### contact_chunk (联系方式块)
将三方联系人信息整合为一段连贯文本，用于向量检索。
格式：采购单位 + 代理机构 + 项目联系人的完整联系信息

示例：
- "采购单位：陈老师 0755-85902242；代理机构：李经理 010-12345678；项目联系人：陈工 025-83795552"
- "采购单位：长春职业技术大学 84603018；无代理机构；项目联系人：张老师 010-12345678"

注意：
- 如果某方联系人缺失，注明"无"
- 确保电话准确完整
- 此字段将用于销售快速定位联系人信息
```

### 2. requirement_chunks（技术要求分块数组）

**用途**：将技术要求按类型拆分为多个小块，用于细粒度的技术要求向量检索。

**格式**：
```json
[
  {"type": "technical_params", "text": "耦合精度≤0.5μm，支持多种芯片尺寸"},
  {"type": "service_requirements", "text": "质保期 3 年，2 小时内响应"},
  {"type": "qualification_requirements", "text": "供应商需具备 ISO9001 认证"}
]
```

**type 可选值**：
- `technical_params`：技术参数（性能指标、精度要求等）
- `service_requirements`：服务要求（售后、培训、交货期等）
- `qualification_requirements`：资格要求（资质证书、业绩要求等）
- `other`：其他要求

**Prompt 更新**：
```markdown
### requirement_chunks (技术要求分块数组)
将技术要求按类型拆分为多个小块，每块包含特定类型的要求。
数组格式，每个元素包含 type 和 text 字段：

type 可选值：
- technical_params：技术参数
- service_requirements：服务要求
- qualification_requirements：资格要求
- other：其他要求

注意：
- 根据公告内容实际包含的类型来填写
- 每条 text 控制在 50-200 字
- 此字段用于细粒度的技术要求检索
```

### 3. attachment_summary（附件摘要增强）

**原定义**：
```markdown
如有附件，简述附件内容（文件名 + 类型）。
```

**新定义**：
```markdown
### attachment_summary (附件摘要)
如有附件，需要详细说明：
- 文件名 + 文件类型（招标文件/技术规格书/图纸/工程量清单等）
- 核心内容概述（50-100 字）

示例：
- "招标文件.pdf：包含投标须知、合同条款、评分标准；技术规格书.pdf：详细技术参数要求"
- "无附件"

注意：附件摘要将用于向量检索，需要包含关键信息如评分标准、技术参数、资质要求等。
```

## 修改的文件

### 1. src/etl/prompt_extract.md
- 增强了 `attachment_summary` 的定义
- 新增了 `contact_chunk` 字段定义
- 新增了 `requirement_chunks` 字段定义

### 2. src/models.py
- `LLM_EXTRACT_TEMPLATE` 新增字段：
  - `"contact_chunk": None`
  - `"requirement_chunks": []`
- `STRUCTURED_RESULT_SCHEMA` 新增字段验证

### 3. src/etl/schema.sql
- `tender_structured` 表新增列：
  - `contact_chunk TEXT`
  - `requirement_chunks TEXT`

### 4. src/etl/extract_structured.py
- `import_to_db()` 函数中：
  - CREATE TABLE 语句新增两列
  - UPDATE 语句新增两个字段
  - INSERT 语句新增两列和占位符

## 下一步工作

### 1. 重新抽取数据测试新字段
```bash
python src/etl/extract_structured.py --limit 5 --output-suffix rag_test
```

### 2. 生成 tender_chunks 表数据
创建脚本将结构化字段转换为 RAG chunk：
- title chunk = project_name
- content_summary chunk = content_summary
- contact chunk = contact_chunk
- requirement chunks = requirement_chunks 数组展开
- attachment chunk = attachment_summary

### 3. 向量 embedding 生成
使用嵌入模型（如 bge-m3）对所有 chunk 进行向量化。

### 4. 实现混合检索
- 结构化过滤（SQL WHERE）
- 向量相似度检索
- 结果排序

## 字段映射关系

| LLM 抽取字段 | tender_chunks.chunk_type | 向量化 | 用途 |
|-------------|--------------------------|--------|------|
| project_name | title | 是 | 项目标题检索 |
| content_summary | content_summary | 是 | 公告摘要检索 |
| contact_chunk | contact_chunk | 是 | 联系人检索 |
| requirement_chunks[] | requirement_chunk | 是 | 技术要求检索 |
| attachment_summary | attachment_summary | 是 | 附件内容检索 |
| province/city/budget | - | 否 | SQL 过滤 |
| announce_type | - | 否 | SQL 过滤 |
| product_keywords | - | 否 | SQL 过滤/标签 |

## 数据库更新语句（如需要）

如果数据库中已有 `tender_structured` 表，需要执行以下 SQL 添加新列：

```sql
ALTER TABLE tender_structured ADD COLUMN contact_chunk TEXT;
ALTER TABLE tender_structured ADD COLUMN requirement_chunks TEXT;
```
