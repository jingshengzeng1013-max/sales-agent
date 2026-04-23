# -*- coding: utf-8 -*-
"""
Skill 注册中心

管理所有 Skill 的注册、查找和调用。
"""

import json
import logging
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path

from .base import BaseSkill, SkillResult

logger = logging.getLogger("agent.skills.registry")


class SkillRegistry:
    """
    Skill 注册中心

    管理所有可用 Skill，支持：
    - 注册/注销 Skill
    - 按名称查找 Skill
    - 批量获取 Skill schema
    - 执行 Skill 并返回结果
    - Skill 分类管理

    示例：
        registry = SkillRegistry()

        # 注册 Skill
        registry.register(MySkill())

        # 获取所有 schema（用于 LLM）
        schemas = registry.get_all_schemas()

        # 执行 Skill
        result = registry.execute("my_skill", {"param": "value"})
    """

    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
        self._categories: Dict[str, List[str]] = {}  # category -> skill_names

    def register(self, skill: BaseSkill, force: bool = False) -> bool:
        """
        注册一个 Skill

        Args:
            skill: BaseSkill 实例
            force: 如果已存在是否强制覆盖

        Returns:
            bool: 注册是否成功
        """
        if not isinstance(skill, BaseSkill):
            logger.error(f"只能注册 BaseSkill 子类实例，实际类型: {type(skill)}")
            return False

        if skill.name in self._skills and not force:
            logger.warning(f"Skill '{skill.name}' 已存在，使用 force=True 覆盖")
            return False

        self._skills[skill.name] = skill

        # 更新分类
        category = skill.category
        if category not in self._categories:
            self._categories[category] = []
        if skill.name not in self._categories[category]:
            self._categories[category].append(skill.name)

        logger.info(f"已注册 Skill: {skill.name} (category: {category})")
        return True

    def unregister(self, name: str) -> bool:
        """
        注销一个 Skill

        Args:
            name: Skill 名称

        Returns:
            bool: 注销是否成功
        """
        if name not in self._skills:
            logger.warning(f"Skill '{name}' 不存在")
            return False

        skill = self._skills.pop(name)

        # 从分类中移除
        category = skill.category
        if category in self._categories and name in self._categories[category]:
            self._categories[category].remove(name)

        logger.info(f"已注销 Skill: {name}")
        return True

    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """
        根据名称获取 Skill

        Args:
            name: Skill 名称

        Returns:
            BaseSkill 或 None
        """
        return self._skills.get(name)

    def execute(self, name: str, params: Dict[str, Any]) -> SkillResult:
        """
        执行一个 Skill

        Args:
            name: Skill 名称
            params: 执行参数

        Returns:
            SkillResult: 执行结果
        """
        skill = self.get_skill(name)
        if not skill:
            logger.error(f"尝试执行未注册的 Skill: {name}")
            return SkillResult(
                success=False,
                error=f"未知 Skill: {name}",
                message=f"可用的 Skill: {', '.join(self.list_skill_names())}"
            )

        # 参数验证
        validation_error = skill.validate_params(params)
        if validation_error:
            logger.warning(f"Skill {name} 参数验证失败: {validation_error}")
            return SkillResult(
                success=False,
                error=f"参数错误: {validation_error}"
            )

        # 执行
        try:
            logger.info(f"执行 Skill: {name}, 参数: {params}")
            result = skill.execute(params)
            return result
        except Exception as e:
            logger.exception(f"Skill {name} 执行异常")
            return SkillResult(
                success=False,
                error=f"执行异常: {str(e)}"
            )

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """
        获取所有 Skill 的 schema（用于 LLM function calling）

        Returns:
            list: schema 列表
        """
        return [skill.get_schema() for skill in self._skills.values()]

    def list_skill_names(self) -> List[str]:
        """获取所有已注册的 Skill 名称"""
        return list(self._skills.keys())

    def list_skills(self) -> List[BaseSkill]:
        """获取所有已注册的 Skill 实例"""
        return list(self._skills.values())

    def list_by_category(self, category: str) -> List[BaseSkill]:
        """获取指定分类的所有 Skill"""
        skill_names = self._categories.get(category, [])
        return [self._skills[name] for name in skill_names if name in self._skills]

    def get_categories(self) -> List[str]:
        """获取所有分类"""
        return list(self._categories.keys())

    def get_stats(self) -> Dict[str, Any]:
        """获取注册统计信息"""
        return {
            "total_skills": len(self._skills),
            "categories": {
                cat: len(skills) for cat, skills in self._categories.items()
            },
            "skills": [
                {
                    "name": s.name,
                    "category": s.category,
                    "description": s.description[:50] + "..." if len(s.description) > 50 else s.description
                }
                for s in self._skills.values()
            ]
        }

    def export_schemas(self, file_path: str):
        """导出所有 schema 到 JSON 文件（用于调试）"""
        schemas = self.get_all_schemas()
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(schemas, f, ensure_ascii=False, indent=2)
        logger.info(f"已导出 {len(schemas)} 个 Skill schema 到 {file_path}")

    def __len__(self) -> int:
        return len(self._skills)

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __repr__(self) -> str:
        return f"<SkillRegistry(skills={len(self._skills)})>"


# 全局注册表实例
_global_registry: Optional[SkillRegistry] = None


def get_registry() -> SkillRegistry:
    """
    获取全局注册表（单例模式）

    Returns:
        SkillRegistry: 全局注册表实例
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry


def register_skill(skill: BaseSkill, force: bool = False) -> bool:
    """
    快捷函数：向全局注册表注册 Skill

    Args:
        skill: BaseSkill 实例
        force: 如果已存在是否强制覆盖

    Returns:
        bool: 注册是否成功
    """
    return get_registry().register(skill, force)


def execute_skill(name: str, params: Dict[str, Any]) -> SkillResult:
    """
    快捷函数：执行全局注册表中的 Skill

    Args:
        name: Skill 名称
        params: 执行参数

    Returns:
        SkillResult: 执行结果
    """
    return get_registry().execute(name, params)


def get_all_schemas() -> List[Dict[str, Any]]:
    """快捷函数：获取全局注册表的所有 schema"""
    return get_registry().get_all_schemas()
