# 销售情报系统 FastAPI 服务部署与运维指南

## 概述

本目录包含销售情报系统 FastAPI 服务的持久化启动脚本，当前会同时管理 Web 端和手机端两个服务：

| 方式 | 文件 | 适用场景 |
|------|------|----------|
| Shell 脚本 | `start_server.sh` | 日常开发、临时部署、快速启停，可同时启动 Web/手机端 |
| systemd 服务 | `sales-api.service` | 生产环境、开机自启、崩溃自动恢复 |

Web 端服务入口：`webapp.server_fastapi:app`，默认监听：`0.0.0.0:8103`  
手机端服务入口：`mobileapp.server_mobile:app`，默认监听：`0.0.0.0:8104`  
Python 环境：`/home/sylincom/miniconda3`

---

## 一、Shell 脚本方式（start_server.sh）

### 1.1 可用命令

```bash
cd /home/sylincom/sales-agent/get_data/webapp

./start_server.sh start    # 启动服务
./start_server.sh stop     # 停止服务
./start_server.sh restart  # 重启服务
./start_server.sh status   # 查看运行状态
./start_server.sh log      # 实时查看日志（tail -f）

# 单独操作某个服务
./start_server.sh start web
./start_server.sh start mobile
./start_server.sh status mobile
./start_server.sh log mobile
```

### 1.2 启动服务

```bash
$ ./start_server.sh start
[INFO] 正在启动 Web 端服务...
[INFO] Python:  /home/sylincom/miniconda3/bin/python3
[INFO] Uvicorn: /home/sylincom/miniconda3/bin/uvicorn
[INFO] 监听:    0.0.0.0:8103
[INFO] 日志:    /home/sylincom/sales-agent/get_data/logs/api_server/server_fastapi_stdout.log
[OK] Web 端服务 启动成功 (PID: 12345)
[OK] 访问地址: http://127.0.0.1:8103/static/demo.html
[OK] API 文档:  http://127.0.0.1:8103/docs
[INFO] 正在启动 手机端服务...
[INFO] 监听:    0.0.0.0:8104
[INFO] 日志:    /home/sylincom/sales-agent/get_data/logs/api_server/server_mobile_stdout.log
[OK] 手机端服务 启动成功 (PID: 12346)
[OK] 访问地址: http://127.0.0.1:8104/
```

### 1.3 停止服务

```bash
$ ./start_server.sh stop
[INFO] 正在停止服务 (PID: 12345)...
[OK] 服务已停止
```

停止时发送 `SIGTERM` 信号，等待最多 30 秒优雅退出。超时未退出则强制 `SIGKILL`。

### 1.4 查看状态

```bash
$ ./start_server.sh status
[OK] 服务运行中 (PID: 12345)
     监听: 0.0.0.0:8103
     日志: .../server_fastapi_stdout.log
     状态: 正常响应
```

状态检测逻辑：
1. 检查 PID 文件是否存在
2. 检查进程是否存活（`kill -0`）
3. 尝试 HTTP 请求确认端口可达

### 1.5 关键文件路径

| 文件 | 路径 | 说明 |
|------|------|------|
| PID 文件 | `logs/api_server/server_fastapi.pid` | 记录主进程 PID |
| 运行日志 | `logs/api_server/server_fastapi_stdout.log` | uvicorn 标准输出 |
| 手机端 PID 文件 | `logs/api_server/server_mobile.pid` | 记录手机端主进程 PID |
| 手机端运行日志 | `logs/api_server/server_mobile_stdout.log` | 手机端 uvicorn 标准输出 |
| 应用日志 | `logs/api_server/api_server_*.log` | 应用内 logging 输出 |

### 1.6 自定义配置

编辑 `start_server.sh` 顶部的配置区：

```bash
PROJECT_DIR="/home/sylincom/sales-agent/get_data"  # 项目根目录
WEB_APP_ENTRY="webapp.server_fastapi:app"           # Web 端应用入口
MOBILE_APP_ENTRY="mobileapp.server_mobile:app"      # 手机端应用入口
HOST="0.0.0.0"                                       # 监听地址
WEB_PORT=8103                                        # Web 端监听端口
MOBILE_PORT=8104                                     # 手机端监听端口
WORKERS=1                                             # Worker 进程数
```

> **注意**：修改 `WEB_APP_ENTRY` 或 `MOBILE_APP_ENTRY` 需确保 Python 模块路径正确；增加 `WORKERS` 时注意内存消耗。

---

## 二、运行环境变量

服务会从环境变量读取模型、Embedding、代理等配置，避免把密钥写入源码：

```bash
export SALES_AGENT_BASE_DIR=/home/sylincom/sales-agent/get_data
export LOCAL_LLM_BASE_URL=http://<your-llm-host>/v1
export LOCAL_LLM_MODEL=<your-model>
export EMBEDDING_BASE_URL=http://<your-embedding-host>/v1
export EMBEDDING_MODEL=<your-embedding-model>
export DEEPSEEK_API_KEY=<optional-deepseek-key>
```

如需启用代理爬虫，再配置：

```bash
export CRAWLER_USE_PROXY=true
export QG_PROXY_API_URL=<proxy-api-url>
export QG_PROXY_USER=<proxy-user>
export QG_PROXY_PASSWORD=<proxy-password>
```

使用 systemd 时，可在 `sales-api.service` 的 `[Service]` 段添加 `Environment=` 行，或改用 `EnvironmentFile=/path/to/sales-agent.env`。

---

## 三、systemd 服务方式（sales-api.service）

### 3.1 安装服务

```bash
# 1. 复制服务文件到 systemd 目录
sudo cp /home/sylincom/sales-agent/get_data/webapp/sales-api.service /etc/systemd/system/

# 2. 重载 systemd 配置
sudo systemctl daemon-reload
```

### 3.2 启动与停止

```bash
# 启动服务
sudo systemctl start sales-api

# 停止服务
sudo systemctl stop sales-api

# 重启服务
sudo systemctl restart sales-api
```

### 3.3 开机自启

```bash
# 设置开机自动启动
sudo systemctl enable sales-api

# 取消开机自启
sudo systemctl disable sales-api
```

### 3.4 查看状态与日志

```bash
# 查看服务状态
sudo systemctl status sales-api

# 查看实时日志（journalctl）
journalctl -u sales-api -f

# 查看最近 100 行日志
journalctl -u sales-api -n 100

# 查看指定时间段的日志
journalctl -u sales-api --since "2026-04-28 10:00" --until "2026-04-28 18:00"
```

### 3.5 服务配置说明

```ini
[Service]
Restart=always      # 进程异常退出后自动重启
RestartSec=5        # 重启前等待 5 秒
TimeoutStartSec=120 # 启动超时 120 秒（首次加载模型可能较慢）
TimeoutStopSec=30   # 停止超时 30 秒
LimitNOFILE=65536   # 文件描述符上限
```

日志输出位置：
- **标准输出** → `logs/api_server/server_fastapi_stdout.log`
- **标准错误** → `logs/api_server/server_fastapi_stderr.log`

### 3.6 修改服务配置

编辑 `/etc/systemd/system/sales-api.service` 后需执行：

```bash
sudo systemctl daemon-reload
sudo systemctl restart sales-api
```

---

## 四、访问地址

服务启动后可通过以下地址访问：

| 用途 | 地址 |
|------|------|
| 前端 Demo 页面 | http://127.0.0.1:8103/static/demo.html |
| 手机端页面 | http://127.0.0.1:8104/ |
| API 根路径 | http://127.0.0.1:8103/ |
| Swagger 文档 | http://127.0.0.1:8103/docs |
| Redoc 文档 | http://127.0.0.1:8103/redoc |

局域网访问请将 `127.0.0.1` 替换为服务器内网 IP。

---

## 五、常见问题

### Q1: 启动失败，提示端口被占用

```bash
# 查找占用端口的进程
lsof -i :8103
# 或
ss -tlnp | grep 8103

# 终止占用进程
kill -9 <PID>
```

### Q2: 启动失败，提示 ModuleNotFoundError

确认当前 Python 环境中已安装所需依赖：

```bash
/home/sylincom/miniconda3/bin/pip install fastapi uvicorn pydantic numpy
```

### Q3: 服务启动后无法访问

1. 检查防火墙是否放行 8103 端口：
   ```bash
   sudo firewall-cmd --list-ports
   sudo firewall-cmd --add-port=8103/tcp --permanent
   sudo firewall-cmd --reload
   ```
2. 检查服务是否正常响应：
   ```bash
   curl http://127.0.0.1:8103/
   ```

### Q4: Shell 脚本提示服务已在运行但实际无法访问

PID 文件可能残留，手动清理后重启：

```bash
rm -f /home/sylincom/sales-agent/get_data/logs/api_server/server_fastapi.pid
./start_server.sh start
```

### Q5: systemd 服务启动超时

首次启动时加载检索器和数据可能较慢，适当增大 `TimeoutStartSec`：

```ini
TimeoutStartSec=300
```

---

## 五、两种方式对比

| 特性 | Shell 脚本 | systemd 服务 |
|------|-----------|-------------|
| 安装复杂度 | 无需安装 | 需 sudo 部署 |
| 崩溃自动恢复 | 不支持 | 支持（Restart=always） |
| 开机自启 | 需手动配置 crontab | 原生支持 |
| 日志管理 | 写入文件 | 文件 + journalctl |
| 权限管理 | 当前用户 | 可指定用户/组 |
| 推荐场景 | 开发/测试 | 生产环境 |

> **生产环境建议**：使用 systemd 服务方式，确保服务高可用。
