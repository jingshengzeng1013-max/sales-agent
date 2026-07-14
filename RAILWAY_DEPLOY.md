# Railway 部署指南

> 将销售情报系统部署到 Railway，获得对外在线访问链接。

---

## 前置准备

### 1. 注册 Railway 账号
访问 [railway.app](https://railway.app)，使用 GitHub 账号登录。

### 2. 准备 GitHub 仓库
```bash
# 在项目根目录初始化 Git（如果还没有）
cd /home/sylincom/sales-agent
git init

# 删除备份文件（含真实数据，禁止上传！）
find . -name "*.bak" -delete

# 添加 .gitignore 确保不上传敏感文件
git add .
git commit -m "准备 Railway 部署"

# 推送到 GitHub
git remote add origin https://github.com/your-username/sales-agent.git
git push -u origin main
```

### 3. 获取 DeepSeek API Key
访问 [platform.deepseek.com](https://platform.deepseek.com)，注册并创建 API Key。

---

## 部署步骤

### Step 1：创建 Railway 项目

1. 登录 [Railway Dashboard](https://railway.app/dashboard)
2. 点击 **New Project** → **Deploy from GitHub repo**
3. 选择你的 `sales-agent` 仓库
4. Railway 会自动识别 `Dockerfile` 并开始构建

### Step 2：配置环境变量

在 Railway 项目的 **Variables** 标签中添加：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `LLM_PROVIDER` | `minimax` | 使用 MiniMax 作为 LLM |
| `MINIMAX_API_KEY` | `sk-cp-xxxxx` | 你的 MiniMax API Key（已内置到代码中，无需重复设置） |
| `PORT` | `8103` | 服务端口（Railway 会自动注入） |

**可选变量：**

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `EMBEDDING_BASE_URL` | `http://your-embedding-server/v1` | Embedding API 地址 |
| `EMBEDDING_MODEL` | `your-model-name` | Embedding 模型名 |

> ⚠️ 如果不配置 Embedding API，向量检索功能不可用，但 BM25 关键词检索仍可正常工作。

### Step 3：配置持久卷（Volume）

1. 进入 Railway 项目的 **Settings** 标签
2. 找到 **Volumes** → **Add Volume**
3. 设置挂载路径：`/app/data`
4. 这会持久化 SQLite 数据库和索引文件

> 首次部署时，`start_railway.sh` 会自动将镜像内置的数据文件复制到持久卷。

### Step 4：配置自定义域名（可选）

1. 进入 **Settings** → **Networking**
2. 点击 **Generate Domain** 生成 Railway 子域名（如 `sales-agent.up.railway.app`）
3. 或绑定自定义域名

### Step 5：验证部署

部署完成后，访问：

```
https://<your-railway-domain>/static/demo.html    ← 演示页面
https://<your-railway-domain>/                    ← API 状态
https://<your-railway-domain>/docs                ← API 文档
```

---

## 配置文件说明

### 已创建的部署文件

| 文件 | 用途 |
|------|------|
| `Dockerfile` | Docker 构建配置，Railway 自动识别 |
| `railway.toml` | Railway 平台配置（健康检查、卷挂载） |
| `.dockerignore` | 排除不需要的文件（备份、日志、附件等） |
| `start_railway.sh` | 启动脚本，处理首次数据初始化 |

### Dockerfile 说明

- 基础镜像：`python:3.10-slim`
- 精简依赖：排除了 `streamlit`、`scrapling`、`DrissionPage` 等不需要的包
- 数据种子：构建时将 `data/` 复制到 `data_seed/`，首次启动时复制到持久卷
- 健康检查：每 30s 检查 `/` 接口

---

## 费用估算

| 项目 | Railway 免费额度 | 实际用量 |
|------|------------------|----------|
| 构建时间 | 5 小时/月 | ~5 分钟/次 |
| 运行时间 | 500 小时/月（$5 信用额度） | 720 小时/月（全天运行） |
| 持久卷 | 1GB 免费 | ~100MB |
| **预估月费** | — | **~$5/月（约 ¥35）** |

> Railway 免费额度为每月 $5 信用额度，全天运行约消耗 $5-7/月。超出后按量计费。

---

## 常见问题

### Q1：部署后访问报 502 错误

**原因**：服务未启动或端口不匹配。

**解决**：
1. 检查 Railway Logs，确认无报错
2. 确认 `PORT` 环境变量与代码一致（默认 8103）
3. Railway 会自动注入 `PORT` 环境变量，无需手动设置

### Q2：AI 销售建议功能不可用

**原因**：未配置 LLM API Key。

**解决**：在 Railway Variables 中添加 `MINIMAX_API_KEY`。

### Q3：向量检索功能不可用

**原因**：未配置 Embedding API。

**解决**：
- 方案 A：配置 `EMBEDDING_BASE_URL` 指向可用的 Embedding 服务
- 方案 B：不配置，系统会自动降级为仅 BM25 关键词检索

### Q4：数据库数据丢失

**原因**：未配置持久卷。

**解决**：按 Step 3 配置 Volume 挂载到 `/app/data`。

### Q5：构建失败

**原因**：依赖安装失败。

**解决**：检查 Railway 构建日志，确认网络通畅。如 `faiss-cpu` 安装失败，可尝试在 Dockerfile 中添加编译依赖。

---

## 快速验证命令

部署成功后，可用以下命令验证：

```bash
# 替换 YOUR_DOMAIN 为实际 Railway 域名
export DOMAIN="https://your-app.up.railway.app"

# 1. 检查服务状态
curl $DOMAIN/

# 2. 检查产品列表
curl $DOMAIN/api/retrieval/product-options

# 3. 检查客户列表
curl "$DOMAIN/api/customers?page=1&size=5"

# 4. 检查筛选选项
curl $DOMAIN/api/retrieval/filter-options
```

---

## 本地 Docker 测试（可选）

推送到 Railway 前，可先在本地测试：

```bash
cd /home/sylincom/sales-agent

# 构建镜像
docker build -t sales-agent .

# 运行容器
docker run -p 8103:8103 \
  -e LLM_PROVIDER=minimax \
  -e MINIMAX_API_KEY=your_key \
  sales-agent

# 访问 http://localhost:8103/static/demo.html
```

---

*Last Updated: 2026-07-14*
