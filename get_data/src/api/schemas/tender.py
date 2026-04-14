# -*- coding: utf-8 -*-
"""招标数据 Pydantic 模型"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class TenderBase(BaseModel):
    """招标项目基础信息"""
    id: int
    project_name: str
    publish_date: Optional[str] = None
    detail_url: Optional[str] = None
    content: Optional[str] = None
    attachment_urls: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None


class StructuredData(BaseModel):
    """结构化抽取数据"""
    announce_type: Optional[str] = None
    buyer_name_std: Optional[str] = None
    agency_name_std: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    budget_raw: Optional[str] = None
    budget_amount: Optional[float] = None
    budget_unit: Optional[str] = None
    product_keywords: Optional[str] = None
    opportunity_score: Optional[int] = None
    opportunity_reason: Optional[str] = None
    next_action: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None


class TenderDetail(TenderBase):
    """招标项目详情（包含结构化数据）"""
    structured: Optional[StructuredData] = None
    attachment_count: int = 0


class TenderListItem(BaseModel):
    """招标列表项"""
    id: int
    project_name: str
    publish_date: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    announce_type: Optional[str] = None
    budget_amount: Optional[float] = None
    budget_unit: Optional[str] = None
    opportunity_score: Optional[int] = None
    buyer_name_std: Optional[str] = None


class ChunkData(BaseModel):
    """RAG 分块数据"""
    chunk_id: int
    tender_id: int
    chunk_type: str
    chunk_text: str
    chunk_order: Optional[int] = None
    metadata_json: Optional[str] = None


class SearchRequest(BaseModel):
    """搜索请求"""
    keyword: Optional[str] = None
    announce_type: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    min_budget: Optional[float] = None
    max_budget: Optional[float] = None
    min_score: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    page: int = 1
    page_size: int = 20


class SearchResponse(BaseModel):
    """搜索响应"""
    total: int
    page: int
    page_size: int
    items: List[TenderListItem]


class StatsOverview(BaseModel):
    """统计概览"""
    total_tenders: int
    total_structured: int
    total_chunks: int
    avg_opportunity_score: Optional[float] = None
    date_range: dict = {}


class StatsByProvince(BaseModel):
    """按省份统计"""
    province: str
    count: int


class StatsByType(BaseModel):
    """按公告类型统计"""
    announce_type: str
    count: int
