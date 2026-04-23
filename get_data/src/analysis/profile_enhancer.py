# -*- coding: utf-8 -*-
"""
客户画像增强器

融合CRM数据（商机/线索）与招标数据，生成增强版客户画像。
"""

import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

from .crm_loader import CRMLoader, get_default_crm_loader

logger = logging.getLogger("analysis.profile_enhancer")


class ProfileEnhancer:
    """客户画像增强器"""

    def __init__(self, crm_loader: CRMLoader = None):
        """
        初始化画像增强器

        Args:
            crm_loader: CRM数据加载器
        """
        self.crm_loader = crm_loader or get_default_crm_loader()
        self._crm_by_code: Dict[str, Dict] = {}
        self._built = False

    def _build_crm_index(self):
        """构建CRM数据索引"""
        if self._built:
            return

        all_codes = self.crm_loader.get_all_credit_codes()
        for code in all_codes:
            self._crm_by_code[code] = {
                "opportunities": self.crm_loader.get_business_by_credit_code(code),
                "leads": self.crm_loader.get_leads_by_credit_code(code),
            }
        self._built = True
        logger.info(f"CRM索引构建完成: {len(self._crm_by_code)} 个客户")

    def _calc_opportunity_summary(self, opportunities: List[Dict]) -> Dict[str, Any]:
        """计算商机汇总统计"""
        if not opportunities:
            return {
                "total_count": 0,
                "total_value": 0.0,
                "active_count": 0,
                "closed_count": 0,
                "signed_count": 0,
                "conversion_rate": 0.0,
            }

        total_count = len(opportunities)
        total_value = sum(o.get('value', 0) for o in opportunities)
        active_count = len([o for o in opportunities if o.get('opportunity_status') == '进行中'])
        closed_count = len([o for o in opportunities if o.get('opportunity_status') == '关闭'])
        signed_count = len([o for o in opportunities if o.get('followup_status') == '签约'])

        conversion_rate = signed_count / total_count if total_count > 0 else 0.0

        return {
            "total_count": total_count,
            "total_value": total_value,
            "active_count": active_count,
            "closed_count": closed_count,
            "signed_count": signed_count,
            "conversion_rate": round(conversion_rate, 2),
        }

    def _calc_lead_summary(self, leads: List[Dict]) -> Dict[str, Any]:
        """计算线索汇总统计"""
        if not leads:
            return {
                "total_count": 0,
                "total_value": 0.0,
                "active_count": 0,
                "converted_count": 0,
                "abandoned_count": 0,
                "conversion_rate": 0.0,
            }

        total_count = len(leads)
        total_value = sum(l.get('lead_value', 0) for l in leads if l.get('lead_value'))
        active_count = len([l for l in leads if l.get('lead_status') == '跟进中'])
        converted_count = len([l for l in leads if l.get('lead_status') == '已转化'])
        abandoned_count = len([l for l in leads if l.get('lead_status') == '已放弃'])

        conversion_rate = converted_count / total_count if total_count > 0 else 0.0

        return {
            "total_count": total_count,
            "total_value": total_value,
            "active_count": active_count,
            "converted_count": converted_count,
            "abandoned_count": abandoned_count,
            "conversion_rate": round(conversion_rate, 2),
        }

    def _extract_contacts(self, opportunities: List[Dict], leads: List[Dict]) -> List[Dict[str, Any]]:
        """提取联系人列表"""
        contacts_map = {}

        for opp in opportunities:
            person = opp.get('contact_person', '')
            if person and person != 'nan':
                credit_code = opp.get('credit_code', '')
                key = f"{credit_code}:{person}"
                if key not in contacts_map:
                    contacts_map[key] = {
                        "name": person,
                        "position": opp.get('contact_position', ''),
                        "source": "商机列表",
                        "customer_name": opp.get('customer_name', ''),
                    }

        for lead in leads:
            person = lead.get('contact_person', '')
            if person and person != 'nan':
                credit_code = lead.get('credit_code', '')
                key = f"{credit_code}:{person}"
                if key not in contacts_map:
                    contacts_map[key] = {
                        "name": person,
                        "position": lead.get('contact_position', ''),
                        "source": "线索列表",
                        "customer_name": lead.get('customer_name', ''),
                    }

        return list(contacts_map.values())

    def _determine_customer_segment(self, opportunities: List[Dict], leads: List[Dict]) -> Optional[str]:
        """确定客户分类"""
        # 优先从商机获取
        for opp in opportunities:
            seg = opp.get('customer_type', '')
            if seg and seg != 'nan':
                return seg

        # 其次从线索获取
        for lead in leads:
            seg = lead.get('customer_segment', '')
            if seg and seg != 'nan':
                return seg

        return None

    def _determine_sales_relationship(self, opportunities: List[Dict], leads: List[Dict]) -> Dict[str, Any]:
        """确定销售关系"""
        all_owners = []
        all_salespersons = []

        for opp in opportunities:
            owner = opp.get('owner', '')
            if owner and owner != 'nan':
                all_owners.append(owner)

        for lead in leads:
            salesperson = lead.get('salesperson', '')
            if salesperson and salesperson != 'nan':
                all_salespersons.append(salesperson)

        # 获取最早和最晚时间
        all_times = []
        for opp in opportunities:
            t = opp.get('report_time', '')
            if t and t != 'nan':
                all_times.append(t)
        for lead in leads:
            t = lead.get('lead_acquisition_time', '')
            if t and t != 'nan':
                all_times.append(t)

        # 确定合作紧密度
        total_crm = len(opportunities) + len(leads)
        if total_crm >= 5:
            relationship_level = "深度合作"
        elif total_crm >= 2:
            relationship_level = "正常合作"
        else:
            relationship_level = "初步接触"

        return {
            "primary_sales": all_owners[0] if all_owners else None,
            "secondary_sales": all_salespersons[0] if all_salespersons else None,
            "all_owners": list(set(all_owners)),
            "all_salespersons": list(set(all_salespersons)),
            "first_contact_date": min(all_times) if all_times else None,
            "last_followup_date": max(all_times) if all_times else None,
            "relationship_level": relationship_level,
            "total_interactions": total_crm,
        }

    def enhance_profile(self, existing_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        增强现有客户画像

        Args:
            existing_profile: 基于招标数据的现有画像

        Returns:
            增强后的画像
        """
        self._build_crm_index()

        credit_code = existing_profile.get('basic_info', {}).get('credit_code')
        if not credit_code:
            # 尝试从客户名称匹配
            customer_name = existing_profile.get('customer_name', '')
            credit_code = self._find_credit_code_by_name(customer_name)

        if not credit_code or credit_code not in self._crm_by_code:
            # 没有CRM数据，返回原画像并标记
            existing_profile['crm_profile'] = None
            existing_profile['has_crm_data'] = False
            return existing_profile

        crm_data = self._crm_by_code[credit_code]
        opportunities = crm_data['opportunities']
        leads = crm_data['leads']

        # 构建CRM画像
        crm_profile = {
            "opportunities": opportunities,
            "leads": leads,
            "opportunity_summary": self._calc_opportunity_summary(opportunities),
            "lead_summary": self._calc_lead_summary(leads),
        }

        # 融合到现有画像
        enhanced = existing_profile.copy()
        enhanced['crm_profile'] = crm_profile
        enhanced['has_crm_data'] = True

        # 更新basic_info
        if 'basic_info' not in enhanced:
            enhanced['basic_info'] = {}
        enhanced['basic_info']['credit_code'] = credit_code

        # 确定客户分类
        segment = self._determine_customer_segment(opportunities, leads)
        if segment:
            enhanced['basic_info']['customer_segment'] = segment

        # 添加联系人
        enhanced['contact_info'] = {
            "contacts": self._extract_contacts(opportunities, leads)
        }

        # 添加销售关系
        enhanced['sales_relationship'] = self._determine_sales_relationship(opportunities, leads)

        # 更新时间
        enhanced['last_updated'] = datetime.now().strftime('%Y-%m-%d')

        return enhanced

    def _find_credit_code_by_name(self, customer_name: str) -> Optional[str]:
        """根据客户名称查找信用代码"""
        self._build_crm_index()
        for code, data in self._crm_by_code.items():
            # 检查商机
            for opp in data['opportunities']:
                if customer_name in opp.get('customer_name', ''):
                    return code
            # 检查线索
            for lead in data['leads']:
                if customer_name in lead.get('customer_name', ''):
                    return code
        return None

    def create_crm_only_profile(self, credit_code: str) -> Optional[Dict[str, Any]]:
        """
        为只有CRM数据但没有招标记录的客户创建画像

        Args:
            credit_code: 客户信用代码

        Returns:
            画像字典，如果没有数据返回None
        """
        self._build_crm_index()

        if credit_code not in self._crm_by_code:
            return None

        crm_data = self._crm_by_code[credit_code]
        opportunities = crm_data['opportunities']
        leads = crm_data['leads']

        if not opportunities and not leads:
            return None

        # 获取客户名称
        customer_name = None
        if opportunities:
            customer_name = opportunities[0].get('customer_name')
        if not customer_name and leads:
            customer_name = leads[0].get('customer_name')

        # 构建基础画像
        profile = {
            "customer_id": credit_code,
            "customer_name": customer_name or "未知客户",
            "basic_info": {
                "credit_code": credit_code,
                "customer_segment": self._determine_customer_segment(opportunities, leads),
            },
            "contact_info": {
                "contacts": self._extract_contacts(opportunities, leads)
            },
            "crm_profile": {
                "opportunities": opportunities,
                "leads": leads,
                "opportunity_summary": self._calc_opportunity_summary(opportunities),
                "lead_summary": self._calc_lead_summary(leads),
            },
            "sales_relationship": self._determine_sales_relationship(opportunities, leads),
            "tender_profile": None,
            "history_tenders": [],
            "has_crm_data": True,
            "has_tender_data": False,
            "last_updated": datetime.now().strftime('%Y-%m-%d'),
        }

        return profile


def enhance_all_profiles(
    existing_profile_file: Path,
    output_file: Path,
    crm_loader: CRMLoader = None
) -> Dict[str, Any]:
    """
    批量增强所有现有画像

    Args:
        existing_profile_file: 现有画像JSONL文件
        output_file: 输出文件路径
        crm_loader: CRM加载器

    Returns:
        处理统计
    """
    from ..utils.jsonl_helper import load_jsonl, save_jsonl

    # 加载现有画像
    existing_profiles = load_jsonl(str(existing_profile_file))
    logger.info(f"加载了 {len(existing_profiles)} 个现有画像")

    # 初始化增强器
    enhancer = ProfileEnhancer(crm_loader)

    # 统计
    stats = {
        "total": len(existing_profiles),
        "enhanced": 0,
        "no_crm_match": 0,
        "crm_only": 0,
    }

    # 收集所有CRM信用代码
    enhancer._build_crm_index()
    all_crm_codes = set(enhancer._crm_by_code.keys())

    # 增强现有画像
    enhanced_profiles = []
    for profile in existing_profiles:
        credit_code = profile.get('basic_info', {}).get('credit_code')
        if credit_code and credit_code in all_crm_codes:
            enhanced = enhancer.enhance_profile(profile)
            enhanced['source'] = 'tender+crm'
            enhanced_profiles.append(enhanced)
            stats['enhanced'] += 1
        else:
            profile['has_crm_data'] = False
            profile['crm_profile'] = None
            enhanced_profiles.append(profile)
            stats['no_crm_match'] += 1

    # 为只有CRM数据的客户创建画像
    tender_codes = set()
    for p in existing_profiles:
        cc = p.get('basic_info', {}).get('credit_code')
        if cc:
            tender_codes.add(cc)

    crm_only_codes = all_crm_codes - tender_codes
    logger.info(f"发现 {len(crm_only_codes)} 个只有CRM数据没有招标记录的客户")

    crm_only_profiles = []
    for code in crm_only_codes:
        profile = enhancer.create_crm_only_profile(code)
        if profile:
            crm_only_profiles.append(profile)
            stats['crm_only'] += 1

    # 合并输出
    all_profiles = enhanced_profiles + crm_only_profiles
    save_jsonl(all_profiles, str(output_file))

    logger.info(f"画像增强完成: 共 {len(all_profiles)} 个")
    logger.info(f"  - 原有画像已增强: {stats['enhanced']}")
    logger.info(f"  - 原有画像无CRM匹配: {stats['no_crm_match']}")
    logger.info(f"  - 新增CRM专属客户: {stats['crm_only']}")

    return stats
