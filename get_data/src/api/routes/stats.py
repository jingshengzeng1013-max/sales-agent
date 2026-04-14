# -*- coding: utf-8 -*-
"""统计路由"""

from fastapi import APIRouter
from typing import List

from schemas.tender import StatsOverview, StatsByProvince, StatsByType
from services.db_service import (
    get_stats_overview as db_get_stats_overview,
    get_stats_by_province as db_get_stats_by_province,
    get_stats_by_type as db_get_stats_by_type
)

router = APIRouter(prefix="/stats", tags=["统计分析"])


@router.get("/overview", response_model=StatsOverview)
async def get_stats_overview():
    """获取统计概览"""
    return db_get_stats_overview()


@router.get("/by_province", response_model=List[StatsByProvince])
async def get_stats_by_province():
    """按省份统计"""
    return db_get_stats_by_province()


@router.get("/by_type", response_model=List[StatsByType])
async def get_stats_by_type():
    """按公告类型统计"""
    return db_get_stats_by_type()
