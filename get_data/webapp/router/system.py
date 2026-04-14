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

    # 各 provider 的推荐模型列表
    MODEL_RECOMMENDATIONS = {
        "deepseek": [
            {"id": "deepseek-chat", "name": "DeepSeek Chat (V3)"},
            {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner (R1)"},
        ],
        "qwen": [
            {"id": "qwen3.5-flash", "name": "Qwen3.5-Flash"},
            {"id": "qwen3.5-plus", "name": "Qwen3.5-Plus"},
            {"id": "qwen-max", "name": "Qwen-Max"},
            {"id": "qwen-turbo", "name": "Qwen-Turbo"},
        ],
        "doubao": [
            {"id": "doubao-seed-2-0-lite-260215", "name": "Doubao Seed 2.0 Lite"},
            {"id": "doubao-seed-1.6", "name": "Doubao Seed 1.6"},
        ],
        "local": [
            {"id": "local-model", "name": "本地模型 (自定义)"},
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
        if pid == "local":
            configured = bool((c.get("base_url") or "").strip())
        else:
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
        row("deepseek", "DeepSeek API", "api", getattr(cfg, "DEEPSEEK_CONFIG", {}), "DEEPSEEK_API_KEY"),
        row(
            "qwen",
            "通义千问（阿里云 DashScope，OpenAI 兼容）",
            "api",
            getattr(cfg, "QWEN_CONFIG", {}),
            "DASHSCOPE_API_KEY",
        ),
        row(
            "local",
            "本地 OpenAI 兼容（如 vLLM / Ollama OpenAI 插件）",
            "local",
            getattr(cfg, "LOCAL_LLM_CONFIG", {}),
            "LOCAL_LLM_BASE_URL",
        ),
        row("doubao", "豆包（火山引擎 Ark）", "api", getattr(cfg, "DOUBAO_CONFIG", {}), "ARK_API_KEY"),
    ]
    return {"ok": True, "default_provider": getattr(cfg, "DEFAULT_PROVIDER", "deepseek"), "providers": providers}
