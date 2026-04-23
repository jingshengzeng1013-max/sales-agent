# -*- coding: utf-8 -*-
"""
FastAPI 服务端：打通数据到前端 demo.html 的全链路
"""

import os
import sys
import json
import sqlite3
import logging
import numpy as np
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path

# 将项目根目录添加到 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# 配置日志
LOG_DIR = BASE_DIR / "logs" / "api_server"
if not LOG_DIR.exists():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

log_filename = f"api_server_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
log_path = LOG_DIR / log_filename

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("api_server")

from src.config import DB_PATH, DATA_DIR
from src.retrieval.retriever import DualRetriever
from src.utils.jsonl_helper import load_jsonl
from src.analysis.sales_advisor import SalesAdvisor
from src.integration.wechat_service import get_wechat_service, WeChatUser

app = FastAPI(title="销售情报系统 API", description="打通数据到前端的检索与展示服务")

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化检索器
logger.info("正在初始化双路检索器...")
product_retriever = DualRetriever(data_type="product")
tender_retriever = DualRetriever(data_type="tender")
sales_advisor = SalesAdvisor()

# 加载客户画像数据 (全量)
logger.info("正在加载客户画像数据...")
CUSTOMER_PROFILE_PATH = DATA_DIR / "output" / "customer" / "customer_profiles.jsonl"
customer_profiles_dict = {}  # 按名称索引
customer_profiles_by_code = {}  # 按信用代码索引
if CUSTOMER_PROFILE_PATH.exists():
    try:
        profiles = load_jsonl(str(CUSTOMER_PROFILE_PATH))
        for p in profiles:
            name = p.get('customer_name')
            code = p.get('customer_id') or p.get('basic_info', {}).get('credit_code', '')
            if name:
                customer_profiles_dict[name] = p
            if code:
                customer_profiles_by_code[code] = p
        logger.info(f"成功加载 {len(customer_profiles_dict)} 个客户画像")
    except Exception as e:
        logger.error(f"加载客户画像失败: {e}")

# 挂载静态文件目录 (webapp/static 下存放 demo.html 等)
static_dir = BASE_DIR / "webapp" / "static"
if not static_dir.exists():
    static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# --- 数据模型 ---

class SearchTendersRequest(BaseModel):
    product_id: str
    target_type: Optional[str] = "tender" # "tender" or "customer"
    top_k: Optional[int] = 20
    min_score: Optional[float] = 0.0
    use_vector: Optional[bool] = True
    use_bm25: Optional[bool] = True
    vector_weight: Optional[float] = 0.5
    bm25_weight: Optional[float] = 0.5
    province: Optional[str] = None
    notice_type: Optional[str] = None
    exclude_won: Optional[bool] = False
    sort_by: Optional[str] = "score" # "score" or "date"
    client_value_weight: Optional[float] = 0.0

# --- API 路由 ---

@app.get("/")
async def root():
    return {
        "status": "online",
        "demo_page": "/static/demo.html",
        "api_docs": "/docs"
    }

@app.get("/api/retrieval/product-options")
async def get_product_options():
    """获取产品下拉列表选项"""
    rows = []
    for p in product_retriever.raw_data:
        rows.append({
            "id": p.get("uuid") or p.get("id"),
            "name": p.get("name"),
            "description": p.get("description")
        })
    return {"rows": rows}

@app.post("/api/retrieval/search-tenders")
async def search_tenders(req: SearchTendersRequest):
    """按产品检索标讯 (满足 demo.html 需求)"""
    # 1. 查找产品
    product = product_retriever.data_dict.get(str(req.product_id))
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {req.product_id} not found")
    
    # 2. 获取检索参数
    query_text = product.get('embedded_content') or f"{product.get('name')} {product.get('description')}"
    query_vector = product.get('embedding')
    if query_vector:
        query_vector = np.array([query_vector]).astype('float32')
    
    logger.info(f"[API] 正在为产品 [{product.get('name')}] 执行混合检索...")
    
    # 3. 执行检索
    results = tender_retriever.hybrid_search(
        query_text, 
        top_k=req.top_k, 
        query_vector=query_vector,
        vector_weight=req.vector_weight,
        bm25_weight=req.bm25_weight,
        province=req.province,
        notice_type=req.notice_type,
        aggregate_by_project=True, # 启用项目汇总
        exclude_won=req.exclude_won,
        sort_by=req.sort_by,
        client_value_weight=req.client_value_weight
    )
    
    # 4. 组装返回结果
    formatted_results = []
    for res in results:
        if res['score'] < req.min_score:
            continue
            
        item = res['data']
        # 适配项目汇总后的数据结构
        is_aggregated = res.get('is_aggregated', False)
        
        if is_aggregated:
            # 项目汇总模式
            formatted_results.append({
                "tender_id": res['id'],
                "score": res['score'],
                "vector_score": res.get('vector_score', 0.0), # 现在有了平均分数
                "bm25_score": res.get('bm25_score', 0.0),
                "bm25_norm_score": res.get('bm25_norm_score', 0.0),
                "rrf_raw_score": res['rrf_raw_score'],
                "is_aggregated": True,
                "match_count": res.get('match_count', 1),
                "data": {
                    "buyer_name_std": item.get('buyer_name', '未知单位'),
                    "project_name": item.get('project_name_std'),
                    "status": item.get('status', '进行中'),
                    "province": item.get('province', ''),
                    "city": item.get('city', ''),
                    "budget_amount": item.get('total_budget'),
                    "budget_unit": "元",
                    "winning_info": item.get('winning_info'),
                    "events": item.get('events', []),
                    # 使用第一个文件的抽取结果
                    "content_summary": item.get('content_summary'),
                    "technical_requirements_summary": item.get('technical_requirements_summary'),
                    "application_scenario": item.get('application_scenario'),
                    "opportunity_score": item.get('opportunity_score'),
                    "opportunity_reason": item.get('opportunity_reason'),
                    "contact_person": item.get('contact_person'),
                    "contact_phone": item.get('contact_phone'),
                    "product_keywords": item.get('product_keywords', []),
                    "buyer_profile_summary": item.get('buyer_profile_summary'),
                    # 兼容旧字段
                    "document_preview": f"项目: {item.get('project_name_std')} | 状态: {item.get('status')} | 包含 {len(item.get('events', []))} 条相关公告",
                    "detail_url": item.get('events', [{}])[0].get('url', '#'),
                    "publish_date": item.get('latest_publish_date') or item.get('publish_date') or '未知时间',
                }
            })
        else:
            # 原始公告模式 (兜底)
            formatted_results.append({
                "tender_id": res['id'],
                "score": res['score'],
                "vector_score": res.get('vector_score', 0.0),
                "bm25_score": res.get('bm25_score', 0.0),
                "bm25_norm_score": res.get('bm25_norm_score', 0.0),
                "rrf_raw_score": res['rrf_raw_score'],
                "is_aggregated": False,
                "data": {
                    "buyer_name_std": item.get('buyer_name_std', '未知单位'),
                    "document_preview": f"采购项目: {item.get('project_name')} | 需求: {item.get('application_scenario', '暂无')}",
                    "detail_url": item.get('source_url') or item.get('notice_url') or '#',
                    "project_name": item.get('project_name'),
                    "publish_date": item.get('publish_date', '未知时间'),
                    "technical_requirements_summary": item.get('technical_requirements_summary', ''),
                    "product_keywords": item.get('product_keywords', []),
                    "province": item.get('province', ''),
                    "city": item.get('city', ''),
                    "budget_amount": item.get('budget_amount'),
                    "budget_unit": item.get('budget_unit', '元'),
                    "application_scenario": item.get('application_scenario', ''),
                    "opportunity_score": item.get('opportunity_score'),
                    "opportunity_reason": item.get('opportunity_reason', ''),
                    "winning_bidder": item.get('winning_bidder'),
                    "winning_amount": item.get('winning_amount'),
                    "content_summary": item.get('content_summary'),
                    "contact_person": item.get('contact_person'),
                    "contact_phone": item.get('contact_phone')
                }
            })
        
    return {
        "results": formatted_results,
        "query": query_text,
        "query_source": "product",
        "product_id": req.product_id,
        "product_info": {
            **product,
            "query_preview": query_text[:200] + "..." if len(query_text) > 200 else query_text
        }
    }

@app.get("/api/customer/profile/{customer_name}")
async def get_customer_profile(customer_name: str):
    """获取指定客户的详细画像（支持名称或信用代码）"""
    # 先按名称查找
    profile = customer_profiles_dict.get(customer_name)
    # 再按信用代码查找
    if not profile and customer_name in customer_profiles_by_code:
        profile = customer_profiles_by_code[customer_name]
    if not profile:
        raise HTTPException(status_code=404, detail=f"Customer profile for '{customer_name}' not found")
    return profile


@app.get("/api/customers")
async def list_customers(
    page: int = Query(1, description="页码", ge=1),
    size: int = Query(20, description="每页条数", ge=1, le=100),
    search: Optional[str] = Query(None, description="搜索关键词（客户名称）"),
    customer_type: Optional[str] = Query(None, description="客户类型筛选：tender/crm/all"),
):
    """
    获取客户列表（支持分页和搜索）

    - page: 页码
    - size: 每页条数
    - search: 客户名称搜索
    - customer_type: tender=政府客户, crm=企业客户, all=全部
    """
    all_profiles = list(customer_profiles_dict.values())

    # 筛选
    filtered = []
    for p in all_profiles:
        # 名称搜索
        if search:
            name = p.get('customer_name', '')
            if search.lower() not in name.lower():
                continue

        # 类型筛选
        if customer_type == 'tender':
            if not (p.get('has_tender_data') or p.get('demand_profile', {}).get('tech_keywords')):
                continue
        elif customer_type == 'crm':
            if not (p.get('has_crm_data') or p.get('crm_history', {}).get('opportunities') or p.get('crm_history', {}).get('leads')):
                continue

        filtered.append(p)

    # 排序（按名称）
    filtered.sort(key=lambda x: x.get('customer_name', ''))

    # 分页
    total = len(filtered)
    start = (page - 1) * size
    end = start + size
    page_profiles = filtered[start:end]

    # 摘要信息
    results = []
    for p in page_profiles:
        vp = p.get('value_profile', {})
        results.append({
            "customer_name": p.get('customer_name', ''),
            "customer_id": p.get('customer_id', '') or p.get('basic_info', {}).get('credit_code', ''),
            "customer_type": '企业客户' if (p.get('has_crm_data') and not p.get('has_tender_data')) else '政府客户' if p.get('has_tender_data') else '未知',
            "province": p.get('basic_info', {}).get('province', ''),
            "city": p.get('basic_info', {}).get('city', ''),
            "tender_count": vp.get('tender_count', 0),
            "opportunity_count": vp.get('opportunity_count', 0),
            "lead_count": vp.get('lead_count', 0),
            "contact": p.get('contact_info', {}).get('contacts', [{}])[0].get('name', '') if p.get('contact_info', {}).get('contacts') else '',
            "phone": p.get('contact_info', {}).get('contacts', [{}])[0].get('phone', '') if p.get('contact_info', {}).get('contacts') else '',
        })

    return {
        "customers": results,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size if total > 0 else 0
    }


@app.get("/api/customers/all")
async def get_all_customers_simple():
    """获取所有客户的简要列表（用于下拉选择等）"""
    results = []
    for name, p in customer_profiles_dict.items():
        results.append({
            "customer_name": name,
            "customer_type": '企业客户' if (p.get('has_crm_data') and not p.get('has_tender_data')) else '政府客户' if p.get('has_tender_data') else '未知',
        })
    return {"customers": results}

class SalesSuggestionRequest(BaseModel):
    project_data: Dict[str, Any]
    customer_name: Optional[str] = None


class DirectSearchRequest(BaseModel):
    """直接搜索请求模型"""
    product_id: str = Query(..., description="产品ID（从产品库选择）")
    top_k: int = Query(10, description="返回结果数量", ge=1, le=100)
    use_vector: bool = Query(True, description="是否使用向量检索")
    use_bm25: bool = Query(True, description="是否使用BM25关键词检索")
    vector_weight: float = Query(0.5, description="向量检索权重", ge=0.0, le=1.0)
    bm25_weight: float = Query(0.5, description="BM25检索权重", ge=0.0, le=1.0)
    province: Optional[str] = Query(None, description="省份筛选，如'北京'、'广东'")
    city: Optional[str] = Query(None, description="城市筛选")
    min_budget: Optional[float] = Query(None, description="最低预算金额（万元）")
    max_budget: Optional[float] = Query(None, description="最高预算金额（万元）")
    exclude_won: bool = Query(False, description="是否排除已中标的招标")
    sort_by: str = Query("score", description="排序方式：score=按相关性，date=按发布时间")
    client_value_weight: float = Query(0.0, description="客户价值权重", ge=0.0, le=1.0)
    aggregate_by_project: bool = Query(True, description="是否按项目汇总")


@app.post("/api/retrieval/direct-search")
async def direct_search(req: DirectSearchRequest):
    """
    直接搜索接口（供后端对接使用）

    根据产品ID从产品库选择产品，检索匹配的招标项目，所有参数均可配置。

    **注意**: min_budget 和 max_budget 单位为万元（如 100 表示 100万元）

    返回数据结构：
    - results: 招标列表
    - total: 原始结果总数
    - product_info: 产品信息
    - scores: 各结果的分项得分（vector_score, bm25_score, rrf_raw_score）
    """
    # 1. 查找产品
    product = product_retriever.data_dict.get(str(req.product_id))
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {req.product_id} not found")

    # 2. 获取产品检索文本
    query_text = product.get('embedded_content') or f"{product.get('name')} {product.get('description')}"
    logger.info(f"[API] 直接搜索: product_id={req.product_id}, name={product.get('name')}, top_k={req.top_k}")

    # 3. 执行混合检索
    results = tender_retriever.hybrid_search(
        query_text=query_text,
        top_k=req.top_k * 3 if req.aggregate_by_project else req.top_k,  # 预留足够结果用于汇总
        query_vector=None,  # 直接搜索不使用预设向量
        use_vector=req.use_vector,
        use_bm25=req.use_bm25,
        vector_weight=req.vector_weight,
        bm25_weight=req.bm25_weight,
        province=req.province,
        city=req.city,
        notice_type=None,
        aggregate_by_project=req.aggregate_by_project,
        exclude_won=req.exclude_won,
        sort_by=req.sort_by,
        client_value_weight=req.client_value_weight
    )

    # 2. 预算筛选（后处理）
    if req.min_budget is not None or req.max_budget is not None:
        filtered_results = []
        for res in results:
            budget = res.get('data', {}).get('total_budget') or res.get('data', {}).get('budget_amount', 0)
            budget_wan = budget / 10000 if budget else 0
            if req.min_budget is not None and budget_wan < req.min_budget:
                continue
            if req.max_budget is not None and budget_wan > req.max_budget:
                continue
            filtered_results.append(res)
        results = filtered_results

    # 3. 城市筛选（后处理）
    if req.city:
        results = [r for r in results if req.city in (r.get('data', {}).get('city') or "")]

    # 4. 限制返回数量
    results = results[:req.top_k]

    # 5. 格式化结果
    formatted_results = []
    for res in results:
        item = res.get('data', {})
        is_aggregated = res.get('is_aggregated', False)

        tender_entry = {
            "tender_id": res.get('id', ''),
            "score": round(res.get('score', 0), 4),
            "is_aggregated": is_aggregated,
            "scores": {
                "vector_score": round(res.get('vector_score', 0), 4) if req.use_vector else None,
                "bm25_score": round(res.get('bm25_score', 0), 4) if req.use_bm25 else None,
                "rrf_raw_score": round(res.get('rrf_raw_score', 0), 4),
            },
            "data": {
                "buyer_name_std": item.get('buyer_name_std') or item.get('buyer_name', '未知单位'),
                "project_name_std": item.get('project_name_std') or item.get('project_name', ''),
                "province": item.get('province', ''),
                "city": item.get('city', ''),
                "budget_amount": item.get('total_budget') or item.get('budget_amount', 0),
                "budget_display": f"{((item.get('total_budget') or item.get('budget_amount', 0)) / 10000):.2f}万元" if item.get('total_budget') or item.get('budget_amount') else "未知",
                "publish_date": (item.get('latest_publish_date') or item.get('publish_date') or '未知时间')[:10],
                "content_summary": item.get('content_summary', ''),
                "technical_requirements_summary": item.get('technical_requirements_summary', ''),
                "application_scenario": item.get('application_scenario', ''),
                "product_keywords": item.get('product_keywords', []),
                "opportunity_score": item.get('opportunity_score', 0),
                "opportunity_reason": item.get('opportunity_reason', ''),
                "contact_person": item.get('contact_person', ''),
                "contact_phone": item.get('contact_phone', ''),
                "status": item.get('status', '进行中'),
                "winning_info": item.get('winning_info'),
                "detail_url": item.get('events', [{}])[0].get('url', '#') if is_aggregated else (item.get('source_url') or item.get('notice_url') or '#'),
            }
        }

        if is_aggregated:
            tender_entry["match_count"] = res.get('match_count', 1)
            tender_entry["data"]["latest_publish_date"] = item.get('latest_publish_date', '')

        formatted_results.append(tender_entry)

    return {
        "success": True,
        "query": query_text,
        "total": len(formatted_results),
        "results": formatted_results,
        "product_info": {
            "product_id": product.get('uuid') or product.get('id'),
            "name": product.get('name'),
            "description": product.get('description'),
            "query_preview": query_text[:200] + "..." if len(query_text) > 200 else query_text
        },
        "params": {
            "use_vector": req.use_vector,
            "use_bm25": req.use_bm25,
            "vector_weight": req.vector_weight,
            "bm25_weight": req.bm25_weight,
            "province": req.province,
            "city": req.city,
            "min_budget": req.min_budget,
            "max_budget": req.max_budget,
            "exclude_won": req.exclude_won,
            "sort_by": req.sort_by,
            "client_value_weight": req.client_value_weight,
            "aggregate_by_project": req.aggregate_by_project,
        }
    }


@app.post("/api/analysis/sales-suggestions")
async def get_sales_suggestions(req: SalesSuggestionRequest):
    """获取 AI 销售建议"""
    customer_profile = None
    if req.customer_name:
        customer_profile = customer_profiles_dict.get(req.customer_name)
    
    suggestions = sales_advisor.generate_suggestions(req.project_data, customer_profile, req.customer_name)
    return {"suggestions": suggestions}


# --- 微信客服推送接口 ---

class WeChatTemplateMessageRequest(BaseModel):
    """微信模板消息请求"""
    openid: str = Query(..., description="接收消息的用户openid")
    first: str = Query(..., description="模板数据：首行")
    keyword1: str = Query(..., description="模板数据：关键词1")
    keyword2: str = Query(..., description="模板数据：关键词2")
    keyword3: str = Query(..., description="模板数据：关键词3")
    remark: str = Query("点击查看详情", description="模板数据：备注")
    template_id: Optional[str] = Query(None, description="模板消息ID")
    url: Optional[str] = Query(None, description="点击跳转URL")


class WeChatBroadcastRequest(BaseModel):
    """微信广播请求"""
    user_openids: List[str] = Query(..., description="接收消息的用户openid列表")
    first: str = Query(..., description="模板数据：首行")
    keyword1: str = Query(..., description="模板数据：关键词1")
    keyword2: str = Query(..., description="模板数据：关键词2")
    keyword3: str = Query(..., description="模板数据：关键词3")
    remark: str = Query("点击查看详情", description="模板数据：备注")
    template_id: Optional[str] = Query(None, description="模板消息ID")
    url: Optional[str] = Query(None, description="点击跳转URL")


@app.get("/api/wechat/users")
async def get_wechat_users(
    page: int = Query(1, description="页码", ge=1),
    size: int = Query(10, description="每页条数", ge=1, le=100),
    subscribe: Optional[int] = Query(None, description="关注状态：1=已关注，0=已取关")
):
    """
    查询微信用户列表

    对接外部客服系统，分页获取已关注用户信息。
    """
    wechat_service = get_wechat_service()
    result = await wechat_service.get_users(page=page, size=size, subscribe=subscribe)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    # 转换用户对象为字典
    users_data = []
    for user in result.get("users", []):
        users_data.append({
            "openid": user.openid,
            "nickname": user.nickname,
            "sex": user.sex,
            "province": user.province,
            "city": user.city,
            "subscribe": user.subscribe,
            "subscribe_time": user.subscribe_time,
            "last_interact_time": user.last_interact_time,
            "phone": user.phone,
            "real_name": user.real_name,
            "is_subscribed": user.is_subscribed
        })

    return {
        "users": users_data,
        "total": result.get("total", 0),
        "size": result.get("size", size),
        "current": result.get("current", page),
        "pages": result.get("pages", 1)
    }


@app.post("/api/wechat/template/send")
async def send_wechat_template_message(req: WeChatTemplateMessageRequest):
    """
    发送微信模板消息（单用户）

    向指定用户发送模板消息，不受48小时客服消息窗口限制。
    """
    wechat_service = get_wechat_service()

    result = await wechat_service.send_template_message(
        openid=req.openid,
        data={
            "first": req.first,
            "keyword1": req.keyword1,
            "keyword2": req.keyword2,
            "keyword3": req.keyword3,
            "remark": req.remark
        },
        template_id=req.template_id,
        url=req.url
    )

    return {
        "success": result.success,
        "errcode": result.errcode,
        "errmsg": result.errmsg
    }


@app.post("/api/wechat/template/broadcast")
async def broadcast_wechat_template_message(req: WeChatBroadcastRequest):
    """
    广播微信模板消息（多用户）

    向多个用户同时发送相同的模板消息。
    """
    wechat_service = get_wechat_service()

    # 构建用户列表
    users = [WeChatUser({"openid": oid, "subscribe": 1}) for oid in req.user_openids]

    # 广播发送
    result = await wechat_service.broadcast_tender_notification(
        users=users,
        project_name=req.first,
        buyer_name=req.keyword1,
        budget=req.keyword2,
        publish_date=req.keyword3,
        detail_url=req.url,
        template_id=req.template_id
    )

    return {
        "success": True,
        **result
    }


@app.post("/api/wechat/tender-notify")
async def notify_tender_update(
    first: str = Query(..., description="通知标题/首行"),
    keyword1: str = Query(..., description="采购单位"),
    keyword2: str = Query(..., description="预算金额"),
    keyword3: str = Query(..., description="发布时间"),
    url: Optional[str] = Query(None, description="跳转链接"),
    template_id: Optional[str] = Query(None, description="模板ID"),
    page: int = Query(1, description="从第几页用户开始通知"),
    size: int = Query(50, description="每页通知多少用户")
):
    """
    招标更新通知（广播所有已关注用户）

    当有新招标项目时，广播通知所有已关注用户。
    """
    wechat_service = get_wechat_service()

    total_success = 0
    total_fail = 0
    all_errors = []

    # 分页获取已关注用户并发送
    current_page = page
    while True:
        result = await wechat_service.get_users(page=current_page, size=size, subscribe=1)
        users = result.get("users", [])

        if not users:
            break

        # 广播通知
        broadcast_result = await wechat_service.broadcast_tender_notification(
            users=users,
            project_name=first,
            buyer_name=keyword1,
            budget=keyword2,
            publish_date=keyword3,
            detail_url=url,
            template_id=template_id
        )

        total_success += broadcast_result["success_count"]
        total_fail += broadcast_result["fail_count"]
        all_errors.extend(broadcast_result.get("errors", []))

        # 检查是否还有下一页
        total_pages = result.get("pages", 1)
        if current_page >= total_pages:
            break
        current_page += 1

        # 防止无限循环
        if current_page > 100:
            break

    return {
        "success": True,
        "total_success": total_success,
        "total_fail": total_fail,
        "errors": all_errors[:20]  # 最多返回20条错误详情
    }

@app.get("/api/db/tables")
async def get_db_tables():
    """获取数据库表列表"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return {"tables": tables, "db_path": str(DB_PATH)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/db/table/{table_name}")
async def get_db_table_data(table_name: str, limit: int = 50, offset: int = 0):
    """获取指定表的数据"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取总数
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        total = cursor.fetchone()[0]
        
        # 获取列名
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        
        # 获取数据
        cursor.execute(f"SELECT * FROM {table_name} LIMIT ? OFFSET ?", (limit, offset))
        rows = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return {
            "columns": columns,
            "rows": rows,
            "total": total,
            "db_path": str(DB_PATH)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/retrieval/filter-options")
async def get_filter_options():
    """获取检索筛选选项 (地区、公告类型等)"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # 获取省份
        cursor.execute("SELECT DISTINCT province FROM tender_structured WHERE province IS NOT NULL AND province != '';")
        provinces = [row[0] for row in cursor.fetchall()]
        
        # 定义常见的公告类型 (基于业务理解)
        notice_types = ["招标公告", "中标公告", "成交结果公告", "竞争性谈判", "竞争性磋商", "单一来源", "变更公告"]
        
        conn.close()
        return {
            "provinces": sorted(provinces),
            "notice_types": notice_types
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    import uvicorn
    import subprocess
    import os

    # 自动获取本机 IP
    import socket
    def get_host_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip
    
    host_ip = get_host_ip()
    port = 8103

    # 自动清理端口
    if os.name == 'nt':  # Windows
        try:
            output = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True).decode()
            for line in output.strip().split('\n'):
                if not line.strip(): continue
                pid = line.strip().split()[-1]
                if pid != '0':
                    logger.info(f"[INFO] 正在清理端口 {port} 上的进程 PID: {pid}")
                    subprocess.run(f'taskkill /F /PID {pid}', shell=True)
        except subprocess.CalledProcessError:
            pass # 端口未被占用

    logger.info("\n" + "="*60)
    logger.info("FastAPI 服务启动中...")
    logger.info(f"本地访问地址: http://127.0.0.1:{port}/static/demo.html")
    logger.info(f"局域网访问地址: http://{host_ip}:{port}/static/demo.html")
    logger.info(f"API 文档地址: http://127.0.0.1:{port}/docs")
    logger.info("="*60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
