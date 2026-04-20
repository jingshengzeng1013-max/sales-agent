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
        sort_by=req.sort_by
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
