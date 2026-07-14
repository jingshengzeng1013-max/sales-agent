# -*- coding: utf-8 -*-
"""
Agentic RAG 销售助手

基于 Skill 架构的智能销售分析 Agent，支持：
- 多轮对话
- 工具自动调用
- 迭代检索
- 自我纠错
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

from .skills import BaseSkill, SkillResult, get_registry

logger = logging.getLogger("agent.sales_agent")


class SalesAgent:
    """
    销售场景 Agent

    基于 Agentic RAG 架构，通过 LLM 自主决策调用 Skill 完成复杂任务。

    使用示例：
        agent = SalesAgent()

        # 注册额外 Skill（可选，已预注册基础 Skill）
        agent.register_skill(MyCustomSkill())

        # 执行任务
        result = agent.run("分析一下智慧城市项目的市场机会")

        # 或流式输出
        for chunk in agent.run_stream("帮我找最近通信类的招标"):
            print(chunk, end="", flush=True)
    """

    def __init__(
        self,
        model: str = "DeepSeek-V3",
        api_key: str = None,
        base_url: str = None,
        max_rounds: int = 5,
        verbose: bool = True
    ):
        """
        初始化 SalesAgent

        Args:
            model: LLM 模型名称
            api_key: API Key
            base_url: API 地址
            max_rounds: 最大对话轮次
            verbose: 是否打印详细日志
        """
        self.model = model
        self.max_rounds = max_rounds
        self.verbose = verbose

        # 初始化 LLM 客户端
        self._init_client(api_key, base_url)

        # 初始化 Skill 注册表
        self.registry = get_registry()
        self._register_default_skills()

        # 对话历史
        self.conversation_history: List[Dict[str, Any]] = []

        # 当前轮次
        self.current_round = 0

        # 执行记录
        self.execution_trace: List[Dict[str, Any]] = []

    def _init_client(self, api_key, base_url):
        """初始化 LLM 客户端"""
        try:
            from openai import OpenAI

            if api_key is None or base_url is None:
                # 从 config 读取
                import sys
                from pathlib import Path
                BASE_DIR = Path(__file__).resolve().parent.parent.parent
                sys.path.append(str(BASE_DIR))

                try:
                    from src.config import get_llm_config
                    llm_config = get_llm_config()
                    api_key = api_key or llm_config.get("api_key", "")
                    base_url = base_url or llm_config.get("base_url", "https://api.minimaxi.com/v1")
                    self.model = self.model or llm_config.get("model", "MiniMax-M3")
                except ImportError:
                    # 默认值
                    api_key = api_key or ""
                    base_url = base_url or "https://api.minimaxi.com/v1"

            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=120.0
            )
            logger.info(f"LLM 客户端初始化成功: {base_url}")
        except Exception as e:
            logger.error(f"LLM 客户端初始化失败: {e}")
            self.client = None

    def _register_default_skills(self):
        """注册默认 Skill"""
        from .skills.search_tenders import SearchTendersSkill
        from .skills.customer_profile import CustomerProfileSkill, CustomerListSkill
        from .skills.sales_suggestions import SalesSuggestionsSkill, ProjectAnalysisSkill

        # 注册基础 Skill
        skills_to_register = [
            SearchTendersSkill(),
            CustomerProfileSkill(),
            CustomerListSkill(),
            SalesSuggestionsSkill(),
            ProjectAnalysisSkill(),
        ]

        for skill in skills_to_register:
            self.registry.register(skill)

        logger.info(f"已注册 {len(self.registry)} 个默认 Skill")

    def register_skill(self, skill: BaseSkill, force: bool = False) -> bool:
        """注册额外 Skill"""
        return self.registry.register(skill, force)

    def get_schemas(self) -> List[Dict[str, Any]]:
        """获取所有 Skill 的 schema"""
        return self.registry.get_all_schemas()

    def _log(self, message: str, level: str = "info"):
        """日志输出"""
        if self.verbose:
            if level == "info":
                logger.info(message)
            elif level == "warning":
                logger.warning(message)
            elif level == "error":
                logger.error(message)
            print(f"[{level.upper()}] {message}")

    def _call_llm(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict] = None,
        tool_choice: str = "auto"
    ) -> Any:
        """调用 LLM"""
        if self.client is None:
            return None

        try:
            params = {
                "model": self.model,
                "messages": messages,
                "tool_choice": tool_choice
            }
            if tools:
                params["tools"] = tools

            response = self.client.chat.completions.create(**params)
            return response

        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return None

    def _execute_tool_call(self, tool_call: Dict) -> Dict[str, Any]:
        """执行单个工具调用"""
        tool_name = tool_call.get("function", {}).get("name", "")
        tool_args = json.loads(tool_call.get("function", {}).get("arguments", "{}"))

        self._log(f"执行工具: {tool_name}, 参数: {tool_args}", "info")

        # 记录执行
        self.execution_trace.append({
            "tool": tool_name,
            "args": tool_args,
            "timestamp": time.time()
        })

        # 执行 Skill
        result = self.registry.execute(tool_name, tool_args)

        return {
            "tool_call_id": tool_call.get("id", ""),
            "tool_name": tool_name,
            "result": result.to_dict()
        }

    def _should_finish(self, response: str) -> bool:
        """判断是否应该结束"""
        finish_markers = [
            "完成调研",
            "完成分析",
            "finish: true",
            "调研完成",
            "分析完成",
            "任务完成"
        ]
        return any(marker in response for marker in finish_markers)

    def chat(self, user_input: str) -> str:
        """
        单轮对话（不自动调用工具）

        Args:
            user_input: 用户输入

        Returns:
            str: LLM 回复
        """
        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })

        response = self._call_llm(
            messages=self.conversation_history,
            tools=self.get_schemas()
        )

        if response is None:
            return "抱歉，LLM 服务暂时不可用"

        msg = response.choices[0].message
        reply = msg.content or ""

        self.conversation_history.append({
            "role": "assistant",
            "content": reply
        })

        return reply

    def run(self, user_query: str, max_rounds: int = None) -> str:
        """
        运行 Agent 执行任务（多轮）

        Args:
            user_query: 用户任务描述
            max_rounds: 最大轮次（覆盖默认值）

        Returns:
            str: 最终回答
        """
        max_rounds = max_rounds or self.max_rounds
        self.current_round = 0
        self.execution_trace = []

        # 添加系统提示
        if not self.conversation_history:
            system_prompt = """你是一位专业的政府采购招投标销售顾问。

你可以使用以下工具来完成任务：
- search_tenders: 搜索招标项目
- get_customer_profile: 获取客户画像
- list_customers: 获取客户列表
- generate_sales_suggestions: 生成销售建议
- analyze_project: 分析项目

每次回复请先思考是否需要调用工具，如果需要，明确说明调用哪个工具以及参数。
当任务完成后，明确说明"完成调研"或"分析完成"。"""

            self.conversation_history.append({
                "role": "system",
                "content": system_prompt
            })

        # 添加用户任务
        current_time = time.localtime()
        time_str = time.strftime("%Y年%m月%d日 %H:%M:%S", current_time)

        task_message = f"当前时间：{time_str}\n\n用户任务：{user_query}\n\n请开始执行任务，必要时调用相关工具。"

        self.conversation_history.append({
            "role": "user",
            "content": task_message
        })

        self._log(f"开始执行任务（最多 {max_rounds} 轮）", "info")

        # 多轮对话循环
        while self.current_round < max_rounds:
            self.current_round += 1
            self._log(f"=== 轮次 {self.current_round}/{max_rounds} ===", "info")

            # 调用 LLM
            response = self._call_llm(
                messages=self.conversation_history,
                tools=self.get_schemas()
            )

            if response is None:
                self._log("LLM 调用失败", "error")
                break

            msg = response.choices[0].message

            # 检查是否需要调用工具
            if msg.tool_calls:
                self._log(f"LLM 决定调用 {len(msg.tool_calls)} 个工具", "info")

                # 将 assistant 消息加入历史
                self.conversation_history.append({
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in msg.tool_calls
                    ]
                })

                # 执行工具调用
                for tool_call in msg.tool_calls:
                    tool_result = self._execute_tool_call(tool_call)

                    # 将工具结果加入历史
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_result["tool_call_id"],
                        "content": json.dumps(tool_result["result"], ensure_ascii=False)
                    })

                # 再次调用 LLM 生成回答
                response = self._call_llm(
                    messages=self.conversation_history,
                    tools=self.get_schemas()
                )

                if response:
                    msg = response.choices[0].message

            # 获取回复内容
            reply = msg.content or ""

            # 添加助手回复到历史
            self.conversation_history.append({
                "role": "assistant",
                "content": reply
            })

            self._log(f"LLM 回复：{reply[:200]}...", "info")

            # 检查是否应该结束
            if self._should_finish(reply):
                self._log("任务完成", "info")
                break

        return self.conversation_history[-1].get("content", "")

    def run_simple(self, user_query: str) -> str:
        """
        简单模式：单轮 LLM 调用，不自动调用工具

        Args:
            user_query: 用户问题

        Returns:
            str: 回答
        """
        # 构建提示
        context = []
        context.append({
            "role": "system",
            "content": "你是一个专业的招投标销售顾问。请直接回答用户问题。"
        })
        context.append({
            "role": "user",
            "content": user_query
        })

        response = self._call_llm(messages=context, tools=None)

        if response:
            return response.choices[0].message.content or ""
        return "抱歉，无法生成回答"

    def get_execution_trace(self) -> List[Dict[str, Any]]:
        """获取执行轨迹"""
        return self.execution_trace

    def reset(self):
        """重置对话历史"""
        self.conversation_history = []
        self.current_round = 0
        self.execution_trace = []

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "model": self.model,
            "max_rounds": self.max_rounds,
            "skills_count": len(self.registry),
            "conversation_rounds": self.current_round,
            "execution_trace_length": len(self.execution_trace)
        }


def create_agent(**kwargs) -> SalesAgent:
    """工厂函数：创建 Agent"""
    return SalesAgent(**kwargs)
