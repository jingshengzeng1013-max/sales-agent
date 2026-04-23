# -*- coding: utf-8 -*-
"""
CRM数据加载器

加载商机列表和线索列表Excel，转换为结构化数据。
"""

import logging
import pandas as pd
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("analysis.crm_loader")


class CRMLoader:
    """CRM数据加载器"""

    def __init__(self, business_file: Path = None, lead_file: Path = None):
        """
        初始化CRM加载器

        Args:
            business_file: 商机列表Excel文件路径
            lead_file: 线索列表Excel文件路径
        """
        self.business_file = business_file
        self.lead_file = lead_file
        self._business_data: List[Dict] = []
        self._lead_data: List[Dict] = []
        self._loaded = False

    def _safe_get_float(self, value, default=0.0):
        """安全获取浮点数"""
        if pd.isna(value):
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _safe_get_str(self, value):
        """安全获取字符串"""
        if pd.isna(value):
            return ''
        return str(value)

    def _parse_business_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """解析商机列表Excel"""
        try:
            df = pd.read_excel(file_path, header=1, dtype=str)  # 全部作为字符串读取避免类型推断问题
            df = df.dropna(subset=['客户统一信用代码'])  # 只保留有信用代码的

            records = []
            for _, row in df.iterrows():
                record = {
                    "opportunity_id": self._safe_get_str(row.get('商机编号')),
                    "opportunity_name": self._safe_get_str(row.get('商机名称')),
                    "lead_id": self._safe_get_str(row.get('关联线索编号')),
                    "owner": self._safe_get_str(row.get('跟进人员')),
                    "customer_name": self._safe_get_str(row.get('客户名称')),
                    "credit_code": self._safe_get_str(row.get('客户统一信用代码')),
                    "is_duplicate": self._safe_get_str(row.get('是否重复客户')) == '是',
                    "contact_person": self._safe_get_str(row.get('客户联系人')),
                    "contact_position": self._safe_get_str(row.get('联系人职位')),
                    "opportunity_status": self._safe_get_str(row.get('商机状态')),
                    "followup_status": self._safe_get_str(row.get('跟进状态')),
                    "planned_followup_date": self._safe_get_str(row.get('计划跟进时间')),
                    "report_time": self._safe_get_str(row.get('提报时间')),
                    "close_period": self._safe_get_str(row.get('商机封闭期')),
                    "lead_name": self._safe_get_str(row.get('关联线索名称')),
                    "value": self._safe_get_float(row.get('商机规模（元）')),
                    "is_linked": self._safe_get_str(row.get('是否关联商机')) == '是',
                    "linked_opportunity_id": self._safe_get_str(row.get('商机关联编号')),
                    "linked_opportunity_owner": self._safe_get_str(row.get('商机关联负责人')),
                    "followup_feedback": self._safe_get_str(row.get('商机跟进反馈')),
                    "close_reason": self._safe_get_str(row.get('结束原因')),
                    "customer_type": self._safe_get_str(row.get('客户类型')),
                    "selling_products": self._safe_get_str(row.get('售卖产品')),
                    "selling_quantity": self._safe_get_float(row.get('售卖数量')),
                    "expected_usage": self._safe_get_str(row.get('预期使用终端')),
                    "updated_at": self._safe_get_str(row.get('更新时间')),
                }
                records.append(record)
            logger.info(f"商机列表加载完成: {len(records)} 条")
            return records
        except Exception as e:
            logger.error(f"加载商机列表失败: {e}")
            return []

    def _parse_lead_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """解析线索列表Excel"""
        try:
            df = pd.read_excel(file_path, header=1, dtype=str)  # 全部作为字符串读取避免类型推断问题
            df = df.dropna(subset=['客户统一信用代码'])

            records = []
            for _, row in df.iterrows():
                record = {
                    "lead_id": self._safe_get_str(row.get('线索编号')),
                    "lead_name": self._safe_get_str(row.get('线索名称')),
                    "reporter": self._safe_get_str(row.get('报备人员')),
                    "contact_phone": self._safe_get_str(row.get('联系方式')),
                    "customer_name": self._safe_get_str(row.get('客户名称')),
                    "credit_code": self._safe_get_str(row.get('客户统一信用代码')),
                    "is_duplicate": self._safe_get_str(row.get('是否重复客户')) == '是',
                    "contact_person": self._safe_get_str(row.get('客户联系人')),
                    "contact_position": self._safe_get_str(row.get('联系人职位')),
                    "lead_acquisition_time": self._safe_get_str(row.get('线索获取时间')),
                    "lead_report_time": self._safe_get_str(row.get('线索报备时间')),
                    "lead_status": self._safe_get_str(row.get('线索状态')),
                    "approval": self._safe_get_str(row.get('业务审批')),
                    "approval_result": self._safe_get_str(row.get('业务审批结果')),
                    "salesperson": self._safe_get_str(row.get('销售人员')),
                    "is_linked": self._safe_get_str(row.get('是否关联线索')) == '是',
                    "linked_lead_id": self._safe_get_str(row.get('线索关联编号')),
                    "linked_lead_owner": self._safe_get_str(row.get('线索关联负责人')),
                    "lead_description": self._safe_get_str(row.get('线索情况简述')),
                    "remark": self._safe_get_str(row.get('信息备注')),
                    "audit_note": self._safe_get_str(row.get('审核说明')),
                    "expected_start_time": self._safe_get_str(row.get('预计启动时间')),
                    "lead_value": self._safe_get_float(row.get('线索规模')),
                    "selling_quantity": self._safe_get_float(row.get('售卖数量')),
                    "updated_at": self._safe_get_str(row.get('更新时间')),
                    "selling_products": self._safe_get_str(row.get('售卖产品')),
                    "customer_segment": self._safe_get_str(row.get('客户类型')),
                }
                records.append(record)
            logger.info(f"线索列表加载完成: {len(records)} 条")
            return records
        except Exception as e:
            logger.error(f"加载线索列表失败: {e}")
            return []

    def load(self, business_file: Path = None, lead_file: Path = None):
        """加载CRM数据"""
        if self._loaded:
            return

        # 使用传入路径或默认路径
        business_file = business_file or self.business_file
        lead_file = lead_file or self.lead_file

        if business_file and Path(business_file).exists():
            self._business_data = self._parse_business_file(Path(business_file))

        if lead_file and Path(lead_file).exists():
            self._lead_data = self._parse_lead_file(Path(lead_file))

        self._loaded = True

    def get_business_by_credit_code(self, credit_code: str) -> List[Dict[str, Any]]:
        """根据信用代码获取商机列表"""
        if not self._loaded:
            self.load()
        return [b for b in self._business_data if b.get('credit_code') == credit_code]

    def get_leads_by_credit_code(self, credit_code: str) -> List[Dict[str, Any]]:
        """根据信用代码获取线索列表"""
        if not self._loaded:
            self.load()
        return [l for l in self._lead_data if l.get('credit_code') == credit_code]

    def get_all_credit_codes(self) -> set:
        """获取所有CRM客户信用代码"""
        if not self._loaded:
            self.load()
        business_codes = set(b.get('credit_code') for b in self._business_data if b.get('credit_code'))
        lead_codes = set(l.get('credit_code') for l in self._lead_data if l.get('credit_code'))
        return business_codes | lead_codes

    @property
    def business_count(self) -> int:
        return len(self._business_data)

    @property
    def lead_count(self) -> int:
        return len(self._lead_data)


def get_default_crm_loader() -> CRMLoader:
    """获取默认CRM加载器（使用docs目录下的文件）"""
    docs_dir = Path(__file__).resolve().parent.parent.parent / "docs"
    business_file = docs_dir / "商机列表20260422113444.xlsx"
    lead_file = docs_dir / "线索列表20260422113326.xlsx"

    loader = CRMLoader(business_file=business_file, lead_file=lead_file)
    loader.load()
    return loader
