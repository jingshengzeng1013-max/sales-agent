# -*- coding: utf-8 -*-
"""
结构化抽取字段、SQLite 表结构和 JSON schema 的单一真相源。
"""

import copy
import json
from datetime import datetime, timezone


SCHEMA_VERSION = "tender-structured-v1"

ANNOUNCE_TYPES = (
    "采购公告",
    "更正公告",
    "结果公告",
    "合同公告",
    "验收公告",
    "终止公告",
    "其他",
)

FINAL_RESULT_FIELDS = (
    "announce_type",
    "buyer_name_std",
    "province",
    "city",
    "budget_raw",
    "budget_amount",
    "budget_unit",
    "product_keywords",
    "technical_requirements_summary",
    "opportunity_score",
    "opportunity_reason",
    "next_action",
)

FINAL_RESULT_TEMPLATE = {
    "announce_type": None,
    "buyer_name_std": None,
    "province": None,
    "city": None,
    "budget_raw": None,
    "budget_amount": None,
    "budget_unit": None,
    "product_keywords": [],
    "technical_requirements_summary": None,
    "opportunity_score": None,
    "opportunity_reason": None,
    "next_action": None,
}

SOURCE_FIELDS = (
    "project_name",
    "buyer_name",
    "agency_name",
    "publish_date",
    "budget",
    "content",
    "attachment_urls",
    "detail_url",
    "project_code",
    "deadline",
)

SOURCE_TEMPLATE = {field: None for field in SOURCE_FIELDS}

RULE_EXTRACT_TEMPLATE = {
    "announce_type": None,
    "province": None,
    "city": None,
    "budget_raw": None,
    "budget_amount": None,
    "budget_unit": None,
    "has_attachments": None,
    "attachment_count": None,
    "contact_phone": None,
}

LLM_EXTRACT_TEMPLATE = {
    "buyer_name_std": None,
    "product_keywords": [],
    "technical_requirements_summary": None,
    "content_summary": None,            # 公告内容摘要
    "opportunity_score": None,
    "opportunity_reason": None,
    "next_action": None,
    # 三方联系人信息
    "buyer_contacts": [],       # 采购人联系人列表 [{"name": "", "phone": ""}]
    "agency_contacts": [],      # 代理机构联系人列表 [{"name": "", "phone": ""}]
    "project_contacts": [],     # 项目联系人列表 [{"name": "", "phone": ""}]
    # RAG 检索块
    "contact_chunk": None,      # 联系方式块（用于向量检索）
    "requirement_chunks": [],   # 技术要求分块数组 [{"type": "", "text": ""}]
    # 兼容旧字段
    "contact_person": None,
    "contact_phone": None,
}

META_TEMPLATE = {
    "schema_version": SCHEMA_VERSION,
    "llm_model": None,
    "llm_version": None,
    "extracted_at": None,
}

TENDER_STRUCTURED_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tender_structured (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id INTEGER NOT NULL UNIQUE,
    announce_type TEXT,
    buyer_name_std TEXT,
    province TEXT,
    city TEXT,
    budget_raw TEXT,
    budget_amount REAL,
    budget_unit TEXT,
    product_keywords_json TEXT,
    technical_requirements_summary TEXT,
    opportunity_score INTEGER CHECK (
        opportunity_score IS NULL
        OR (opportunity_score >= 0 AND opportunity_score <= 100)
    ),
    opportunity_reason TEXT,
    next_action TEXT,
    extracted_json TEXT NOT NULL,
    llm_model TEXT,
    llm_version TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(tender_id) REFERENCES tenders(id) ON DELETE CASCADE
)
"""

TENDER_STRUCTURED_INDEX_SQLS = (
    "CREATE INDEX IF NOT EXISTS idx_tender_structured_buyer ON tender_structured(buyer_name_std)",
    "CREATE INDEX IF NOT EXISTS idx_tender_structured_location ON tender_structured(province, city)",
    "CREATE INDEX IF NOT EXISTS idx_tender_structured_score ON tender_structured(opportunity_score)",
)

STRUCTURED_RESULT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://example.local/schemas/tender-structured-v1.json",
    "title": "TenderStructuredResult",
    "type": "object",
    "additionalProperties": False,
    "required": ["final", "meta"],
    "properties": {
        "tender_id": {
            "type": ["integer", "null"],
            "minimum": 1,
        },
        "source": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                field: {"type": ["string", "null"]}
                for field in SOURCE_FIELDS
            },
        },
        "rule_extract": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "announce_type": {
                    "type": ["string", "null"],
                    "enum": [*ANNOUNCE_TYPES, None],
                },
                "province": {"type": ["string", "null"]},
                "city": {"type": ["string", "null"]},
                "budget_raw": {"type": ["string", "null"]},
                "budget_amount": {"type": ["number", "null"], "minimum": 0},
                "budget_unit": {"type": ["string", "null"]},
                "has_attachments": {"type": ["boolean", "null"]},
                "attachment_count": {"type": ["integer", "null"], "minimum": 0},
                "contact_phone": {"type": ["string", "null"]},
            },
        },
        "llm_extract": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "buyer_name_std": {"type": ["string", "null"]},
                "product_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                },
                "technical_requirements_summary": {"type": ["string", "null"]},
                "content_summary": {"type": ["string", "null"]},
                "opportunity_score": {
                    "type": ["integer", "null"],
                    "minimum": 0,
                    "maximum": 100,
                },
                "opportunity_reason": {"type": ["string", "null"]},
                "next_action": {"type": ["string", "null"]},
                # 三方联系人信息
                "buyer_contacts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": ["string", "null"]},
                            "phone": {"type": ["string", "null"]},
                        },
                    },
                    "default": [],
                },
                "agency_contacts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": ["string", "null"]},
                            "phone": {"type": ["string", "null"]},
                        },
                    },
                    "default": [],
                },
                "project_contacts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": ["string", "null"]},
                            "phone": {"type": ["string", "null"]},
                        },
                    },
                    "default": [],
                },
                # 兼容旧字段
                "contact_person": {"type": ["string", "null"]},
                "contact_phone": {"type": ["string", "null"]},
                # RAG 检索块
                "contact_chunk": {"type": ["string", "null"]},
                "requirement_chunks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["technical_params", "service_requirements", "qualification_requirements", "other"]
                            },
                            "text": {"type": ["string", "null"]},
                        },
                        "required": ["type", "text"],
                    },
                    "default": [],
                },
            },
        },
        "final": {
            "type": "object",
            "additionalProperties": False,
            "required": list(FINAL_RESULT_FIELDS),
            "properties": {
                "announce_type": {
                    "type": ["string", "null"],
                    "enum": [*ANNOUNCE_TYPES, None],
                },
                "buyer_name_std": {"type": ["string", "null"]},
                "province": {"type": ["string", "null"]},
                "city": {"type": ["string", "null"]},
                "budget_raw": {"type": ["string", "null"]},
                "budget_amount": {"type": ["number", "null"], "minimum": 0},
                "budget_unit": {"type": ["string", "null"]},
                "product_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                },
                "technical_requirements_summary": {"type": ["string", "null"]},
                "opportunity_score": {
                    "type": ["integer", "null"],
                    "minimum": 0,
                    "maximum": 100,
                },
                "opportunity_reason": {"type": ["string", "null"]},
                "next_action": {"type": ["string", "null"]},
            },
        },
        "meta": {
            "type": "object",
            "additionalProperties": False,
            "required": ["schema_version", "extracted_at"],
            "properties": {
                "schema_version": {
                    "type": "string",
                    "const": SCHEMA_VERSION,
                },
                "llm_model": {"type": ["string", "null"]},
                "llm_version": {"type": ["string", "null"]},
                "extracted_at": {
                    "type": "string",
                    "format": "date-time",
                },
            },
        },
    },
}


def _copy_template(template):
    """返回深拷贝，避免调用方误改共享默认值。"""
    return copy.deepcopy(template)


def get_empty_structured_payload():
    """生成一份可直接填充的结构化抽取结果骨架。"""
    payload = {
        "tender_id": None,
        "source": _copy_template(SOURCE_TEMPLATE),
        "rule_extract": _copy_template(RULE_EXTRACT_TEMPLATE),
        "llm_extract": _copy_template(LLM_EXTRACT_TEMPLATE),
        "final": _copy_template(FINAL_RESULT_TEMPLATE),
        "meta": _copy_template(META_TEMPLATE),
    }
    payload["meta"]["extracted_at"] = datetime.now(timezone.utc).isoformat()
    return payload


def dumps_structured_payload(payload):
    """统一 JSON 序列化格式，便于落库和 diff。"""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def validate_structured_payload(payload):
    """对核心字段做轻量校验，避免明显脏数据落库。"""
    if not isinstance(payload, dict):
        raise ValueError("structured payload must be a dict")

    final = payload.get("final")
    meta = payload.get("meta")
    if not isinstance(final, dict):
        raise ValueError("payload.final must be a dict")
    if not isinstance(meta, dict):
        raise ValueError("payload.meta must be a dict")

    for field in FINAL_RESULT_FIELDS:
        if field not in final:
            raise ValueError(f"payload.final missing field: {field}")

    product_keywords = final.get("product_keywords")
    if not isinstance(product_keywords, list):
        raise ValueError("payload.final.product_keywords must be a list")
    if any(not isinstance(item, str) for item in product_keywords):
        raise ValueError("payload.final.product_keywords must contain strings only")

    announce_type = final.get("announce_type")
    if announce_type is not None and announce_type not in ANNOUNCE_TYPES:
        raise ValueError(f"invalid announce_type: {announce_type}")

    budget_amount = final.get("budget_amount")
    if budget_amount is not None and budget_amount < 0:
        raise ValueError("payload.final.budget_amount must be >= 0")

    opportunity_score = final.get("opportunity_score")
    if opportunity_score is not None:
        if not isinstance(opportunity_score, int):
            raise ValueError("payload.final.opportunity_score must be an integer")
        if not 0 <= opportunity_score <= 100:
            raise ValueError("payload.final.opportunity_score must be between 0 and 100")

    if meta.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("payload.meta.schema_version does not match current schema")
    if not meta.get("extracted_at"):
        raise ValueError("payload.meta.extracted_at is required")

    return True
