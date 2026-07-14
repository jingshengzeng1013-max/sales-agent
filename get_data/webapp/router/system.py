# -*- coding: utf-8 -*-
from typing import Any
from fastapi import APIRouter
from webapp.utils import guess_lan_ipv4s
import sys
from src.config import BASE_DIR

router = APIRouter()

@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "root": str(BASE_DIR)}

@router.get("/api/llm/options")
def api_llm_options() -> dict[str, Any]:
    """供前端填充「线路 + 默认模型」；不返回任何 API Key。"""
    from src import config as cfg

    MODEL_RECOMMENDATIONS = {
        "minimax": [
            {"id": "MiniMax-M3", "name": "MiniMax-M3"},
            {"id": "MiniMax-M1", "name": "MiniMax-M1"},
            {"id": "abab6.5s-chat", "name": "ABAB 6.5s"},
        ],
    }

    def row(
        pid: str,
        label: str,
        kind: str,
        c: dict[str, Any],
        env_key: str,
    ) -> dict[str, Any]:
        key = (c.get("api_key") or "").strip()
        configured = bool(key)
        return {
            "id": pid,
            "label": label,
            "kind": kind,
            "default_model": (c.get("model") or "").strip(),
            "base_url": (c.get("base_url") or "").strip(),
            "timeout_sec": int(c.get("timeout") or 120),
            "configured": configured,
            "env_key": env_key,
            "models": MODEL_RECOMMENDATIONS.get(pid, []),
        }

    providers = [
        row("minimax", "MiniMax API", "api", getattr(cfg, "MINIMAX_CONFIG", {}), "MINIMAX_API_KEY"),
    ]
    return {"ok": True, "default_provider": getattr(cfg, "DEFAULT_PROVIDER", "minimax"), "providers": providers}
