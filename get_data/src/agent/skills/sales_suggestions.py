# -*- coding: utf-8 -*-
"""
销售建议 Skill

利用 LLM 生成销售切入点建议。
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

from ..base import BaseSkill, SkillResult

logger = logging.getLogger("agent.skills.sales_suggestions")


class SalesSuggestionsSkill(BaseSkill):
    """
    销售建议 Skill

    基于项目信息和客户画像，生成专业的销售切入点建议。
    输出包含：
    - 需求匹配度分析
    - 竞争策略建议
    - 关键切入点
    - 风险提示
    """

    name = "generate_sales_suggestions"
    description = "基于项目需求和客户画像，生成专业的销售切入点建议。包括需求匹配度分析、竞争策略建议、关键切入点和风险提示。"
    category = "analysis"

    parameters = {
        "type": "object",
        "properties": {
            "project_data": {
                "type": "object",
                "description": "项目数据，包含项目名称、采购单位、预算金额、内容摘要、技术要点、应用场景、产品关键词等"
            },
            "customer_name": {
                "type": "string",
                "description": "客户名称（可选，用于关联客户画像）"
            },
            "style": {
                "type": "string",
                "enum": ["professional", "concise", "detailed"],
                "description": "建议风格：professional=专业简洁，concise=简明扼要，detailed=详细全面",
                "default": "professional"
            }
        },
        "required": ["project_data"]
    }

    def __init__(self, advisor=None):
        super().__init__()
        self._advisor = advisor

    def _get_advisor(self):
        """延迟加载 SalesAdvisor"""
        if self._advisor is None:
            try:
                import sys
                from pathlib import Path
                BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
                sys.path.append(str(BASE_DIR))

                from src.analysis.sales_advisor import SalesAdvisor
                self._advisor = SalesAdvisor(use_cache=True)
                logger.info("销售建议引擎加载成功")
            except Exception as e:
                logger.error(f"加载销售建议引擎失败: {e}")
                self._advisor = None
        return self._advisor

    def execute(self, params: Dict[str, Any]) -> SkillResult:
        """
        生成销售建议

        Args:
            params: {
                "project_data": {
                    "project_name_std": str,
                    "buyer_name": str,
                    "total_budget": float,
                    "content_summary": str,
                    "technical_requirements_summary": str,
                    "application_scenario": str,
                    "product_keywords": List[str]
                },
                "customer_name": str,
                "style": str
            }

        Returns:
            SkillResult: {
                "success": bool,
                "data": {
                    "suggestions": str,    # Markdown 格式的建议
                    "project_name": str,
                    "customer_name": str,
                    "cached": bool          # 是否使用缓存
                }
            }
        """
        try:
            advisor = self._get_advisor()
            if advisor is None:
                return SkillResult(
                    success=False,
                    error="销售建议引擎未初始化"
                )

            project_data = params.get("project_data", {})
            customer_name = params.get("customer_name")
            style = params.get("style", "professional")

            if not project_data:
                return SkillResult(
                    success=False,
                    error="缺少项目数据"
                )

            # 获取客户画像（如果提供了客户名）
            customer_profile = None
            if customer_name:
                try:
                    from pathlib import Path
                    import json
                    BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
                    profile_path = BASE_DIR / "data" / "output" / "customer" / "customer_profiles.jsonl"

                    if profile_path.exists():
                        with open(profile_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                profile = json.loads(line.strip())
                                if profile.get("customer_name") == customer_name:
                                    customer_profile = profile
                                    break
                except Exception as e:
                    logger.warning(f"加载客户画像失败: {e}")

            # 生成建议
            suggestions = advisor.generate_suggestions(
                project_data=project_data,
                customer_profile=customer_profile,
                customer_name=customer_name
            )

            # 检查是否使用了缓存（通过 advisor 的日志判断）
            # 这里简化处理，实际可以通过修改 advisor 返回额外信息
            cached = False

            return SkillResult(
                success=True,
                data={
                    "suggestions": suggestions,
                    "project_name": project_data.get("project_name_std", ""),
                    "customer_name": customer_name or "",
                    "style": style,
                    "cached": cached
                },
                message="销售建议生成成功"
            )

        except Exception as e:
            logger.exception(f"生成销售建议异常: {e}")
            return SkillResult(
                success=False,
                error=f"生成建议异常: {str(e)}"
            )


class ProjectAnalysisSkill(BaseSkill):
    """
    项目分析 Skill

    对招标项目进行深度分析，评估机会价值和竞争态势。
    """

    name = "analyze_project"
    description = "对招标项目进行深度分析，包括项目需求解读、机会评分、竞争态势分析和跟进建议。"
    category = "analysis"

    parameters = {
        "type": "object",
        "properties": {
            "project_data": {
                "type": "object",
                "description": "项目数据"
            },
            "include_competitors": {
                "type": "boolean",
                "description": "是否分析竞争对手",
                "default": True
            }
        },
        "required": ["project_data"]
    }

    def execute(self, params: Dict[str, Any]) -> SkillResult:
        """分析项目"""
        try:
            project_data = params.get("project_data", {})
            include_competitors = params.get("include_competitors", True)

            if not project_data:
                return SkillResult(
                    success=False,
                    error="缺少项目数据"
                )

            # 基本分析
            analysis = {
                "project_name": project_data.get("project_name_std", ""),
                "buyer_name": project_data.get("buyer_name", ""),
                "budget": project_data.get("total_budget", 0),
                "opportunity_score": project_data.get("opportunity_score", 0),
                "product_keywords": project_data.get("product_keywords", []),
                "technical_summary": project_data.get("technical_requirements_summary", ""),
                "application_scenario": project_data.get("application_scenario", "")
            }

            # 机会评估
            opportunity_level = "高"
            if analysis["opportunity_score"] < 60:
                opportunity_level = "低"
            elif analysis["opportunity_score"] < 80:
                opportunity_level = "中"

            analysis["opportunity_level"] = opportunity_level

            # 预算评估
            budget_wan = analysis["budget"] / 10000 if analysis["budget"] else 0
            if budget_wan >= 500:
                analysis["budget_level"] = "大额"
            elif budget_wan >= 100:
                analysis["budget_level"] = "中等"
            else:
                analysis["budget_level"] = "小额"

            return SkillResult(
                success=True,
                data=analysis,
                message=f"项目分析完成，机会等级：{opportunity_level}"
            )

        except Exception as e:
            logger.exception(f"项目分析异常: {e}")
            return SkillResult(
                success=False,
                error=f"分析异常: {str(e)}"
            )
