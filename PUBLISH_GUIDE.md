# 销售情报系统 - 对外发布指南

> 本文档说明如何将销售情报系统部署为对外可访问的在线演示版本。

---

## 一、数据脱敏说明

### 已脱敏的数据

| 数据文件 | 脱敏内容 | 方式 |
|----------|----------|------|
| `docs/商机列表20260422113444.xlsx` | 公司名、人名、电话、信用代码 | 替换为虚构数据 |
| `docs/线索列表20260422113326.xlsx` | 公司名、人名、电话、信用代码 | 替换为虚构数据 |
| `get_data/data/output/customer/customer_profiles.jsonl` | CRM 相关客户信息 | 基于脱敏 Excel 重新生成 |
| `get_data/data/product.jsonl` | 公司名"中科晶上" | 替换为"星通科技" |
| `get_data/data/embedding/product_embedded.jsonl` | 同上 | 同上 |

### 脱敏策略

- **公司名** → 虚构公司名（保留行业特征，如"星途新能源汽车有限公司"）
- **人名** → 随机常见姓氏 + 名字用字组合
- **电话** → 138/139 等前缀的假号码
- **统一信用代码** → 格式合法但虚构的 18 位代码
- **金额/日期/状态** → 保留原始分布特征，确保演示效果

### 未脱敏的数据（公开信息）

- 政府采购招标公告数据（来源：中国政府采购网，公开信息）
- 招标公告中的联系人姓名和电话（已在公告中公开）

### 原始数据备份

原始 CRM 文件已备份为 `.xlsx.bak`，原始画像备份为 `.jsonl.bak`，原始产品库备份为 `.jsonl.bak`。**对外发布前请删除所有 `.bak` 文件**：

```bash
find /home/sylincom/sales-agent -name "*.bak" -delete
```

---

## 二、对外发布所需平台资源

### 方案 A：云服务器部署（推荐）

**所需资源：**

| 资源 | 规格 | 用途 | 预估费用 |
|------|------|------|----------|
| 云服务器 | 2核4G | 运行 FastAPI 后端 + SQLite | 约 50-100 元/月 |
| 公网 IP | 1 个 | 外部访问入口 | 通常随服务器提供 |
| 域名（可选） | 1 个 | 提供易记的访问地址 | 约 50 元/年 |
| SSL 证书（可选） | 1 个 | HTTPS 加密 | 免费（Let's Encrypt） |

**推荐云平台：**
- 腾讯云轻量应用服务器（性价比高）
- 阿里云 ECS
- 华为云耀云服务器

**部署步骤：**

1. 购买云服务器，选择 Ubuntu 22.04 / CentOS 8 系统
2. 安装 Python 3.10+ 和依赖
3. 上传项目代码
4. 运行部署脚本：`./deploy_public.sh`
5. 配置安全组/防火墙，开放端口 8103
6. （可选）配置 Nginx 反向代理 + 域名 + HTTPS

### 方案 B：Serverless 部署（免运维）

**所需资源：**

| 资源 | 用途 |
|------|------|
| EdgeOne Pages / Vercel | 前端静态页面托管 |
| 云函数 (SCF / Lambda) | 后端 API 托管 |
| 云数据库 | SQLite 需替换为云数据库 |

> ⚠️ Serverless 方案需要较多改造（SQLite → PostgreSQL，FastAPI 适配云函数），不推荐用于快速演示。

### 方案 C：内网穿透（临时演示）

**所需资源：**

| 资源 | 用途 |
|------|------|
| frp / ngrok | 内网穿透工具 |
| 本地服务器 | 运行项目 |

> 适合短期演示，不适合长期对外访问。

---

## 三、部署操作步骤（方案 A 详细版）

### 1. 准备服务器

```bash
# SSH 登录服务器
ssh user@your-server-ip

# 安装 Python 3.10+
sudo apt update && sudo apt install -y python3 python3-pip

# 安装 Git
sudo apt install -y git
```

### 2. 上传项目

```bash
# 方式一：Git 克隆（如果代码在仓库中）
git clone <your-repo-url> /opt/sales-agent

# 方式二：SCP 上传
scp -r sales-agent/ user@your-server-ip:/opt/sales-agent
```

### 3. 安装依赖

```bash
cd /opt/sales-agent/get_data
pip3 install -r requirements.txt
```

### 4. 配置 LLM API（可选）

```bash
# 使用 DeepSeek API（推荐，成本低）
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=your_api_key

# 或使用本地 LLM
export LLM_PROVIDER=local
export LOCAL_LLM_BASE_URL=http://your-llm-server:8001/v1
```

### 5. 启动服务

```bash
cd /opt/sales-agent
./deploy_public.sh
```

### 6. 配置 Nginx 反向代理（推荐）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8103;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 7. 配置 HTTPS（推荐）

```bash
# 安装 Certbot
sudo apt install -y certbot python3-certbot-nginx

# 申请免费 SSL 证书
sudo certbot --nginx -d your-domain.com
```

### 8. 设置开机自启（推荐）

```bash
# 使用 systemd
sudo cp /opt/sales-agent/get_data/webapp/sales-api.service /etc/systemd/system/
# 编辑 service 文件，修改路径为实际路径
sudo vim /etc/systemd/system/sales-api.service
sudo systemctl daemon-reload
sudo systemctl enable sales-api
sudo systemctl start sales-api
```

---

## 四、对外访问地址

部署完成后，提供以下链接给外部用户：

| 链接 | 用途 |
|------|------|
| `http://your-domain.com/static/demo.html` | 演示版首页（推荐） |
| `http://your-domain.com/static/index.html` | 完整版首页 |
| `http://your-domain.com/docs` | API 文档（Swagger） |
| `http://your-domain.com/` | API 状态检查 |

---

## 五、发布前检查清单

- [ ] 删除所有 `.bak` 备份文件（含真实数据）
- [ ] 确认 `docs/` 下的 Excel 文件为脱敏假数据
- [ ] 确认 `customer_profiles.jsonl` 无真实 CRM 数据残留
- [ ] 确认 `product.jsonl` 中无真实公司名
- [ ] 确认 LLM API Key 未硬编码在代码中
- [ ] 确认服务器防火墙仅开放必要端口
- [ ] 确认 `.gitignore` 排除了敏感数据文件
- [ ] 测试所有页面功能正常
- [ ] 配置 HTTPS（如使用域名）

---

## 六、成本估算

| 项目 | 月费用 | 年费用 |
|------|--------|--------|
| 云服务器（2核4G） | ~60 元 | ~720 元 |
| 域名 | ~4 元 | ~50 元 |
| SSL 证书 | 0 元 | 0 元 |
| LLM API（DeepSeek） | ~10-50 元 | ~120-600 元 |
| **合计** | **~70-110 元** | **~840-1320 元** |

> LLM API 费用取决于使用量，演示用途通常较低。

---

## 七、快速验证

部署完成后，执行以下验证：

```bash
# 1. 检查服务状态
curl http://your-domain.com/

# 2. 检查产品列表
curl http://your-domain.com/api/retrieval/product-options

# 3. 检查客户列表
curl "http://your-domain.com/api/customers?page=1&size=5"

# 4. 检查筛选选项
curl http://your-domain.com/api/retrieval/filter-options
```

预期返回 JSON 格式数据，无错误。

---

*Last Updated: 2026-07-14*
