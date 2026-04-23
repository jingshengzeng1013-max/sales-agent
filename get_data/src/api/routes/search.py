# -*- coding: utf-8 -*-
"""搜索路由"""

import json
from fastapi import APIRouter

from schemas.tender import SearchRequest, SearchResponse, TenderListItem
from services.db_service import get_tenders_list

router = APIRouter(prefix="/search", tags=["搜索"])


@router.post("", response_model=SearchResponse)
async def search_tenders(request: SearchRequest):
    """搜索招标项目"""
    offset = (request.page - 1) * request.page_size

    items, total = get_tenders_list(
        keyword=request.keyword,
        announce_type=request.announce_type,
        province=request.province,
        city=request.city,
        min_budget=request.min_budget,
        max_budget=request.max_budget,
        min_score=request.min_score,
        start_date=request.start_date,
        end_date=request.end_date,
        offset=offset,
        limit=request.page_size
    )

    return SearchResponse(
        total=total,
        page=request.page,
        page_size=request.page_size,
        items=items
    )


@router.get("/filters")
async def get_search_filters():
    """获取搜索筛选选项"""
    from services.db_service import get_announce_types, get_provinces

    announce_types = get_announce_types()
    provinces = get_provinces()

    return {
        "announce_types": announce_types,
        "provinces": provinces
    }
