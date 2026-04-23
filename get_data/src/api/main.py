# -*- coding: utf-8 -*-
"""FastAPI 主入口"""

import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import time

from routes.tenders import router as tenders_router
from routes.search import router as search_router
from routes.stats import router as stats_router
from logging_config import logger

app = FastAPI(
    title="政府采购招投标数据系统 API",
    description="提供招标项目查询、搜索、统计等功能",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    # 记录请求
    logger.info(f"{request.method} {request.url.path} - 开始处理")

    # 处理请求
    response = await call_next(request)

    # 计算耗时
    duration = time.time() - start_time

    # 记录响应
    logger.info(
        f"{request.method} {request.url.path} - "
        f"状态：{response.status_code} - "
        f"耗时：{duration:.3f}s"
    )

    return response

# 注册路由
app.include_router(tenders_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(stats_router, prefix="/api")


@app.get("/")
async def root():
    logger.info("访问 API 根路径")
    return {
        "message": "政府采购招投标数据系统 API",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    logger.info("启动 API 服务器...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
