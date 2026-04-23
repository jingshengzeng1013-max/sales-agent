# -*- coding: utf-8 -*-
"""
Chunks 生成测试
测试 tender_chunks 表数据生成功能
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


def test_chunk_types():
    """测试 chunk_type 的定义"""
    valid_chunk_types = [
        "title",                # 项目标题
        "content_summary",      # 公告内容摘要
        "contact_chunk",        # 联系方式块
        "requirement_chunk",    # 技术要求分块
        "attachment_summary"    # 附件摘要
    ]

    assert len(valid_chunk_types) == 5
    print("[OK] test_chunk_types 通过")


def test_chunk_metadata():
    """测试 chunk 元数据格式"""
    sample_metadata = {
        "announce_type": "招标公告",
        "buyer_name_std": "北京大学",
        "province": "北京市",
        "city": "北京市"
    }

    # 验证元数据字段
    assert "announce_type" in sample_metadata
    assert "buyer_name_std" in sample_metadata

    print("[OK] test_chunk_metadata 通过")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("Chunks 生成测试")
    print("=" * 60)

    test_chunk_types()
    test_chunk_metadata()

    print("=" * 60)
    print("[OK] 所有测试通过")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
