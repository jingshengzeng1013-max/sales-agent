# -*- coding: utf-8 -*-
"""
招标搜索 Skill

提供招标项目的搜索功能，支持向量检索和关键词检索。
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

from ..base import BaseSkill, SkillResult

logger = logging.getLogger("agent.skills.search_tenders")


class SearchTendersSkill(BaseSkill):
    """
    招标搜索 Skill

    在招标库中搜索符合条件的项目，支持：
    - 按关键词搜索
    - 按产品筛选
    - 按省份/城市筛选
    - 按预算范围筛选
    - 排除已中标项目
    - 排序方式（相关性/时间）
    """

    name = "search_tenders"
    description = "在招标库中搜索招标项目，支持按产品、地区、预算等条件筛选。返回匹配的招标列表，每条包含项目名称、采购单位、预算金额、发布时间等关键信息。"
    category = "retrieval"

    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词，可以是产品名称、技术关键词或项目描述"
            },
            "top_k": {
                "type": "integer",
                "description": "返回结果数量，默认10条",
                "default": 10
            },
            "province": {
                "type": "string",
                "description": "省份筛选，如'北京'、'广东'，为空表示不限制"
            },
            "city": {
                "type": "string",
                "description": "城市筛选，精确匹配"
            },
            "min_budget": {
                "type": "number",
                "description": "最低预算金额（万元），如 100 表示 100 万元以上"
            },
            "max_budget": {
                "type": "number",
                "description": "最高预算金额（万元），如 500 表示 500 万元以下"
            },
            "exclude_won": {
                "type": "boolean",
                "description": "是否排除已中标的招标",
                "default": False
            },
            "sort_by": {
                "type": "string",
                "enum": ["score", "date"],
                "description": "排序方式：score=按相关性，date=按发布时间",
                "default": "score"
            }
        },
        "required": ["query"]
    }

    def __init__(self, retriever=None):
        super().__init__()
        self._retriever = retriever
        self._retriever_loaded = False

    def _get_retriever(self):
        """延迟加载 retriever"""
        if self._retriever is None and not self._retriever_loaded:
            try:
                import sys
                from pathlib import Path
                BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
                sys.path.append(str(BASE_DIR))

                from src.retrieval.retriever import DualRetriever
                self._retriever = DualRetriever(data_type="tender")
                self._retriever_loaded = True
                logger.info("招标检索器加载成功")
            except Exception as e:
                logger.error(f"加载招标检索器失败: {e}")
                self._retriever = None
        return self._retriever

    def execute(self, params: Dict[str, Any]) -> SkillResult:
        """
        执行招标搜索

        Args:
            params: {
                "query": str,           # 搜索关键词
                "top_k": int,          # 返回数量
                "province": str,        # 省份筛选
                "min_budget": float,   # 最低预算
                "max_budget": float,   # 最高预算
                "exclude_won": bool,    # 排除已中标
                "sort_by": str          # 排序方式
            }

        Returns:
            SkillResult: {
                "success": bool,
                "data": {
                    "count": int,           # 结果数量
                    "results": [             # 结果列表
                        {
                            "tender_id": str,
                            "project_name": str,
                            "buyer_name": str,
                            "budget_amount": float,
                            "publish_date": str,
                            "score": float,
                            ...
                        }
                    ]
                }
            }
        """
        try:
            retriever = self._get_retriever()
            if retriever is None:
                return SkillResult(
                    success=False,
                    error="招标检索器未初始化，请确保索引已构建"
                )

            # 提取参数
            query = params.get("query", "")
            top_k = params.get("top_k", 10)
            province = params.get("province")
            city = params.get("city")
            min_budget = params.get("min_budget")
            max_budget = params.get("max_budget")
            exclude_won = params.get("exclude_won", False)
            sort_by = params.get("sort_by", "score")

            # 构建查询参数字典
            search_params = {
                "query": query,
                "top_k": top_k,
                "sort_by": sort_by,
            }

            if province:
                search_params["province"] = province
            if exclude_won:
                search_params["exclude_won"] = True

            # 执行搜索
            results = retriever.search(**search_params)

            # 后处理：预算筛选
            if min_budget is not None or max_budget is not None:
                filtered_results = []
                for r in results:
                    budget = r.get("data", {}).get("budget_amount", 0)
                    # budget 单位是元，min_budget/max_budget 单位是万元
                    budget_wan = budget / 10000 if budget else 0

                    if min_budget is not None and budget_wan < min_budget:
                        continue
                    if max_budget is not None and budget_wan > max_budget:
                        continue

                    filtered_results.append(r)
                results = filtered_results

            # 后处理：城市筛选
            if city:
                results = [
                    r for r in results
                    if city in (r.get("data", {}).get("city") or "")
                ]

            # 格式化结果
            formatted_results = []
            for r in results:
                data = r.get("data", {})
                formatted_results.append({
                    "tender_id": r.get("tender_id", ""),
                    "project_name": data.get("project_name", ""),
                    "buyer_name": data.get("buyer_name_std", ""),
                    "province": data.get("province", ""),
                    "city": data.get("city", ""),
                    "budget_amount": data.get("budget_amount", 0),
                    "budget_display": f"{data.get('budget_amount', 0) / 10000:.2f}万元" if data.get('budget_amount') else "未知",
                    "publish_date": data.get("publish_date", "")[:10] if data.get("publish_date") else "",
                    "score": r.get("score", 0),
                    "summary": data.get("content_summary", "")[:200] if data.get("content_summary") else "",
                })

            logger.info(f"搜索完成，查询={query}，结果数={len(formatted_results)}")

            return SkillResult(
                success=True,
                data={
                    "count": len(formatted_results),
                    "results": formatted_results,
                    "query": query,
                    "filters": {
                        "province": province,
                        "city": city,
                        "min_budget": min_budget,
                        "max_budget": max_budget,
                        "exclude_won": exclude_won
                    }
                },
                message=f"找到 {len(formatted_results)} 条匹配的招标"
            )

        except Exception as e:
            logger.exception(f"招标搜索异常: {e}")
            return SkillResult(
                success=False,
                error=f"搜索异常: {str(e)}"
            )
