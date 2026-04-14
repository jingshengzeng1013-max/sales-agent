# -*- coding: utf-8 -*-
import asyncio
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional, List, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.config import DATA_DIR, DB_PATH
from src.retrieval.tender_document import build_tender_retrieval_document
from webapp.utils import sqlite_row_to_jsonable, shorten_cell

logger = logging.getLogger("get_data.webapp.router.retrieval")
router = APIRouter(prefix="/api/retrieval")

class HybridSearchBody(BaseModel):
    query: str = Field("", max_length=8000)
    tender_id: Optional[int] = Field(None, ge=1)
    top_k: int = Field(10, ge=1, le=2000)
    use_vector: bool = Field(True)
    use_bm25: bool = Field(True)
    min_score: float = Field(0.0, ge=0.0, le=1.0)
    vector_weight: float = Field(0.5, ge=0.0, le=1.0)
    bm25_weight: float = Field(0.5, ge=0.0, le=1.0)

class TenderSearchByProductBody(BaseModel):
    product_id: str = Field(..., description="必须提供产品ID")
    top_k: int = Field(20, ge=1, le=2000)
    use_vector: bool = Field(True)
    use_bm25: bool = Field(True)
    min_score: float = Field(0.0, ge=0.0, le=1.0)
    vector_weight: float = Field(0.5, ge=0.0, le=1.0)
    bm25_weight: float = Field(0.5, ge=0.0, le=1.0)

def _retrieval_optional_deps() -> dict[str, bool]:
    d = {}
    try:
        import faiss
        d["faiss"] = True
    except ImportError:
        d["faiss"] = False
    try:
        from rank_bm25 import BM25Okapi
        d["rank_bm25"] = True
    except ImportError:
        d["rank_bm25"] = False
    try:
        from src.retrieval.embedding_api import EmbeddingAPIClient
        d["embedding_api"] = True
    except ImportError:
        d["embedding_api"] = False
    return d

def _serialize_hybrid_hits(rows: list[Any]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        if not isinstance(r, dict): continue
        vs = r.get("vector_score")
        bs = r.get("bm25_score")
        rrf_raw = r.get("rrf_raw_score")
        out.append({
            "product_id": r.get("product_id"),
            "score": float(r.get("score", 0)),
            "rrf_raw_score": float(rrf_raw) if rrf_raw is not None else None,
            "vector_score": float(vs) if vs is not None else None,
            "bm25_score": float(bs) if bs is not None else None,
            "data": r.get("data") if isinstance(r.get("data"), dict) else {},
        })
    return out

def _serialize_tender_index_hits(rows: list[Any]) -> list[dict[str, Any]]:
    out = []

    # Collect all tender IDs to fetch detail_urls in one query
    tids_to_fetch = []
    for r in rows:
        if not isinstance(r, dict): continue
        pid = r.get("product_id")
        if pid is not None:
            try:
                tids_to_fetch.append(int(pid))
            except: pass

    url_map = {}
    if tids_to_fetch and Path(DB_PATH).is_file():
        try:
            conn = sqlite3.connect(DB_PATH)
            placeholders = ",".join("?" for _ in tids_to_fetch)
            cur = conn.execute(f"SELECT id, detail_url FROM tenders WHERE id IN ({placeholders})", tids_to_fetch)
            for row in cur:
                url_map[row[0]] = row[1]
            conn.close()
        except Exception as e:
            print(f"[WARN] Failed to fetch detail_urls: {e}")

    for r in rows:
        if not isinstance(r, dict): continue
        vs = r.get("vector_score")
        bs = r.get("bm25_score")
        rrf_raw = r.get("rrf_raw_score")
        pid = r.get("product_id")
        tid = None
        detail_url = None
        if pid is not None:
            try:
                tid = int(pid)
                detail_url = url_map.get(tid)
            except: pass

        data = dict(r.get("data")) if isinstance(r.get("data"), dict) else {}
        if detail_url:
            data["detail_url"] = detail_url

        out.append({
            "tender_id": tid,
            "product_id": pid,
            "score": float(r.get("score", 0)),
            "rrf_raw_score": float(rrf_raw) if rrf_raw is not None else None,
            "vector_score": float(vs) if vs is not None else None,
            "bm25_score": float(bs) if bs is not None else None,
            "data": data,
        })
    return out

def _resolve_product_info_for_query(product_id: str) -> Optional[dict[str, Any]]:
    pid = (product_id or "").strip()
    if not pid: return None
    try:
        from tools.match_product import executor as _mp
        if _mp._hybrid_searcher is not None:
            d = _mp._hybrid_searcher.product_data.get(pid)
            if isinstance(d, dict): return d
    except: pass
    
    meta_path = DATA_DIR / "index" / "metadata.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            pd = meta.get("product_data") or {}
            d = pd.get(pid)
            if isinstance(d, dict): return d
        except: pass
    return None

@router.get("/status")
def get_status():
    deps = _retrieval_optional_deps()
    index_dir = (DATA_DIR / "index").resolve()
    products_json = (DATA_DIR / "products.json").resolve()

    searcher_loaded = False
    indexed_documents = None
    try:
        from tools.match_product import executor as _mp_exec
        if _mp_exec._hybrid_searcher is not None:
            searcher_loaded = True
            indexed_documents = _mp_exec._hybrid_searcher.search_size()
    except: pass

    tender_searcher_loaded = False
    tender_indexed_documents = None
    try:
        from src.retrieval import tender_index_search as _tis
        if _tis._tender_searcher is not None:
            tender_searcher_loaded = True
            tender_indexed_documents = _tis._tender_searcher.search_size()
    except: pass

    # Get API base URL from config
    api_base_url = None
    try:
        from src.config import EMBEDDING_CONFIG
        api_base_url = EMBEDDING_CONFIG.get("base_url")
    except: pass

    return {
        "ok": True,
        "deps": deps,
        "searcher_loaded": searcher_loaded,
        "indexed_documents": indexed_documents,
        "tender_searcher_loaded": tender_searcher_loaded,
        "tender_indexed_documents": tender_indexed_documents,
        "products_json_exists": products_json.is_file(),
        "api_base_url": api_base_url,
    }

@router.get("/product-options")
def get_product_options():
    rows = []
    meta_path = DATA_DIR / "index" / "metadata.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            pids = meta.get("product_ids") or []
            pdata = meta.get("product_data") or {}
            for pid in pids:
                sid = str(pid)
                info = pdata.get(pid, pdata.get(sid)) or {}
                nm = info.get("name")
                rows.append({"id": sid, "name": str(nm) if nm else sid})
        except: pass
    return {"ok": True, "rows": rows}

@router.post("/search")
async def search(body: HybridSearchBody):
    deps = _retrieval_optional_deps()
    if not all(deps.values()):
        raise HTTPException(status_code=503, detail="依赖未安装")
    
    q = (body.query or "").strip()
    tender_id_used = None
    if body.tender_id is not None:
        from tools.query_tenders.executor import query_tenders
        rows_qt, _ = query_tenders(tender_ids=[int(body.tender_id)])
        if not rows_qt:
            raise HTTPException(status_code=404, detail="未找到招标记录")
        from src.retrieval.tender_document import build_tender_retrieval_document
        q = build_tender_retrieval_document(rows_qt[0])
        tender_id_used = int(body.tender_id)
    
    if not q:
        raise HTTPException(status_code=400, detail="查询内容不能为空")

    def _run():
        from tools.match_product.executor import get_hybrid_searcher
        return get_hybrid_searcher().search(
            q, top_k=body.top_k, use_vector=body.use_vector,
            use_bm25=body.use_bm25, min_score=body.min_score,
            vector_weight=body.vector_weight, bm25_weight=body.bm25_weight
        )

    raw = await asyncio.to_thread(_run)
    return {
        "ok": True,
        "query": q,
        "tender_id": tender_id_used,
        "results": _serialize_hybrid_hits(raw)
    }

@router.post("/search-tenders")
async def search_tenders(body: TenderSearchByProductBody):
    product_id_used = body.product_id
    
    from src.retrieval.product_document import build_product_retrieval_document
    info = _resolve_product_info_for_query(product_id_used)
    if not info:
        raise HTTPException(status_code=404, detail="未找到产品")
    
    q = build_product_retrieval_document(info)
    if not q:
        raise HTTPException(status_code=400, detail="产品查询内容为空")

    def _run():
        from src.retrieval.tender_index_search import get_tender_index_searcher
        from src.retrieval.product_query_cache import get_product_query_embedding
        searcher = get_tender_index_searcher()
        qe = get_product_query_embedding(product_id_used) if product_id_used else None
        return searcher.search(
            q, top_k=body.top_k, use_vector=body.use_vector,
            use_bm25=body.use_bm25, min_score=body.min_score,
            query_embedding=qe,
            vector_weight=body.vector_weight, bm25_weight=body.bm25_weight
        )

    raw = await asyncio.to_thread(_run)
    return {
        "ok": True,
        "query": q,
        "query_source": "product",
        "product_id": product_id_used,
        "product_info": info,
        "results": _serialize_tender_index_hits(raw),
    }

@router.get("/tender-structured/{tender_id}")
def get_tender_structured_row(tender_id: int):
    if tender_id < 1:
        raise HTTPException(status_code=400, detail="tender_id 须为 >= 1 的整数")
    if not Path(DB_PATH).is_file():
        raise HTTPException(status_code=404, detail="数据库文件不存在")
    
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM tender_structured WHERE tender_id = ?", (tender_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="未找到记录")
        return {"ok": True, "row": sqlite_row_to_jsonable(row)}
    finally:
        conn.close()
