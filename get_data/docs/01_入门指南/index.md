# 政府采购招投标数据系统 - 文档索引

## 新手入门

| 文档 | 说明 | 适合人群 |
|------|------|----------|
| [README.md](README.md) | **完整使用指南**，快速开始 | 新用户必读 |
| [LLM 抽取新手指南.md](LLM%20抽取新手指南.md) | LLM 结构化抽取详细教程 | 需要使用 LLM 功能 |
| [Web 前端使用指南.md](Web%20前端使用指南.md) | Web 界面使用教程 | 使用 Web 界面 |
| [LLM API 配置指南.md](LLM%20API%20配置指南.md) | DeepSeek/通义千问配置 | 配置 LLM API |

## 快速操作

### 手动执行完整流程

```bash
# 1. 重置数据库
python src/utils/reset_db.py

# 2. 爬取列表
python src/crawler/ccgp_crawler.py

# 3. 爬取详情
python src/crawler/crawl_detail.py

# 4. LLM 抽取
python src/etl/extract_structured.py --all
python src/etl/import_structured_db.py

# 5. 项目聚合
python src/etl/aggregate_projects.py

# 6. 生成客户画像
python src/analysis/generate_customer_profiles.py

# 7. 向量化和索引
python src/vectorization/vectorize_data.py --type tender
python src/vectorization/build_index.py --type tender

# 8. 启动服务
python webapp/server_fastapi.py
# 访问 http://127.0.0.1:8103/static/demo.html
```

## 文档目录

### 01 入门指南
- [README.md](README.md) - 完整使用指南（新用户必读）
- [LLM 抽取新手指南.md](LLM%20抽取新手指南.md) - LLM 结构化抽取教程
- [LLM API 配置指南.md](LLM%20API%20配置指南.md) - API 配置说明
- [Web 前端使用指南.md](Web%20前端使用指南.md) - Web 界面教程

### 02 RAG 方案
- [MVP RAG 实施方案](../02_RAG%20方案/MVP_RAG_实施方案.md) - RAG 系统设计
- [向量检索方案设计](../02_RAG%20方案/向量检索方案设计.md) - FAISS + BM25 检索
- [DeepSeek 结构化抽取报告](../02_RAG%20方案/DeepSeek%20结构化抽取报告.md) - 抽取效果评估

### 03 架构设计
- [项目架构说明](../03_架构设计/项目架构说明.md) - 系统架构
- [项目详细流程](../03_架构设计/项目详细流程.md) - 数据处理流程

### 04 技术文档
- [附件下载与解析流程](../04_技术文档/附件下载与解析流程.md) - 附件处理
- [阿里云 LLM 配置](../04_技术文档/ALIYUN_LLM_SETUP.md) - 阿里云配置

### 05 部署运维
- [部署指南](../05_部署运维/部署指南.md) - 生产环境部署
- [运维手册](../05_部署运维/运维手册.md) - 日常运维
- [常见问题排查](../05_部署运维/常见问题排查.md) - 问题诊断

### 06 开发指南
- [项目结构说明](../06_开发指南/项目结构说明.md) - 代码结构
- [代码规范](../06_开发指南/代码规范.md) - 开发规范
- [模块开发教程](../06_开发指南/模块开发教程.md) - 新模块开发

## 常用命令速查

### 数据爬取
```bash
python src/crawler/ccgp_crawler.py           # 爬取列表
python src/crawler/crawl_detail.py           # 爬取详情
python src/crawler/crawl_detail.py repair-att-url  # 修复附件
```

### LLM 抽取
```bash
python src/etl/extract_structured.py --all    # 全量抽取
python src/etl/extract_structured.py --limit 50 # 测试 50 条
python src/etl/import_structured_db.py         # 导入数据库
```

### 索引构建
```bash
python src/vectorization/vectorize_data.py --type tender  # 向量化
python src/vectorization/build_index.py --type tender      # 构建索引
```

### 工具命令
```bash
python src/utils/reset_db.py                  # 重置数据库
python src/utils/manage_logs.py list --days 7  # 查看日志
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 爬虫 | curl_cffi (绕过 TLS 指纹) |
| 数据库 | SQLite |
| AI 抽取 | DeepSeek / 通义千问 / 本地 LLM |
| 向量检索 | FAISS |
| 关键词检索 | BM25 + jieba |
| 后端 | FastAPI |
| 前端 | HTML5 + CSS + Vanilla JS |

## 相关链接

- 中国政府采购网：https://www.ccgp.gov.cn/
- DeepSeek 平台：https://platform.deepseek.com/
- 阿里云 DashScope: https://dashscope.console.aliyun.com/
