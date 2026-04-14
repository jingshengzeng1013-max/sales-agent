#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
get_data Web UI：FastAPI 托管静态页。
重构后的入口文件，具体逻辑已迁移至 webapp/router/ 目录下。
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

import contextlib
from fastapi import FastAPI, HTTPException
from starlette.requests import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import LOGS_WEBAPP_DIR
from webapp.router import system, retrieval, intel, db, crawl, extract, output

# 配置日志
logger = logging.getLogger("get_data.webapp")

def _configure_logging() -> None:
    level_name = os.environ.get("GET_DATA_WEB_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
    )
    LOGS_WEBAPP_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(LOGS_WEBAPP_DIR / "webapp.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(fh)

_configure_logging()

def _warmup():
    """启动时预热检索索引"""
        from tools.match_product.executor import get_hybrid_searcher
    from src.retrieval.tender_index_search import get_tender_index_searcher

    try:
        get_hybrid_searcher()
        get_tender_index_searcher()
    except Exception as e:
        logger.error(f"预热失败: {e}")

@contextlib.asynccontextmanager
async def _app_lifespan(app: FastAPI):
    if not os.environ.get("GET_DATA_WEB_SKIP_WARMUP"):
        asyncio.create_task(asyncio.to_thread(_warmup))
    yield

app = FastAPI(
    title="get_data Web UI",
    version="1.1.0",
    lifespan=_app_lifespan,
)

# 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def _log_requests(request: Request, call_next):
    t0 = time.perf_counter()
        response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    logger.info(f"{request.method} {request.url.path} {response.status_code} {ms:.1f}ms")
    return response

# 挂载路由
app.include_router(system.router)
app.include_router(retrieval.router)
app.include_router(intel.router)
app.include_router(db.router)
app.include_router(crawl.router)
app.include_router(extract.router)
app.include_router(output.router)

# 静态文件
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 文档目录（用于 demo 页面加载 MD 说明）
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
if DOCS_DIR.is_dir():
    app.mount("/docs", StaticFiles(directory=str(DOCS_DIR)), name="docs")

@app.get("/")
def index() -> FileResponse:
    index_file = STATIC_DIR / "index.html"
    if not index_file.is_file():
        raise HTTPException(status_code=500, detail="static/index.html 缺失")
    return FileResponse(index_file)

if __name__ == "__main__":
    import uvicorn
    from webapp.utils import terminate_listeners_on_port, guess_lan_ipv4s
    
    host = os.environ.get("GET_DATA_WEB_HOST", "0.0.0.0")
    port = int(os.environ.get("GET_DATA_WEB_PORT", "8103"))
    
    # 启动前先清理占用该端口的进程
    terminate_listeners_on_port(port)
    
    print("=" * 50)
    print("get_data Web UI 启动准备中...")
    print(f"本地访问链接: http://127.0.0.1:{port}")
    for ip in guess_lan_ipv4s():
        print(f"局域网访问链接: http://{ip}:{port}")
    print("=" * 50)
    
    uvicorn.run(app, host=host, port=port)
