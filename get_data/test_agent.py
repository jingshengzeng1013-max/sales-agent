# -*- coding: utf-8 -*-
"""
Agent 测试脚本
"""

import sys
from pathlib import Path

# 添加项目根目录到 path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.agent import SalesAgent, create_agent


def test_agent_creation():
    """测试 Agent 创建"""
    print("=" * 50)
    print("测试 1: Agent 创建")
    print("=" * 50)

    agent = create_agent(verbose=True)
    print(f"Agent 创建成功!")
    print(f"模型: {agent.model}")
    print(f"最大轮次: {agent.max_rounds}")
    print(f"已注册 Skill 数量: {len(agent.registry)}")
    print(f"Skill 列表: {agent.list_skill_names()}")
    print()


def test_simple_chat():
    """测试简单对话（不调用工具）"""
    print("=" * 50)
    print("测试 2: 简单对话模式")
    print("=" * 50)

    agent = create_agent(verbose=True)
    reply = agent.run_simple("你好，你是做什么的？")
    print(f"回复: {reply}")
    print()


def test_skill_schemas():
    """测试获取 Skill schemas"""
    print("=" * 50)
    print("测试 3: Skill Schemas")
    print("=" * 50)

    agent = create_agent()
    schemas = agent.get_schemas()
    print(f"共有 {len(schemas)} 个 Skill schema:")
    for s in schemas:
        print(f"  - {s['function']['name']}: {s['function']['description'][:50]}...")
    print()


def test_direct_skill_execution():
    """测试直接执行 Skill"""
    print("=" * 50)
    print("测试 4: 直接执行 Skill")
    print("=" * 50)

    agent = create_agent()

    # 测试搜索招标
    print("\n执行 search_tenders Skill...")
    result = agent.registry.execute("search_tenders", {
        "query": "智慧城市",
        "top_k": 3
    })
    print(f"结果: {result.to_dict()}")
    print()


def test_agent_run():
    """测试 Agent 多轮执行"""
    print("=" * 50)
    print("测试 5: Agent 多轮执行")
    print("=" * 50)

    agent = create_agent(verbose=True)

    # 重置对话历史
    agent.reset()

    # 执行任务
    reply = agent.run("帮我找最近智慧城市相关的招标项目")
    print(f"\n最终回复:\n{reply}")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Agentic RAG 销售助手测试")
    print("=" * 60 + "\n")

    try:
        test_agent_creation()
        test_skill_schemas()
        test_direct_skill_execution()
        test_simple_chat()
        # test_agent_run()  # 这个需要较长时间，暂时跳过
    except Exception as e:
        print(f"\n测试过程出现异常: {e}")
        import traceback
        traceback.print_exc()
