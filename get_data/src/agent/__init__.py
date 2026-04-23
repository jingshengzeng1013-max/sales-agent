# -*- coding: utf-8 -*-
"""
Agent 模块

提供 Agentic RAG 销售助手能力。
"""

from .sales_agent import SalesAgent, create_agent
from .skills import BaseSkill, SkillResult, SkillRegistry, get_registry

__all__ = [
    "SalesAgent",
    "create_agent",
    "BaseSkill",
    "SkillResult",
    "SkillRegistry",
    "get_registry",
]
