# -*- coding: utf-8 -*-
"""招标相关路由"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional

from schemas.tender import (
    TenderDetail,
    TenderListItem,
    ChunkData
)
from services.db_service import (
    get_tender_by_id,
    get_structured_by_tender_id,
    get_chunks_by_tender_id
)

router = APIRouter(prefix="/tenders", tags=["招标项目"])


@router.get("/{tender_id}", response_model=TenderDetail)
async def get_tender_detail(tender_id: int):
    """获取招标项目详情"""
    tender = get_tender_by_id(tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail="招标项目不存在")

    structured = get_structured_by_tender_id(tender_id)

    # 解析附件 URL 数量
    attachment_count = 0
    if tender.get("attachment_urls"):
        try:
            urls = json.loads(tender["attachment_urls"])
            attachment_count = len(urls) if isinstance(urls, list) else 0
        except:
            pass

    # 构建响应
    result = {
        **tender,
        "structured": structured,
        "attachment_count": attachment_count
    }

    return result


@router.get("/{tender_id}/chunks", response_model=List[ChunkData])
async def get_tender_chunks(tender_id: int):
    """获取招标项目的 RAG 分块"""
    chunks = get_chunks_by_tender_id(tender_id)
    return chunks
