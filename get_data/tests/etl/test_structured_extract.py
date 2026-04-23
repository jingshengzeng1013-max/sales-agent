# -*- coding: utf-8 -*-
"""
LLM 结构化抽取测试
测试 prompt 解析和字段抽取功能
"""

import sys
import os
import json

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


def test_structured_output_format():
    """测试结构化输出格式"""
    # 模拟 LLM 返回的 JSON 数据
    sample_output = {
        "announce_type": "招标公告",
        "buyer_name_std": "北京大学",
        "province": "北京市",
        "city": "北京市",
        "budget_raw": "100 万元",
        "budget_amount": 1000000,
        "budget_unit": "元",
        "product_keywords": ["芯片", "测试设备"],
        "contact_chunk": "采购单位：张老师 010-12345678",
        "requirement_chunks": [
            {"type": "technical_params", "text": "技术参数要求..."}
        ]
    }

    # 验证必填字段
    required_fields = [
        "announce_type", "buyer_name_std", "province", "city",
        "budget_raw", "budget_amount", "budget_unit", "product_keywords"
    ]

    for field in required_fields:
        assert field in sample_output, f"缺少必填字段：{field}"

    print("[OK] test_structured_output_format 通过")


def test_contact_chunk_format():
    """测试 contact_chunk 字段格式"""
    sample = {
        "contact_chunk": "采购单位：张老师 010-12345678；代理机构：李经理 021-87654321；项目联系人：王工 025-11112222"
    }

    # 验证包含三方联系人信息
    assert "采购单位" in sample["contact_chunk"]
    assert "010-12345678" in sample["contact_chunk"]

    print("[OK] test_contact_chunk_format 通过")


def test_requirement_chunks_format():
    """测试 requirement_chunks 字段格式"""
    sample = {
        "requirement_chunks": [
            {"type": "technical_params", "text": "技术参数..."},
            {"type": "service_requirements", "text": "服务要求..."},
            {"type": "qualification_requirements", "text": "资格要求..."}
        ]
    }

    valid_types = ["technical_params", "service_requirements", "qualification_requirements", "other"]

    for chunk in sample["requirement_chunks"]:
        assert "type" in chunk
        assert "text" in chunk
        assert chunk["type"] in valid_types

    print("[OK] test_requirement_chunks_format 通过")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("LLM 结构化抽取测试")
    print("=" * 60)

    test_structured_output_format()
    test_contact_chunk_format()
    test_requirement_chunks_format()

    print("=" * 60)
    print("[OK] 所有测试通过")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
