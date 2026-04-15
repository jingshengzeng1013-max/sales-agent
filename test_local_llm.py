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


def interactive_chat():
    """交互式对话模式"""
    client = create_client()
    messages = [{"role": "system", "content": "你是一个有帮助的 AI 助手。"}]
    
    print("\n" + "*" * 50)
    print("进入交互模式 (输入 'exit' 或 'quit' 退出，输入 'clear' 清空上下文)")
    print("*" * 50)

    while True:
        try:
            user_input = input("\n用户 > ").strip()
            
            if not user_input:
                continue
            if user_input.lower() in ['exit', 'quit']:
                print("退出对话。")
                break
            if user_input.lower() == 'clear':
                messages = [{"role": "system", "content": "你是一个有帮助的 AI 助手。"}]
                print("上下文已清空。")
                continue

            messages.append({"role": "user", "content": user_input})
            
            print("助手 > ", end="", flush=True)
            response = client.chat.completions.create(
                model=os.environ.get('LOCAL_LLM_MODEL', MODEL),
                messages=messages,
                stream=True,
            )

            full_reply = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    print(content, end="", flush=True)
                    full_reply += content
            print() # 换行
            
            messages.append({"role": "assistant", "content": full_reply})

        except KeyboardInterrupt:
            print("\n强制退出。")
            break
        except Exception as e:
            print(f"\n发生错误：{e}")
            _print_exc_chain(e)


def main():
    print("=" * 50)
    print("本地 LLM 调用测试")
    print("=" * 50)
    base = os.environ.get("LOCAL_LLM_BASE_URL", BASE_URL)
    print(f"端点：{base}")
    print(f"模型：{os.environ.get('LOCAL_LLM_MODEL', MODEL)}")
    print("=" * 50)

    probe_openai_compat_base(base)

    # 进入交互式对话
    interactive_chat()

    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)


if __name__ == "__main__":
    main()
