# Web 前端使用指南

## 快速启动

### Windows 一键启动

```bash
run.bat
```

### 手动启动

```bash
# 1. 启动 FastAPI 后端
cd src/api
python main.py

# 2. 启动 Streamlit 前端（新终端）
cd src
streamlit run main_app.py --server.headless true --server.port 8501
```

## 访问地址

| 服务 | 地址 |
|------|------|
| Web 界面 | http://localhost:8501 |
| API 文档 | http://localhost:8000/docs |

## 功能模块

### 1. 🏠 首页搜索

支持关键词搜索和高级筛选：

- 关键词：项目名称、采购单位、内容摘要
- 公告类型：招标公告、中标公告、废标公告等
- 省份筛选
- 机会评分：0-100 分
- 日期范围

### 2. 📄 项目详情

点击列表中的"查看详情"进入，显示：

- 基本信息（发布日期、公告类型、机会评分）
- 采购信息（采购单位、代理机构、预算）
- 联系人信息
- 产品关键词
- 技术要求摘要
- 公告原文
- 附件链接

### 3. 📈 统计分析

- 关键指标卡片
- 地区分布条形图
- 公告类型分布图

### 4. 💬 智能问答

自然语言提问，智能检索相关项目。

## 系统架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Streamlit     │────▶│   FastAPI       │────▶│   SQLite        │
│   前端界面      │     │   后端 API      │     │   数据库        │
│   (8501 端口)    │     │   (8000 端口)    │     │   ccgp_data.db  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## API 接口速查

```bash
# 搜索项目
POST /api/search
{
    "keyword": "通信",
    "min_score": 80,
    "page": 1,
    "page_size": 20
}

# 获取详情
GET /api/tenders/{id}

# 统计概览
GET /api/stats/overview

# 地区分布
GET /api/stats/by_province
```

## 依赖安装

```bash
pip install fastapi uvicorn pydantic streamlit pandas
```
