# -*- coding: utf-8 -*-
"""
阿里云 DashScope 大模型调用工具
支持通义千问系列模型
"""

import sys
import os
import re
import json

# 添加项目根目录和 src 目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)
from config import get_llm_config

# 尝试导入 openai（阿里云 DashScope 使用 OpenAI 兼容接口）
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("[WARN] openai 库未安装，LLM 功能将不可用。请运行：pip install openai")


def get_client(api_key=None):
    """获取 LLM 客户端"""
    if not HAS_OPENAI:
        return None

    llm_config = get_llm_config()
    api_key = api_key or llm_config.get('api_key')
    if not api_key:
        print("[WARN] 未配置 API Key")
        return None

    base_url = llm_config.get('base_url')
    timeout = llm_config.get('timeout', 120)

    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)


def chat_completion(messages, model=None, api_key=None, **kwargs):
    """
    通用对话完成接口

    Args:
        messages: 消息列表 [{"role": "user", "content": "..."}]
        model: 模型名称，默认使用配置中的模型
        api_key: API Key，默认使用配置中的 API Key
        **kwargs: 其他参数（temperature, max_tokens 等）

    Returns:
        str: 模型响应内容
    """
    client = get_client(api_key)
    if not client:
        return None

    model = model or get_llm_config().get('model', 'MiniMax-M3')
    temperature = kwargs.get('temperature', 0.1)
    max_tokens = kwargs.get('max_tokens', 2000)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[ERROR] LLM 调用失败：{e}")
        return None


def extract_json(response_text):
    """从响应文本中提取 JSON"""
    if not response_text:
        return None

    # 提取 JSON
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def call_for_extraction(prompt, model=None, api_key=None):
    """
    调用 LLM 进行数据抽取

    Args:
        prompt: 提示词
        model: 模型名称
        api_key: API Key

    Returns:
        dict: 解析后的 JSON 数据
    """
    response = chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        api_key=api_key,
        max_tokens=2000,
        temperature=0.1
    )

    return extract_json(response)


# 预定义的抽取 Prompt
EXTRACT_PROMPT = """你是一个专业的招投标数据抽取专家。请从以下招标公告中提取关键信息，并以严格的 JSON 格式输出。

## 输入数据
- 项目名称：{project_name}
- 采购人：{buyer_name}
- 代理机构：{agency_name}
- 预算：{budget}
- 发布日期：{publish_date}
- 公告内容：
{content}

## 输出要求
1. 必须输出严格的 JSON 格式，不要有任何额外文字
2. 不要猜测，所有字段必须来源于输入文本
3. opportunity_score 范围固定为 0-100
4. 未提及的字段设为 null 或空数组/空字符串

## 输出 JSON 字段
{{
  "product_keywords": [],
  "application_scenario": "",
  "technical_requirements_summary": "",
  "contact_person": "",
  "attachment_summary": "",
  "opportunity_score": 0,
  "opportunity_reason": "",
  "next_action": ""
}}
"""


def extract_tender_data(tender_info):
    """
    抽取招标数据结构化字段

    Args:
        tender_info: 招标信息字典
            - project_name: 项目名称
            - buyer_name: 采购人
            - agency_name: 代理机构
            - budget: 预算
            - publish_date: 发布日期
            - content: 公告内容

    Returns:
        dict: 结构化字段
    """
    prompt = EXTRACT_PROMPT.format(
        project_name=tender_info.get('project_name', ''),
        buyer_name=tender_info.get('buyer_name', ''),
        agency_name=tender_info.get('agency_name', ''),
        budget=tender_info.get('budget', ''),
        publish_date=tender_info.get('publish_date', ''),
        content=tender_info.get('content', '')[:6000]
    )

    return call_for_extraction(prompt)


if __name__ == "__main__":
    # 测试调用
    import argparse

    parser = argparse.ArgumentParser(description='LLM 工具测试')
    parser.add_argument('--api-key', type=str, help='API Key')
    parser.add_argument('--model', type=str, default='qwen-plus', help='模型名称')
    args = parser.parse_args()

    # 简单测试
    test_input = {
        'project_name': '测试项目',
        'buyer_name': '测试单位',
        'agency_name': '',
        'budget': '100 万元',
        'publish_date': '2026-03-30',
        'content': '这是一个测试招标公告，需要采购芯片相关设备。'
    }

    result = extract_tender_data(test_input)
    print("抽取结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
