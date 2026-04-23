# -*- coding: utf-8 -*-
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from webapp.utils import tee_flow_stdout_stderr
import queue
import threading
import time
import json
from src.config import LOGS_STREAM_DIR

router = APIRouter(prefix="/api/crawl")

class CrawlerWorkflowBody(BaseModel):
    keyword: str = ""
    base_url: str = ""
    delay_min: float = 2.0
    delay_max: float = 5.0
    max_pages: int = 3
    timeout: int = 30
    searchtype: str = "1"
    bidSort: str = "0"
    time_type: str = "2"
    start_time: str = ""
    end_time: str = ""
    detail_limit: int = 0  # 0 表示详情阶段不限制条数（爬完待爬列表）
    detail_delay_min: float = 2.0
    detail_delay_max: float = 5.0
    detail_timeout: int = 30
    run_list: bool = True
    run_import: bool = True
    run_detail: bool = True
    json_path: str = ""

@router.get("/defaults")
def get_defaults():
    from src.crawler_graph import crawler_workflow_defaults
    return {"defaults": crawler_workflow_defaults()}

@router.post("/workflow/stream")
async def workflow_stream(body: CrawlerWorkflowBody):
    from src.crawler_graph import run_crawler_graph
    q = queue.Queue()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    session_log = LOGS_STREAM_DIR / f"crawler_{stamp}.log"
    holder = {}
    payload = body.model_dump()

    def _worker():
        try:
            with open(session_log, "w", encoding="utf-8") as lf:
                with tee_flow_stdout_stderr(q, lf):
                    holder["result"] = run_crawler_graph(payload)
        except Exception as e:
            holder["error"] = str(e)
        finally:
            q.put(None)

    threading.Thread(target=_worker, daemon=True).start()

    async def _events():
        while True:
            import asyncio
            chunk = await asyncio.to_thread(q.get)
            if chunk is None: break
            yield f"data: {json.dumps({'type': 'log', 'text': chunk}, ensure_ascii=False)}\n\n"
        if "error" in holder:
            yield f"data: {json.dumps({'type': 'error', 'message': holder['error']}, ensure_ascii=False)}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'done', 'result': holder.get('result')}, ensure_ascii=False)}\n\n"

    return StreamingResponse(_events(), media_type="text/event-stream")
