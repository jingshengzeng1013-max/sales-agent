# -*- coding: utf-8 -*-
"""
本地 LLM 调用测试脚本 - 独立于项目，直接调用本地 OpenAI 兼容端点
"""
import os
import urllib.error
import urllib.request

from openai import OpenAI

# ==================== 配置区域 ====================
# 修改为你的本地模型配置
BASE_URL = "http://10.210.10.51:11437/v1"  # 本地推理服务端点 (vLLM / Ollama / LM Studio 等)
API_KEY = "sk-local"                   # 本地服务通常不需要真实 key
MODEL = "/models/Qwen3-32B"                   # 你的本地模型名称
# ==================== 配置区域 ====================


def create_client() -> OpenAI:
    """创建 OpenAI 客户端"""
    base = os.environ.get("LOCAL_LLM_BASE_URL", BASE_URL).rstrip("/")
    return OpenAI(
        api_key=os.environ.get("LOCAL_LLM_API_KEY", API_KEY),
        base_url=base,
        timeout=120.0,
    )


def _print_exc_chain(exc: BaseException) -> None:
    """打印 OpenAI SDK 包装下的真实网络错误（如超时、拒绝连接）。"""
    depth = exc
    i = 0
    while depth is not None and i < 6:
        print(f"  └─ [{type(depth).__name__}] {depth}")
        depth = getattr(depth, "__cause__", None) or getattr(
            depth, "__context__", None
        )
        i += 1


def probe_openai_compat_base(base_url: str, timeout: float = 5.0) -> None:
    """探测 /v1/models 是否可达（常见 OpenAI 兼容服务）。"""
    base = base_url.rstrip("/")
    if not base.endswith("/v1"):
        models_url = base + "/v1/models"
    else:
        models_url = base + "/models"
    print(f"\n[连通性] GET {models_url}（超时 {timeout}s）…")
    try:
        req = urllib.request.Request(models_url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(500)
            print(f"  HTTP {resp.status}，响应前 {len(body)} 字节（服务在线）")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}：{e.reason}（端口通，路径或鉴权可能不对）")
    except urllib.error.URLError as e:
        print(f"  无法连接：{e.reason}")
        print("  常见原因：本机与 10.210.10.51 不在同一网段、未连 VPN、防火墙拦截、")
        print("  或服务未在 11437 监听。请在能访问该机的终端执行：")
        print(f"    curl -sS -m 3 {models_url}")
    except Exception as e:
        print(f"  探测异常：{e}")


def chat_simple(prompt: str, system_prompt: str = "You are a helpful assistant") -> str:
    """简单对话"""
    client = create_client()

    response = client.chat.completions.create(
        model=os.environ.get('LOCAL_LLM_MODEL', MODEL),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        stream=False,
    )

    return response.choices[0].message.content


def chat_stream(prompt: str, system_prompt: str = "You are a helpful assistant") -> None:
    """流式输出对话"""
    client = create_client()

    response = client.chat.completions.create(
        model=os.environ.get('LOCAL_LLM_MODEL', MODEL),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        stream=True,
    )

    print("模型回复：", end="", flush=True)
    for chunk in response:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print()  # 换行


def main():
    print("=" * 50)
    print("本地 LLM 调用测试")
    print("=" * 50)
    base = os.environ.get("LOCAL_LLM_BASE_URL", BASE_URL)
    print(f"端点：{base}")
    print(f"模型：{os.environ.get('LOCAL_LLM_MODEL', MODEL)}")
    print("=" * 50)

    probe_openai_compat_base(base)

    # 测试 1: 简单对话
    print("\n[测试 1] 简单对话:")
    try:
        result = chat_simple("你好，请介绍一下自己")
        print(f"回复：{result}")
    except Exception as e:
        print(f"错误：{e}")
        _print_exc_chain(e)

    # 测试 2: 流式输出
    print("\n[测试 2] 流式输出:")
    try:
        chat_stream("用一句话解释什么是人工智能")
    except Exception as e:
        print(f"错误：{e}")
        _print_exc_chain(e)

    # 测试 3: 多轮对话
    print("\n[测试 3] 多轮对话:")
    try:
        client = create_client()
        messages = [
            {"role": "system", "content": "你是一个编程助手"},
            {"role": "user", "content": "Python 中如何定义一个函数？"},
        ]

        response = client.chat.completions.create(
            model=os.environ.get('LOCAL_LLM_MODEL', MODEL),
            messages=messages,
            stream=False,
        )
        print(f"回复：{response.choices[0].message.content}")

        # 继续追问
        messages.append({"role": "assistant", "content": response.choices[0].message.content})
        messages.append({"role": "user", "content": "能举个例子吗？"})

        response2 = client.chat.completions.create(
            model=os.environ.get('LOCAL_LLM_MODEL', MODEL),
            messages=messages,
            stream=False,
        )
        print(f"追问回复：{response2.choices[0].message.content}")
    except Exception as e:
        print(f"错误：{e}")
        _print_exc_chain(e)

    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)


if __name__ == "__main__":
    main()
