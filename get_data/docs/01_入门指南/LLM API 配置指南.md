# LLM API 配置与使用指南

本文档介绍如何配置和使用 LLM（大语言模型）进行结构化数据抽取。

---

## 支持的 LLM 服务商

系统目前支持以下 LLM 服务商：

| 服务商 | 模型 | 适用场景 |
|--------|------|----------|
| DeepSeek | deepseek-chat | 推荐，性价比高 |
| 本地 LLM | OpenAI 兼容格式 | 内网部署，无额外费用 |

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
# 使用 DeepSeek（默认）
python -m src.etl.core.extract_structured --limit 50

# 指定提供商
python -m src.etl.core.extract_structured --provider deepseek --limit 50
```

### 1.4 费用说明（2026 年 3 月）

| 模型 | 输入（缓存命中） | 输入（缓存未命中） | 输出 |
|------|-----------------|-------------------|------|
| deepseek-chat | ¥0.2/1M tokens | ¥2.0/1M tokens | ¥3.0/1M tokens |

**单条记录花费**: 约 ¥0.001-0.005 元

---

## 二、本地 LLM 配置

### 2.1 前提条件

本地 LLM 需要通过 OpenAI 兼容 API 暴露（如 vLLM 或 SGLang 部署）。

### 2.2 配置方式

**方式 1：编辑 `src/config.py`**

```python
LOCAL_LLM_CONFIG = {
    "api_key": "local-api-key",  # 本地 API Key
    "base_url": "http://10.210.10.51:8002/v1",  # 本地服务地址
    "model": "/models/Kimi-K2.5",
    "timeout": 600,
}
```

**方式 2：使用环境变量（推荐）**

```bash
# Windows PowerShell
$env:LOCAL_LLM_BASE_URL="http://10.210.10.51:8002/v1"
$env:LOCAL_LLM_MODEL="/models/Kimi-K2.5"
$env:LOCAL_LLM_API_KEY="local-api-key"

# Linux/Mac
export LOCAL_LLM_BASE_URL="http://10.210.10.51:8002/v1"
export LOCAL_LLM_MODEL="/models/Kimi-K2.5"
export LOCAL_LLM_API_KEY="local-api-key"
```

### 2.3 使用本地模型

```bash
# 设置环境变量后
python -m src.etl.core.extract_structured --provider local --limit 50
```

---

## 三、模型选择建议

### 3.1 模型对比

| 模型 | 优点 | 缺点 | 推荐场景 |
|------|------|------|----------|
| deepseek-chat | 性价比高，速度快 | 需要网络 | 日常批量抽取 |
| 本地 LLM | 无额外费用，内网可用 | 需要自行部署 | 内网环境、大量使用 |

### 3.2 选择建议

- **首次使用/测试**: 推荐 `deepseek-chat`
- **内网环境**: 推荐本地 LLM
- **日常批量抽取**: 推荐本地 LLM（无费用）或 `deepseek-chat`（效果好）

---

## 四、测试模型效果

### 4.1 单模型测试

```bash
# 测试 DeepSeek
python -m src.etl.core.extract_structured --provider deepseek --limit 10

# 测试本地 LLM
python -m src.etl.core.extract_structured --provider local --limit 10
```

### 4.2 查看抽取结果

抽取结果保存在：
```
get_data/data/output/etl/tenders_structured_{provider}.jsonl
```

---

## 五、常见问题

### Q1: API Key 无效？

**检查项**:
- API Key 是否正确复制（无多余空格）
- API Key 是否已激活
- 账户余额是否充足

### Q2: 请求超时？

**解决方法**:
- 增加 `timeout` 值
- 检查网络连接
- 稍后重试

### Q3: 额度不足？

**解决方法**:
- DeepSeek: 访问 https://platform.deepseek.com/ 充值

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
1. 使用本地 LLM（无额外费用）
2. 利用缓存命中（相同内容不重复抽取）
3. 减少不必要的抽取（使用 `--limit` 参数）

---

## 六、相关文档

- [完整使用指南](README.md)
- [LLM 抽取新手指南.md](LLM 抽取新手指南.md)

---

## 技术支持

遇到问题请查看：
- 日志文件：`logs/extract_*.log`
- 完整文档：`docs/README.md`
