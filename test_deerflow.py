# -*- coding: utf-8 -*-
"""
DeerFlow 连接测试脚本
验证 DeerFlowClient 能否正常初始化并执行简单对话
"""

import sys
sys.path.insert(0, r"D:\sales_agent\get_data\.claude\skills\deer-flow\backend")

# 设置 UTF-8 输出
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from deerflow.client import DeerFlowClient

# DeerFlow config 路径
CONFIG_PATH = r"D:\sales_agent\get_data\.claude\skills\deer-flow\config.yaml"

def test_deerflow():
    print("=" * 60)
    print("DeerFlow Connection Test")
    print("=" * 60)

    # 1. 初始化客户端
    print("\n[1] Initialize DeerFlowClient...")
    try:
        client = DeerFlowClient(config_path=CONFIG_PATH)
        print("    [OK] Client initialized")
    except Exception as e:
        print(f"    [FAIL] Init failed: {e}")
        return False

    # 2. 列出可用模型
    print("\n[2] List available models...")
    try:
        models = client.list_models()
        print(f"    Found {len(models.get('models', []))} models")
        for m in models.get('models', []):
            print(f"    - {m.get('name')} ({m.get('display_name', m.get('name'))})")
    except Exception as e:
        print(f"    [FAIL] Get models failed: {e}")

    # 3. 列出可用 Skills
    print("\n[3] List available skills...")
    try:
        skills = client.list_skills()
        print(f"    Found {len(skills.get('skills', []))} skills")
        for s in skills.get('skills', []):
            print(f"    - {s.get('name')}")
    except Exception as e:
        print(f"    [FAIL] Get skills failed: {e}")

    # 4. 执行简单对话测试
    print("\n[4] Run simple chat test...")
    print("    Sending: 'Say hello in one sentence'")
    try:
        response = client.chat("Say hello in one sentence", thread_id="test-thread")
        print(f"    Response: {response}")
        print("    [OK] Chat test passed")
    except Exception as e:
        print(f"    [FAIL] Chat test failed: {e}")
        return False

    print("\n" + "=" * 60)
    print("DeerFlow Test Complete")
    print("=" * 60)
    return True

if __name__ == "__main__":
    test_deerflow()
