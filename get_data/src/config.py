# -*- coding: utf-8 -*-
"""
配置文件
集中管理所有路径和参数
"""

import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path("D:/sales_agent/get_data")

# 数据目录
DATA_DIR = BASE_DIR / "data"

# HTML 保存目录（放在 data 下）
HTML_DIR = DATA_DIR / "html"

# 数据库路径
DB_PATH = DATA_DIR / "ccgp_data.db"

# 阿里云 DashScope 配置
# 文档：https://help.aliyun.com/zh/dashscope/
# 北京地域 base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_CONFIG = {
    "api_key": "",  # 填入阿里云 API Key（从环境变量 DASHSCOPE_API_KEY 获取）
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen3.5-plus",  # 通义千问 3.5 Plus
    "timeout": 120,
}

# DeepSeek 配置（官方 API）
# 定价参考：https://platform.deepseek.com/pricing
# 输入（缓存命中）：0.2 元/1M tokens
# 输入（缓存未命中）：2 元/1M tokens
# 输出：3 元/1M tokens
DEEPSEEK_CONFIG = {
    "api_key": "sk-e9a318f595e0419a94c255f3154eb1cf",  # 填入 DeepSeek API Key
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "timeout": 120,
    # 定价（元/1M tokens）
    "pricing": {
        "input_cache_hit": 0.2,    # 输入（缓存命中）
        "input_cache_miss": 2.0,   # 输入（缓存未命中）
        "output": 3.0,             # 输出
    }
}

# 字节跳动豆包配置（Volcengine Ark）
# 定价参考：https://www.volcengine.com/docs/82379/1099320
DOUBAO_CONFIG = {
    "api_key": "",  # 填入 Volcengine API Key（从环境变量 ARK_API_KEY 获取）
    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "model": "doubao-seed-2-0-lite-260215",  # 豆包 Seed 2.0 Lite
    "timeout": 120,
}

# 本地 LLM（OpenAI 兼容，如 vLLM / SGLang；base_url 需含 /v1）
LOCAL_LLM_CONFIG = {
    "api_key": os.environ.get("LOCAL_LLM_API_KEY", "local-api-key"),
    "base_url": os.environ.get(
        "LOCAL_LLM_BASE_URL", "http://10.210.10.51:11437/v1"
    ).rstrip("/"),
    "model": os.environ.get("LOCAL_LLM_MODEL", "/models/Qwen3-32B"),
    "timeout": int(os.environ.get("LOCAL_LLM_TIMEOUT", "600")),
}


# =============================================================================
# 统一模型配置管理
# =============================================================================

# 所有模型配置映射（可通过模型名称获取配置）
LLM_PROVIDERS = {
    "local": {
        "name": "Local OpenAI-compatible",
        "config": LOCAL_LLM_CONFIG,
        "env_key": None,
    },
    "deepseek": {
        "name": "DeepSeek",
        "config": DEEPSEEK_CONFIG,
        "env_key": None,  # 已硬编码 API Key
    },
}

# 默认使用的模型提供商（可用环境变量 LLM_PROVIDER=deepseek 切换）
DEFAULT_PROVIDER = os.environ.get("LLM_PROVIDER", "local")


def get_llm_config(provider=None):
    """
    获取指定模型的配置

    Args:
        provider (str, optional): 模型提供商名称，如 'deepseek'。
                                  为 None 时使用默认提供商。

    Returns:
        dict: 模型配置字典

    Raises:
        ValueError: 当指定的提供商不存在时抛出
    """
    if provider is None:
        provider = DEFAULT_PROVIDER

    if provider not in LLM_PROVIDERS:
        available = ", ".join(LLM_PROVIDERS.keys())
        raise ValueError(f"未知的模型提供商：{provider}。可用的提供商：{available}")

    return LLM_PROVIDERS[provider]["config"]


# 爬虫配置
CRAWLER_CONFIG = {
    "base_url": "https://search.ccgp.gov.cn/bxsearch",
    "keyword": "通信终端",
    "delay_min": 2,
    "delay_max": 5,
    "page_index": 1,
    "timeout": 30,
    # URL 参数配置
    "searchtype": "2",        # 搜索类型：1=标题，2=全文
    "bidSort": "0",           # 排序方式：0=时间，1=相关性
    # 与浏览器 bxsearch 一致；缺省时站点结果集/分页可能与网页不一致
    "buyerName": "",
    "projectId": "",
    "pinMu": "0",
    "bidType": "0",
    "dbselect": "bidx",       # 采购公告索引；勿随意删改
    "displayZone": "",
    "zoneId": "",
    "pppStatus": "0",
    "agentName": "",
    # 时间配置
    # timeType: "0":今日 "1":近三日 "2":近一周 "3":近一月 "4":近三月 "5":近半年 "6":指定时间
    "timeType": "5",
    # 近半年示例：与网页手工搜索范围对齐（YYYY:MM:DD）
    "start_time": "2025:10:14",
    "end_time": None,  # None 表示结束日为当天
}

# 确保数据目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
HTML_DIR.mkdir(parents=True, exist_ok=True)

# 日志目录
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# 流式日志目录（用于 Web UI 实时日志输出）
LOGS_STREAM_DIR = LOGS_DIR / "stream"
LOGS_STREAM_DIR.mkdir(parents=True, exist_ok=True)

# 输出目录（用于保存提取的 JSON、生成的报告等）
OUTPUT_DIR = DATA_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 爬虫输出目录（专门存放爬取的 JSON 数据）
CRAWLER_OUTPUT_DIR = OUTPUT_DIR / "crawler"
CRAWLER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ETL 结构化抽取产出（tenders_structured*.json）
ETL_OUTPUT_DIR = OUTPUT_DIR / "etl"
ETL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 附件下载目录（存放实际下载的附件文件）
ATTACHMENT_DIR = DATA_DIR / "attachment"
ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)

# 通义千问配置（从环境变量读取）
QWEN_CONFIG = {
    "api_key": os.environ.get("DASHSCOPE_API_KEY", ""),
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen3.5-plus",
    "timeout": 120,
}

# Embedding API 配置（用于向量检索）
EMBEDDING_CONFIG = {
    "base_url": "http://10.210.10.51:8022/v1",  # 本地 Embedding 服务地址
    "model": "/models/Qwen3-Embedding-0.6B",
    "dimension": 1024,
}

# 向量检索索引目录
INDEX_DIR = DATA_DIR / "index"
INDEX_DIR.mkdir(parents=True, exist_ok=True)

# 招标公告索引目录（用于按产品搜招标）
TENDER_INDEX_DIR = DATA_DIR / "index_tenders"
TENDER_INDEX_DIR.mkdir(parents=True, exist_ok=True)

# Web 应用日志目录
LOGS_WEBAPP_DIR = LOGS_DIR / "webapp"
LOGS_WEBAPP_DIR.mkdir(parents=True, exist_ok=True)
