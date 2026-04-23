# -*- coding: utf-8 -*-
"""
统一客户画像格式

将招标画像和CRM画像统一为相同结构。
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("analysis.profile_unifier")


UNIFIED_PROFILE_SCHEMA = {
    # 核心标识
    "customer_id": "",           # 统一用credit_code作为ID
    "customer_name": "",         # 客户名称

    # 基础信息
    "basic_info": {
        "credit_code": "",       # 统一信用代码
        "province": "",          # 省份
        "city": "",              # 城市
        "customer_type": "",     # 客户类型（汽车组/应急组/政府单位等）
        "customer_segment": "",   # 客户细分（toG/toB）
        "is_from_crm": False,     # 是否来自CRM
        "is_from_tender": False,  # 是否来自招标
    },

    # 联系人信息
    "contact_info": {
        "contacts": [            # 联系人列表
            {
                "name": "",      # 姓名
                "position": "",  # 职位
                "phone": "",     # 电话
                "source": ""     # 来源（招标/商机/线索）
            }
        ]
    },

    # 需求画像（来自招标数据）
    "demand_profile": {
        "tech_keywords": [],     # 技术关键词
        "application_scenarios": [],  # 应用场景
        "technical_summaries": []     # 技术摘要
    },

    # 价值评估
    "value_profile": {
        "tender_count": 0,       # 招标次数
        "total_budget": 0.0,     # 总预算
        "avg_opportunity_score": 0.0,  # 平均机会评分

        # CRM相关价值
        "opportunity_value": 0.0, # 商机总规模
        "opportunity_count": 0,   # 商机数量
        "lead_value": 0.0,       # 线索总规模
        "lead_count": 0,         # 线索数量
    },

    # 竞争态势（来自招标数据）
    "competitive_landscape": {
        "past_winners": [],      # 历史中标单位
        "past_winning_products": []  # 历史中标产品
    },

    # 销售关系（来自CRM数据）
    "sales_relationship": {
        "primary_sales": "",     # 主销售
        "secondary_sales": "",   # 副销售
        "all_owners": [],        # 所有商机负责人
        "all_salespersons": [],  # 所有线索销售
        "relationship_level": "", # 合作紧密度
        "first_contact_date": "", # 首次接触
        "last_followup_date": "" # 最近跟进
    },

    # 招标历史（来自招标数据）
    "history_tenders": [],       # 历史招标记录

    # CRM历史（来自CRM数据）
    "crm_history": {
        "opportunities": [],     # 商机列表
        "leads": []              # 线索列表
    },

    # 元数据
    "has_crm_data": False,
    "has_tender_data": False,
    "last_updated": ""
}


def unify_tender_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """将招标画像转为统一格式"""
    unified = {**UNIFIED_PROFILE_SCHEMA}

    # 核心标识
    unified["customer_id"] = profile.get("basic_info", {}).get("credit_code") or ""
    unified["customer_name"] = profile.get("customer_name", "")

    # 基础信息
    unified["basic_info"]["credit_code"] = profile.get("basic_info", {}).get("credit_code", "")
    unified["basic_info"]["province"] = profile.get("basic_info", {}).get("province", "")
    unified["basic_info"]["city"] = profile.get("basic_info", {}).get("city", "")
    unified["basic_info"]["customer_type"] = profile.get("basic_info", {}).get("customer_type", "")
    unified["basic_info"]["is_from_tender"] = True

    # 联系人信息
    contacts = []
    persons = profile.get("contact_info", {}).get("persons", [])
    phones = profile.get("contact_info", {}).get("phones", [])
    for i, name in enumerate(persons):
        contacts.append({
            "name": name,
            "position": "",
            "phone": phones[i] if i < len(phones) else "",
            "source": "招标"
        })
    unified["contact_info"]["contacts"] = contacts

    # 需求画像
    unified["demand_profile"] = profile.get("demand_profile", {})

    # 价值评估
    value = profile.get("value_profile", {})
    unified["value_profile"]["tender_count"] = value.get("tender_count", 0)
    unified["value_profile"]["total_budget"] = value.get("total_budget", 0.0)
    unified["value_profile"]["avg_opportunity_score"] = value.get("avg_opportunity_score", 0.0)

    # 竞争态势
    unified["competitive_landscape"] = profile.get("competitive_landscape", {})

    # 招标历史
    unified["history_tenders"] = profile.get("history_tenders", [])

    # 元数据
    unified["has_tender_data"] = True
    unified["last_updated"] = profile.get("last_updated", datetime.now().strftime("%Y-%m-%d"))

    return unified


def unify_crm_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """将CRM画像转为统一格式"""
    unified = {**UNIFIED_PROFILE_SCHEMA}

    # 核心标识
    unified["customer_id"] = profile.get("customer_id", "")
    unified["customer_name"] = profile.get("customer_name", "")

    # 基础信息
    unified["basic_info"]["credit_code"] = profile.get("basic_info", {}).get("credit_code", "")
    unified["basic_info"]["customer_type"] = profile.get("basic_info", {}).get("customer_type", "")
    unified["basic_info"]["is_from_crm"] = True

    # 联系人信息
    unified["contact_info"]["contacts"] = profile.get("contact_info", {}).get("contacts", [])

    # CRM数据
    crm = profile.get("crm_profile", {})
    opportunities = crm.get("opportunities", [])
    leads = crm.get("leads", [])

    # 商机汇总
    unified["crm_history"]["opportunities"] = opportunities
    unified["value_profile"]["opportunity_count"] = len(opportunities)
    unified["value_profile"]["opportunity_value"] = sum(
        float(o.get("value", 0) or 0) for o in opportunities
    )

    # 线索汇总
    unified["crm_history"]["leads"] = leads
    unified["value_profile"]["lead_count"] = len(leads)
    unified["value_profile"]["lead_value"] = sum(
        float(l.get("lead_value", 0) or 0) for l in leads
    )

    # 销售关系
    sales_rel = profile.get("sales_relationship", {})
    unified["sales_relationship"]["all_owners"] = sales_rel.get("owners", [])
    unified["sales_relationship"]["all_salespersons"] = sales_rel.get("salespersons", [])
    unified["sales_relationship"]["primary_sales"] = sales_rel.get("owners", [None])[0] if sales_rel.get("owners") else ""
    unified["sales_relationship"]["secondary_sales"] = sales_rel.get("salespersons", [None])[0] if sales_rel.get("salespersons") else ""

    # 元数据
    unified["has_crm_data"] = True
    unified["last_updated"] = profile.get("last_updated", datetime.now().strftime("%Y-%m-%d"))

    return unified


def merge_profiles(tender_profile: Dict[str, Any], crm_profile: Dict[str, Any]) -> Dict[str, Any]:
    """合并招标画像和CRM画像"""
    # 以招标画像为基础
    unified = unify_tender_profile(tender_profile)

    # 融合CRM数据
    if crm_profile:
        crm_unified = unify_crm_profile(crm_profile)

        # 合并basic_info
        unified["basic_info"]["customer_type"] = (
            crm_unified["basic_info"]["customer_type"]
            or unified["basic_info"].get("customer_type", "")
        )
        unified["basic_info"]["is_from_crm"] = True

        # 合并联系人
        existing_names = {c["name"] for c in unified["contact_info"]["contacts"]}
        for contact in crm_unified["contact_info"]["contacts"]:
            if contact["name"] and contact["name"] not in existing_names:
                unified["contact_info"]["contacts"].append(contact)
                existing_names.add(contact["name"])

        # 合并CRM价值
        unified["value_profile"]["opportunity_value"] = crm_unified["value_profile"]["opportunity_value"]
        unified["value_profile"]["opportunity_count"] = crm_unified["value_profile"]["opportunity_count"]
        unified["value_profile"]["lead_value"] = crm_unified["value_profile"]["lead_value"]
        unified["value_profile"]["lead_count"] = crm_unified["value_profile"]["lead_count"]

        # 合并销售关系
        unified["sales_relationship"]["all_owners"] = crm_unified["sales_relationship"]["all_owners"]
        unified["sales_relationship"]["all_salespersons"] = crm_unified["sales_relationship"]["all_salespersons"]
        unified["sales_relationship"]["primary_sales"] = crm_unified["sales_relationship"]["primary_sales"]
        unified["sales_relationship"]["secondary_sales"] = crm_unified["sales_relationship"]["secondary_sales"]

        # 合并CRM历史
        unified["crm_history"] = crm_unified["crm_history"]

        unified["has_crm_data"] = True

    return unified


def unify_all_profiles(tender_file: str, crm_file: str, output_file: str) -> Dict[str, Any]:
    """
    统一所有画像

    Args:
        tender_file: 招标画像JSONL文件
        crm_file: CRM画像JSONL文件
        output_file: 输出文件

    Returns:
        处理统计
    """
    from ..utils.jsonl_helper import load_jsonl, save_jsonl

    # 加载数据
    tender_profiles = load_jsonl(tender_file)
    crm_profiles = load_jsonl(crm_file)

    logger.info(f"招标画像: {len(tender_profiles)}个, CRM画像: {len(crm_profiles)}个")

    # 构建CRM索引（按客户名称）
    crm_by_name = {}
    crm_by_code = {}
    for p in crm_profiles:
        name = p.get("customer_name", "")
        code = p.get("customer_id", "")
        if name:
            crm_by_name[name] = p
        if code:
            crm_by_code[code] = p

    # 统计
    stats = {
        "total": 0,
        "tender_only": 0,
        "crm_only": 0,
        "merged": 0
    }

    unified_profiles = []

    # 处理招标画像
    for tp in tender_profiles:
        customer_name = tp.get("customer_name", "")
        credit_code = tp.get("basic_info", {}).get("credit_code", "")

        # 查找匹配的CRM数据
        crm_match = None
        if credit_code and credit_code in crm_by_code:
            crm_match = crm_by_code[credit_code]
        elif customer_name in crm_by_name:
            crm_match = crm_by_name[customer_name]

        if crm_match:
            # 合并
            unified = merge_profiles(tp, crm_match)
            stats["merged"] += 1
        else:
            # 仅招标
            unified = unify_tender_profile(tp)
            stats["tender_only"] += 1

        unified_profiles.append(unified)

    # 处理仅CRM的客户
    tender_names = {p.get("customer_name", "") for p in tender_profiles}
    tender_codes = {p.get("basic_info", {}).get("credit_code", "") for p in tender_profiles}

    for cp in crm_profiles:
        name = cp.get("customer_name", "")
        code = cp.get("customer_id", "")

        # 已经被合并的跳过
        if name in tender_names or code in tender_codes:
            continue

        unified = unify_crm_profile(cp)
        unified_profiles.append(unified)
        stats["crm_only"] += 1

    stats["total"] = len(unified_profiles)

    # 保存
    save_jsonl(unified_profiles, output_file)

    logger.info(f"统一完成: {stats}")
    return stats


def unify_single_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """统一单个画像格式"""
    has_tender = bool(profile.get("history_tenders") or profile.get("demand_profile"))
    has_crm = bool(profile.get("crm_profile") or profile.get("crm_history"))

    if has_tender and has_crm:
        # 两种数据都有，需要合并
        # 这种情况比较复杂，需要传入两个版本
        return profile
    elif has_tender:
        return unify_tender_profile(profile)
    elif has_crm:
        return unify_crm_profile(profile)
    else:
        return profile
