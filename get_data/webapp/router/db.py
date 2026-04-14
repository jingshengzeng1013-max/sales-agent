# -*- coding: utf-8 -*-
import sqlite3
import logging
from typing import Any
from fastapi import APIRouter, HTTPException
from webapp.utils import shorten_cell, sqlite_row_to_jsonable
from src.config import DB_PATH
from pathlib import Path

logger = logging.getLogger("get_data.webapp.router.db")
router = APIRouter(prefix="/api/db")

@router.get("/tables")
def get_tables():
    if not Path(DB_PATH).is_file():
        return {"ok": True, "tables": [], "hint": "数据库文件尚未创建"}
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
        tables = [r[0] for r in cur.fetchall()]
        return {"ok": True, "tables": tables}
    finally:
        conn.close()

@router.get("/table/{table_name}")
def get_table_rows(table_name: str, limit: int = 50, offset: int = 0):
    if not Path(DB_PATH).is_file():
        raise HTTPException(status_code=404, detail="数据库文件不存在")
    
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        count_row = conn.execute(f"SELECT COUNT(*) AS c FROM {table_name}").fetchone()
        total = int(count_row["c"]) if count_row else 0
        
        cur = conn.execute(f"SELECT * FROM {table_name} LIMIT ? OFFSET ?", (limit, offset))
        raw_rows = cur.fetchall()
        columns = list(raw_rows[0].keys()) if raw_rows else []
        rows = [{k: shorten_cell(r[k]) for k in columns} for r in raw_rows]
        
        return {
            "ok": True,
            "table": table_name,
            "columns": columns,
            "rows": rows,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@router.get("/tender-detail/{tender_id}")
def get_tender_detail(tender_id: int):
    if not Path(DB_PATH).is_file():
        raise HTTPException(status_code=404, detail="数据库文件不存在")
    
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        
        cur = conn.execute("SELECT * FROM tender_structured WHERE tender_id = ?", (tender_id,))
        row = cur.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail=f"未找到 tender_id = {tender_id} 的结构化数据")
        
        return {
            "ok": True,
            "data": sqlite_row_to_jsonable(row)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()
