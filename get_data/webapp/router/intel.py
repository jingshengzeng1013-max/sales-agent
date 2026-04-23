# -*- coding: utf-8 -*-
"""销售情报相关 API：仅保留混合检索等共用的招标下拉数据源。"""
import logging
import sqlite3
from pathlib import Path

from fastapi import APIRouter

from src.config import DB_PATH

logger = logging.getLogger("get_data.webapp.router.intel")
router = APIRouter(prefix="/api/intel")


@router.get("/tender-options")
def get_tender_options(limit: int = 200):
    if not Path(DB_PATH).is_file():
        return {"ok": True, "rows": []}
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT t.id AS id, t.project_name AS project_name,
                   ts.buyer_name_std AS buyer_name_std
            FROM tenders t
            INNER JOIN tender_structured ts ON t.id = ts.tender_id
            ORDER BY t.created_at DESC LIMIT ?
            """,
            (limit,),
        )
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            d["label"] = f"#{d['id']} {d['project_name']} — {d['buyer_name_std']}"[:200]
            rows.append(d)
        return {"ok": True, "rows": rows}
    finally:
        conn.close()
