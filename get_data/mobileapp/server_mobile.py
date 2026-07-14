# -*- coding: utf-8 -*-
"""FastAPI entry for the mobile sales intelligence page."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
WEB_API_PORT = 8103
MOBILE_PORT = 8104

app = FastAPI(
    title="销售情报系统移动端",
    description="面向销售人员的移动端检索入口",
    docs_url=None,
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def mobile_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": "sales-mobile",
        "mobile_port": MOBILE_PORT,
        "web_api_port": WEB_API_PORT,
    }

