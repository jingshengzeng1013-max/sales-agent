# -*- coding: utf-8 -*-
import logging
import sys
import json
import time
import queue
import threading
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from webapp.utils import tee_flow_stdout_stderr, subprocess_env, decode_subprocess_bytes
from src.config import BASE_DIR, LOGS_STREAM_DIR, OUTPUT_DIR

logger = logging.getLogger("get_data.webapp.router.extract")
router = APIRouter(prefix="/api")

class ExtractStructuredBody(BaseModel):
    limit: int = Field(20, ge=1, le=5000)
    use_llm: bool = True
    provider: str = ""
    model: str = "deepseek-chat"
    run_import: bool = True
    import_replace: bool = False
    output_suffix: str = ""

class ImportStructuredBody(BaseModel):
    import_basename: str
    replace: bool = False

def _popen_stream_to_queue(cmd, cwd, q, log_fp):
    import subprocess
    env = subprocess_env()
    proc = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, bufsize=0
    )
    try:
        while True:
            chunk = proc.stdout.read(4096)
            if not chunk: break
            s = decode_subprocess_bytes(chunk)
            q.put(s)
            if log_fp:
                log_fp.write(s)
                log_fp.flush()
    finally:
        proc.stdout.close()
    proc.wait()
    return proc.returncode

@router.post("/extract/structured/stream")
async def extract_structured_stream(body: ExtractStructuredBody):
    q = queue.Queue()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    session_log = LOGS_STREAM_DIR / f"extract_{stamp}.log"
    holder = {}
    
    extract_py = BASE_DIR / "src" / "etl" / "core" / "extract_structured.py"
    cmd = [sys.executable, str(extract_py), "--limit", str(body.limit), "--model", body.model]
    if body.provider: cmd.extend(["--provider", body.provider])
    if not body.use_llm: cmd.append("--no-llm")
    if body.output_suffix: cmd.extend(["--output-suffix", body.output_suffix])

    def _worker():
        try:
            with open(session_log, "w", encoding="utf-8") as lf:
                rc = _popen_stream_to_queue(cmd, str(BASE_DIR), q, lf)
                holder["returncode"] = rc
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
        yield f"data: {json.dumps({'type': 'done', 'result': holder}, ensure_ascii=False)}\n\n"

    return StreamingResponse(_events(), media_type="text/event-stream")

@router.post("/import/structured/stream")
async def import_structured_stream(body: ImportStructuredBody):
    # ... 类似逻辑 ...
    return {"ok": True}
