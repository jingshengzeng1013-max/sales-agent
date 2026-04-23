# -*- coding: utf-8 -*-
"""
Skill 基类定义

所有 Skill 必须继承 BaseSkill 并实现 execute 方法。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger("agent.skills")


@dataclass
class SkillResult:
    """Skill 执行结果"""
    success: bool
    data: Any = None
    error: str = ""
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "message": self.message
        }


class BaseSkill(ABC):
    """
    Skill 基类

    所有工具类必须继承此类并实现：
    - name: 技能名称（唯一标识）
    - description: 技能描述（LLM 会看到）
    - parameters: OpenAI 格式的参数 schema
    - execute(): 执行逻辑

    示例：
        class MySkill(BaseSkill):
            name = "my_skill"
            description = "这是我的技能描述"
            parameters = {
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "输入参数"}
                },
                "required": ["input"]
            }

            def execute(self, params: Dict[str, Any]) -> SkillResult:
                try:
                    result = do_something(params["input"])
                    return SkillResult(success=True, data=result)
                except Exception as e:
                    return SkillResult(success=False, error=str(e))
    """

    # 技能名称（子类必须定义）
    name: str = ""

    # 技能描述（告诉 LLM 什么时候用）
    description: str = ""

    # 参数 schema（OpenAI function calling 格式）
    parameters: Dict[str, Any] = field(default_factory=dict)

    # 是否需要认证
    requires_auth: bool = False

    # 技能分类（用于分组展示）
    category: str = "general"

    def __init__(self):
        if not self.name:
            raise ValueError(f"{self.__class__.__name__} 必须定义 name 属性")

        if not self.description:
            raise ValueError(f"{self.__class__.__name__} 必须定义 description 属性")

        self.logger = logging.getLogger(f"agent.skills.{self.name}")

    def get_schema(self) -> Dict[str, Any]:
        """
        返回 OpenAI function calling 格式的 schema

        Returns:
            dict: 符合 OpenAI tools 参数格式的 schema
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters if self.parameters else {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }

    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        """
        验证参数是否符合 schema 要求

        Args:
            params: 传入的参数

        Returns:
            str: 错误信息，None 表示验证通过
        """
        if not self.parameters:
            return None

        required = self.parameters.get("required", [])
        for req_field in required:
            if req_field not in params:
                return f"缺少必需参数: {req_field}"

        properties = self.parameters.get("properties", {})
        for key, value in params.items():
            if key not in properties:
                # 忽略未定义的参数（更灵活）
                pass
            else:
                expected_type = properties[key].get("type")
                if expected_type == "string" and not isinstance(value, str):
                    return f"参数 {key} 必须是字符串"
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    return f"参数 {key} 必须是数字"
                elif expected_type == "boolean" and not isinstance(value, bool):
                    return f"参数 {key} 必须是布尔值"
                elif expected_type == "array" and not isinstance(value, list):
                    return f"参数 {key} 必须是数组"

        return None

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> SkillResult:
        """
        执行 Skill 的核心逻辑

        Args:
            params: 工具调用时传入的参数

        Returns:
            SkillResult: 执行结果
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name})>"
