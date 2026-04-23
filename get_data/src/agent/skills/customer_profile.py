# -*- coding: utf-8 -*-
"""
客户画像 Skill

提供客户360度画像查询功能。
"""

import logging
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

from ..base import BaseSkill, SkillResult

logger = logging.getLogger("agent.skills.customer_profile")


class CustomerProfileSkill(BaseSkill):
    """
    客户画像 Skill

    查询客户的360度画像信息，包括：
    - 基础信息（地区、类型）
    - 价值评估（历史招标次数、总预算、平均评分）
    - 需求特征（技术关键词、应用场景）
    - 竞争态势（历史中标单位、中标率）
    - 联系方式
    """

    name = "get_customer_profile"
    description = "获取客户的360度画像信息，包括历史招标次数、采购偏好、竞争态势、联系方式等。用于评估客户价值和制定销售策略。"
    category = "retrieval"

    parameters = {
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string",
                "description": "客户/采购单位名称（支持模糊匹配）"
            },
            "detail_level": {
                "type": "string",
                "enum": ["summary", "full"],
                "description": "返回详情级别：summary=摘要，full=完整",
                "default": "summary"
            }
        },
        "required": ["customer_name"]
    }

    def __init__(self, profiles_path: Path = None):
        super().__init__()
        self._profiles_path = profiles_path
        self._profiles: Dict[str, Any] = {}
        self._loaded = False

    def _load_profiles(self):
        """延迟加载客户画像数据"""
        if self._loaded:
            return

        if self._profiles_path is None:
            # 默认路径
            BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
            self._profiles_path = BASE_DIR / "data" / "output" / "customer" / "customer_profiles.jsonl"

        if not self._profiles_path.exists():
            logger.warning(f"客户画像文件不存在: {self._profiles_path}")
            self._loaded = True
            return

        try:
            with open(self._profiles_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        profile = json.loads(line)
                        name = profile.get("customer_name", "")
                        if name:
                            self._profiles[name] = profile
                    except json.JSONDecodeError:
                        continue

            logger.info(f"加载了 {len(self._profiles)} 个客户画像")
        except Exception as e:
            logger.error(f"加载客户画像失败: {e}")

        self._loaded = True

    def _find_profile(self, customer_name: str) -> Optional[Dict[str, Any]]:
        """模糊匹配查找客户画像"""
        self._load_profiles()

        # 精确匹配
        if customer_name in self._profiles:
            return self._profiles[customer_name]

        # 模糊匹配（包含）
        customer_lower = customer_name.lower()
        for name, profile in self._profiles.items():
            if customer_lower in name.lower() or name.lower() in customer_lower:
                return profile

        return None

    def execute(self, params: Dict[str, Any]) -> SkillResult:
        """
        执行客户画像查询

        Args:
            params: {
                "customer_name": str,    # 客户名称
                "detail_level": str      # 详情级别
            }

        Returns:
            SkillResult: {
                "success": bool,
                "data": {
                    "customer_name": str,
                    "basic_info": {...},
                    "value_profile": {...},
                    "demand_profile": {...},
                    "competitive_landscape": {...},
                    "contact_info": {...}
                }
            }
        """
        try:
            customer_name = params.get("customer_name", "")
            detail_level = params.get("detail_level", "summary")

            if not customer_name:
                return SkillResult(
                    success=False,
                    error="缺少必需参数: customer_name"
                )

            profile = self._find_profile(customer_name)

            if profile is None:
                return SkillResult(
                    success=False,
                    error=f"未找到客户 '{customer_name}' 的画像数据"
                )

            # 根据详情级别返回数据
            if detail_level == "summary":
                # 返回摘要版本
                summary = {
                    "customer_name": profile.get("customer_name", ""),
                    "basic_info": {
                        "province": profile.get("basic_info", {}).get("province", ""),
                        "city": profile.get("basic_info", {}).get("city", "")
                    },
                    "value_profile": {
                        "tender_count": profile.get("value_profile", {}).get("tender_count", 0),
                        "total_budget": profile.get("value_profile", {}).get("total_budget", 0),
                        "avg_opportunity_score": profile.get("value_profile", {}).get("avg_opportunity_score", 0)
                    },
                    "demand_profile": {
                        "tech_keywords": profile.get("demand_profile", {}).get("tech_keywords", [])[:5],
                        "application_scenarios": profile.get("demand_profile", {}).get("application_scenarios", [])[:3]
                    },
                    "competitive_landscape": {
                        "past_winners": profile.get("competitive_landscape", {}).get("past_winners", [])[:5]
                    }
                }
                return SkillResult(
                    success=True,
                    data=summary,
                    message=f"找到客户 '{profile.get('customer_name')}' 的画像"
                )
            else:
                # 返回完整版本
                return SkillResult(
                    success=True,
                    data=profile,
                    message=f"找到客户 '{profile.get('customer_name')}' 的完整画像"
                )

        except Exception as e:
            logger.exception(f"客户画像查询异常: {e}")
            return SkillResult(
                success=False,
                error=f"查询异常: {str(e)}"
            )


class CustomerListSkill(BaseSkill):
    """
    客户列表 Skill

    获取所有客户列表，支持按价值、地区等筛选。
    """

    name = "list_customers"
    description = "获取客户列表，可按价值等级、地区等条件筛选。返回客户名称和基本统计信息。"
    category = "retrieval"

    parameters = {
        "type": "object",
        "properties": {
            "province": {
                "type": "string",
                "description": "省份筛选"
            },
            "min_tender_count": {
                "type": "integer",
                "description": "最少招标次数筛选"
            },
            "sort_by": {
                "type": "string",
                "enum": ["tender_count", "avg_score", "total_budget"],
                "description": "排序字段",
                "default": "tender_count"
            },
            "top_k": {
                "type": "integer",
                "description": "返回数量",
                "default": 20
            }
        },
        "required": []
    }

    def __init__(self, profiles_path: Path = None):
        super().__init__()
        self._profiles_path = profiles_path
        self._profiles: List[Dict[str, Any]] = []
        self._loaded = False

    def _load_profiles(self):
        """延迟加载客户画像数据"""
        if self._loaded:
            return

        if self._profiles_path is None:
            BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
            self._profiles_path = BASE_DIR / "data" / "output" / "customer" / "customer_profiles.jsonl"

        if not self._profiles_path.exists():
            logger.warning(f"客户画像文件不存在: {self._profiles_path}")
            self._loaded = True
            return

        try:
            with open(self._profiles_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        profile = json.loads(line)
                        self._profiles.append(profile)
                    except json.JSONDecodeError:
                        continue

            logger.info(f"加载了 {len(self._profiles)} 个客户画像")
        except Exception as e:
            logger.error(f"加载客户画像失败: {e}")

        self._loaded = True

    def execute(self, params: Dict[str, Any]) -> SkillResult:
        """获取客户列表"""
        try:
            self._load_profiles()

            province = params.get("province")
            min_tender_count = params.get("min_tender_count", 0)
            sort_by = params.get("sort_by", "tender_count")
            top_k = params.get("top_k", 20)

            # 筛选
            filtered = []
            for p in self._profiles:
                # 省份筛选
                if province:
                    p_province = p.get("basic_info", {}).get("province", "")
                    if province not in p_province:
                        continue

                # 招标次数筛选
                tender_count = p.get("value_profile", {}).get("tender_count", 0)
                if tender_count < min_tender_count:
                    continue

                filtered.append(p)

            # 排序
            if sort_by == "tender_count":
                filtered.sort(key=lambda x: x.get("value_profile", {}).get("tender_count", 0), reverse=True)
            elif sort_by == "avg_score":
                filtered.sort(key=lambda x: x.get("value_profile", {}).get("avg_opportunity_score", 0), reverse=True)
            elif sort_by == "total_budget":
                filtered.sort(key=lambda x: x.get("value_profile", {}).get("total_budget", 0), reverse=True)

            # 取前 top_k
            filtered = filtered[:top_k]

            # 格式化结果
            results = []
            for p in filtered:
                vp = p.get("value_profile", {})
                results.append({
                    "customer_name": p.get("customer_name", ""),
                    "province": p.get("basic_info", {}).get("province", ""),
                    "city": p.get("basic_info", {}).get("city", ""),
                    "tender_count": vp.get("tender_count", 0),
                    "total_budget": vp.get("total_budget", 0),
                    "avg_score": vp.get("avg_opportunity_score", 0)
                })

            return SkillResult(
                success=True,
                data={
                    "count": len(results),
                    "customers": results
                },
                message=f"找到 {len(results)} 个客户"
            )

        except Exception as e:
            logger.exception(f"客户列表查询异常: {e}")
            return SkillResult(
                success=False,
                error=f"查询异常: {str(e)}"
            )
