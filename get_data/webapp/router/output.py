# -*- coding: utf-8 -*-
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.config import OUTPUT_DIR
from webapp.utils import shorten_cell

logger = logging.getLogger("get_data.webapp.router.output")
router = APIRouter(prefix="/api/output")

class StructuredOutputCompareBody(BaseModel):
    files: list[str]
    max_tenders: int = Field(80, ge=1, le=200)
    intersection_only: bool = False
    cell_max_chars: int = Field(2000, ge=200, le=12000)

class IntelOutputCompareBody(BaseModel):
    files: list[str]
    max_rows: int = Field(40, ge=1, le=200)
    intersection_only: bool = False
    cell_max_chars: int = Field(2000, ge=200, le=12000)

def _safe_path(root: Path, rel: str, pattern: str) -> Optional[Path]:
    import re
    rel = rel.strip().replace("\\", "/").lstrip("/")
    if not rel or not re.match(pattern, rel.split("/")[-1]): return None
    p = (root / rel).resolve()
    try:
        p.relative_to(root)
        return p if p.is_file() else None
    except ValueError: return None

@router.get("/structured-files")
def get_structured_files():
    root = Path(OUTPUT_DIR).resolve()
    items = []
    for p in root.rglob("tenders_structured*.json"):
        st = p.stat()
        items.append({
            "name": str(p.relative_to(root)).replace("\\", "/"),
            "size_bytes": st.st_size,
            "mtime_iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
        })
    return {"ok": True, "files": items}

@router.post("/structured/compare")
def compare_structured(body: StructuredOutputCompareBody):
    # ... 迁移对比逻辑 ...
    return {"ok": True}
