# LLM API 配置与使用指南

本文档介绍如何配置和使用 LLM（大语言模型）进行结构化数据抽取。

---

## 支持的 LLM 服务商

系统目前支持以下 LLM 服务商：

| 服务商 | 模型 | 适用场景 |
|--------|------|----------|
| DeepSeek | deepseek-chat, deepseek-reasoner | 推荐，性价比高 |
| 阿里云 DashScope | qwen-plus, qwen-max | 中文理解强 |

---

## 一、DeepSeek 配置（推荐）

### 1.1 获取 API Key

1. 访问 DeepSeek 开放平台：https://platform.deepseek.com/
2. 注册/登录账号
3. 进入控制台 → API Keys
4. 创建新的 API Key
5. 复制 API Key（格式：`sk-xxxxxxxxxxxxxxxx`）

### 1.2 配置 API Key

编辑 `src/config.py`：

```python
DEEPSEEK_CONFIG = {
    "api_key": "sk-e9a318f595e0419a94c255f3154eb1cf",  # 替换为你的 API Key
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "timeout": 120,
}
```

### 1.3 使用 DeepSeek 模型

```bash
# 使用 DeepSeek V3（默认）
python src/etl/extract_structured.py --limit 50

# 使用 DeepSeek R1（推理版）
python src/etl/extract_structured.py --model deepseek-reasoner --limit 50
```

### 1.4 费用说明（2026 年 3 月）

| 模型 | 输入（缓存命中） | 输入（缓存未命中） | 输出 |
|------|-----------------|-------------------|------|
| deepseek-chat | ¥0.2/1M tokens | ¥2.0/1M tokens | ¥3.0/1M tokens |
| deepseek-reasoner | ¥4.0/1M tokens | ¥4.0/1M tokens | ¥8.0/1M tokens |

**单条记录花费**: 约 ¥0.001-0.005 元

---

## 二、字节跳动豆包配置（免费）

### 2.1 获取 API Key

1. 访问火山引擎方舟大模型平台：https://console.volcengine.com/ark
2. 登录/注册火山引擎账号
3. 开通"豆包 Seed 2.0"系列模型服务
4. 进入 API 密钥管理 → 创建访问凭证
5. 复制 API Key

### 2.2 配置 API Key

有两种配置方式：

**方式 1：编辑 `src/config.py`**

```python
DOUBAO_CONFIG = {
    "api_key": "your-api-key-here",  # 替换为你的 API Key
    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "model": "doubao-seed-2-0-lite-260215",
    "timeout": 120,
}
```

**方式 2：使用环境变量（推荐）**

```bash
# Windows PowerShell
$env:ARK_API_KEY="your-api-key-here"

# Linux/Mac
export ARK_API_KEY="your-api-key-here"
```

### 2.3 使用豆包模型

```bash
# 使用豆包 Seed 2.0 Lite
python src/etl/extract_structured.py --model doubao --limit 50
```

### 2.4 费用说明

豆包 Seed 2.0 Lite 目前提供**免费额度**，适合测试和小额使用。

---

## 三、阿里云 DashScope 配置

### 2.1 获取 API Key

1. 访问阿里云 DashScope 控制台：https://dashscope.console.aliyun.com/
2. 登录/注册阿里云账号
3. 开通"模型服务"（通义千问）
4. 进入 API-KEY 管理 → 创建新的 API Key
5. 复制 API Key（格式：`sk-xxxxxxxxxxxxxxxx`）

### 2.2 配置 API Key

编辑 `src/config.py`：

```python
DASHSCOPE_CONFIG = {
    "api_key": "sk-xxxxxxxxxxxxxxxx",  # 替换为你的 API Key
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen-plus",
    "timeout": 60,
}
```

### 2.3 使用阿里云模型

```bash
# 使用通义千问 Plus
python src/etl/extract_structured.py --model qwen-plus --limit 50

# 使用通义千问 Max
python src/etl/extract_structured.py --model qwen-max --limit 50
```

### 2.4 费用说明（2026 年 3 月）

| 模型 | 输入 | 输出 |
|------|------|------|
| qwen-plus | ¥4.0/1M tokens | ¥12.0/1M tokens |
| qwen-max | ¥20.0/1M tokens | ¥60.0/1M tokens |

**单条记录花费**: 约 ¥0.005-0.015 元

---

## 三、使用环境变量（可选）

如果不想在代码中硬编码 API Key，可以使用环境变量：

### Windows (PowerShell)

```powershell
$env:DEEPSEEK_API_KEY="sk-xxx"
$env:DASHSCOPE_API_KEY="sk-xxx"
```

### Linux/Mac

```bash
export DEEPSEEK_API_KEY="sk-xxx"
export DASHSCOPE_API_KEY="sk-xxx"
```

### 在代码中读取环境变量

```python
import os

DEEPSEEK_CONFIG = {
    "api_key": os.getenv("DEEPSEEK_API_KEY", "default-key"),
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "timeout": 120,
}
```

---

## 四、模型选择建议

### 4.1 模型对比

| 模型 | 优点 | 缺点 | 推荐场景 |
|------|------|------|----------|
| deepseek-chat | 性价比高，速度快 | 复杂推理一般 | 日常批量抽取 |
| deepseek-reasoner | 推理能力强 | 价格较高 | 复杂公告 |
| doubao-seed-2-0-lite | 免费额度，性价比高 | 新模型 | 测试/日常使用 |
| qwen-plus | 中文理解好，性价比高 | 能力中等 | 日常使用 |
| qwen-max | 中文理解最强 | 价格最贵 | 高精度要求 |

### 4.2 选择建议

- **首次使用/测试**: 推荐 `doubao-seed-2-0-lite`，有免费额度
- **日常批量抽取**: 推荐 `deepseek-chat`，性价比最高
- **追求精度**: 推荐 `qwen-max`，中文理解最强
- **复杂公告**: 推荐 `deepseek-reasoner`，推理能力强
- **均衡选择**: 推荐 `qwen-plus`，性能和价格平衡

---

## 五、测试模型效果

### 5.1 单模型测试

```bash
# 测试 DeepSeek V3
python src/etl/extract_structured.py --model deepseek-chat --limit 10

# 测试 DeepSeek R1
python src/etl/extract_structured.py --model deepseek-reasoner --limit 10

# 测试字节跳动豆包
python src/etl/extract_structured.py --model doubao --limit 10

# 测试通义千问 Plus
python src/etl/extract_structured.py --model qwen-plus --limit 10

# 测试通义千问 Max
python src/etl/extract_structured.py --model qwen-max --limit 10
```

### 5.2 批量测试所有模型

Windows 用户可以直接运行：

```bash
test_models.bat
```

该脚本会依次使用 5 个模型各抽取 10 条记录，生成 5 个 JSON 文件用于对比。

---

## 六、查看抽取结果

### 6.1 JSON 文件位置

抽取结果保存在：

```
output/tenders_structured_{model_name}.json
```

### 6.2 查看文件内容

```bash
# Windows
notepad output\tenders_structured_deepseek-chat.json

# Linux/Mac
cat output/tenders_structured_deepseek-chat.json
```

### 6.3 对比不同模型效果

可以通过以下维度对比：

1. **字段完整度**: 哪个模型抽取的字段更多
2. **准确性**: 随机抽样检查抽取结果是否准确
3. **花费**: 查看日志文件中的 token 花费
4. **速度**: 哪个模型响应更快

---

## 七、支持的模型列表

| 模型标识 | 模型名称 | 服务商 | 说明 |
|----------|----------|--------|------|
| `deepseek-chat` | deepseek-chat | DeepSeek | DeepSeek V3，性价比高 |
| `deepseek-reasoner` | deepseek-reasoner | DeepSeek | DeepSeek R1，推理能力强 |
| `doubao` | doubao-seed-2-0-lite-260215 | 字节跳动 | 豆包 Seed 2.0 Lite，免费额度 |
| `qwen-plus` | qwen-plus | 阿里云 | 通义千问 Plus，均衡选择 |
| `qwen-max` | qwen-max | 阿里云 | 通义千问 Max，最强中文模型 |

---

## 八、常见问题

### Q1: API Key 无效？

**检查项**:
- API Key 是否正确复制（无多余空格）
- API Key 是否已激活
- 账户余额是否充足

### Q2: 请求超时？

**解决方法**:
- 增加 `timeout` 值：`"timeout": 120`
- 检查网络连接
- 稍后重试

### Q3: 额度不足？

**解决方法**:
- DeepSeek: 访问 https://platform.deepseek.com/ 充值
- 阿里云：访问 https://dashscope.console.aliyun.com/ 充值
- 字节跳动豆包：访问 https://console.volcengine.com/ark 领取免费额度

### Q4: 抽取失败率高？

**可能原因**:
- API Key 权限不足
- 模型服务未开通
- 网络问题

**解决方法**:
- 检查模型服务是否已开通
- 查看日志文件 `logs/extract_*.log` 获取详细错误信息

### Q5: 如何降低花费？

**建议**:
1. 使用缓存命中（相同内容不重复抽取）
2. 选择性价比更高的模型（如 deepseek-chat, doubao）
3. 减少不必要的抽取（使用 `--limit` 参数）
4. 批量抽取时选择合适的时间（避免高峰期）
5. 利用豆包的免费额度进行测试和开发

---

## 九、相关文档

- [完整使用指南](README.md)
- [LLM 抽取新手指南.md](LLM 抽取新手指南.md)
- [MVP_RAG_实施方案.md](MVP_RAG_实施方案.md)

---

## 技术支持

遇到问题请查看：
- 日志文件：`logs/extract_*.log`
- 完整文档：`docs/README.md`
