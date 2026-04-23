# 阿里云 DashScope 集成说明

## 配置方式

### 1. 在 config.py 中配置

编辑 `src/config.py`，设置 API Key：

```python
DASHSCOPE_CONFIG = {
    "api_key": "sk-xxxxxxxxxxxxxxxx",  # 替换为你的 API Key
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen-plus",
    "timeout": 60,
}
```

### 2. 使用环境变量（推荐）

```bash
# Windows PowerShell
$env:DASHSCOPE_API_KEY="sk-xxxxxxxxxxxxxxxx"

# Linux/Mac
export DASHSCOPE_API_KEY="sk-xxxxxxxxxxxxxxxx"
```

## 获取 API Key

1. 访问阿里云 DashScope 控制台：https://dashscope.console.aliyun.com/
2. 登录/注册阿里云账号
3. 开通"模型服务"（通义千问）
4. 创建 API Key
5. 复制 API Key 到配置文件或环境变量

## 使用方式

### 方法 1：通过 extract_structured.py 抽取

```bash
# 纯规则抽取（不使用 LLM）
python src/etl/extract_structured.py --all

# 使用 LLM 增强抽取
python src/etl/extract_structured.py --all --use-llm

# 指定 API Key（覆盖配置）
python src/etl/extract_structured.py --all --use-llm --api-key sk-xxx
```

### 方法 2：通过 llm_client.py 调用

```python
from src.etl.llm_client import extract_tender_data, chat_completion

# 方式 1：使用预定义的抽取函数
tender_info = {
    'project_name': '芯片采购项目',
    'buyer_name': '某某大学',
    'budget': '100 万元',
    'content': '...'
}
result = extract_tender_data(tender_info)

# 方式 2：通用对话接口
response = chat_completion(
    messages=[{"role": "user", "content": "你好，请介绍一下自己"}],
    model="qwen-plus"
)
```

## 支持的模型

在 `config.py` 的 `DASHSCOPE_CONFIG` 中修改 `model` 参数：

| 模型 | 说明 |
|------|------|
| `qwen-plus` | 通义千问-plus（推荐） |
| `qwen-max` | 通义千问-max（最强） |
| `qwen-turbo` | 通义千问-turbo（最快） |

## 费用说明

- 通义千问-plus：约 0.004 元/千 tokens
- 具体价格请参考：https://help.aliyun.com/zh/dashscope/developer-reference/tongyi-qianwen-llm/price

## 常见问题

### Q: API Key 无效？
A: 检查 API Key 是否正确复制，确保没有多余空格

### Q: 请求超时？
A: 在 config.py 中增加 `timeout` 值，如 `"timeout": 120`

### Q: 额度不足？
A: 登录阿里云控制台充值或领取免费额度
