# -*- coding: utf-8 -*-
"""
Agent Skill 模块

提供模块化的工具注册和管理架构，每个 Skill 独立实现，可插拔。
"""

from .base import BaseSkill, SkillResult
from .registry import SkillRegistry, get_registry

# 导出公共接口
__all__ = [
    'BaseSkill',
    'SkillResult',
    'SkillRegistry',
    'get_registry',
]
