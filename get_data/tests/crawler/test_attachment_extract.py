# -*- coding: utf-8 -*-
"""
附件链接提取测试
测试 bizDownload 链接的 UUID 提取和下载链接生成功能
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.crawler.crawl_detail import extract_bizdownload_uuid


def test_extract_bizdownload_uuid_simple():
    """测试简单的 HTML 片段"""
    html = """
    <a class='bizDownload' href='' id='3048A92F3366BCAB13ACDB3164FD57' title='点击下载'>
        测试文件.pdf
    </a>
    """
    attachments = extract_bizdownload_uuid(html)
    assert len(attachments) == 1
    assert attachments[0]['uuid'] == '3048A92F3366BCAB13ACDB3164FD57'
    assert '测试文件.pdf' in attachments[0]['text']
    assert attachments[0]['url'] == 'https://download.ccgp.gov.cn/oss/download?uuid=3048A92F3366BCAB13ACDB3164FD57'
    print("[OK] test_extract_bizdownload_uuid_simple 通过")


def test_extract_bizdownload_uuid_multiple():
    """测试多个附件链接"""
    html = """
    <a class='bizDownload' href='' id='3048A92F3366BCAB13ACDB3164FD57' title='点击下载'>文件 1.pdf</a>
    <a class='bizDownload' href='' id='3E82874E7B452569C1B0585824F740' title='点击下载'>文件 2.pdf</a>
    """
    attachments = extract_bizdownload_uuid(html)
    assert len(attachments) == 2
    assert attachments[0]['uuid'] == '3048A92F3366BCAB13ACDB3164FD57'
    assert attachments[1]['uuid'] == '3E82874E7B452569C1B0585824F740'
    print("[OK] test_extract_bizdownload_uuid_multiple 通过")


def test_extract_bizdownload_uuid_empty():
    """测试没有 bizDownload 链接的情况"""
    html = "<p>没有附件链接</p>"
    attachments = extract_bizdownload_uuid(html)
    assert len(attachments) == 0
    print("[OK] test_extract_bizdownload_uuid_empty 通过")


def test_extract_bizdownload_uuid_from_file():
    """测试从实际 HTML 文件提取"""
    html_file = "html/光芯片工艺平台物业管理和特种设施服务采购项目单一来源采购征求意见公示.html"
    if not os.path.exists(html_file):
        print(f"⚠ 跳过 test_extract_bizdownload_uuid_from_file: 文件不存在 {html_file}")
        return

    with open(html_file, 'r', encoding='utf-8') as f:
        html = f.read()

    attachments = extract_bizdownload_uuid(html)
    assert len(attachments) >= 1, "应该至少找到 1 个附件 [FAIL]"

    for att in attachments:
        assert 'uuid' in att
        assert 'text' in att
        assert 'url' in att
        assert att['url'].startswith('https://download.ccgp.gov.cn/oss/download?uuid=')

    print(f"[OK] test_extract_bizdownload_uuid_from_file 通过 (找到 {len(attachments)} 个附件)")

    # 打印详细信息
    for att in attachments:
        print(f"  - {att['text'][:50]}...")
        print(f"    UUID: {att['uuid']}")
        print(f"    URL: {att['url']}")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("附件链接提取测试")
    print("=" * 60)

    test_extract_bizdownload_uuid_simple()
    test_extract_bizdownload_uuid_multiple()
    test_extract_bizdownload_uuid_empty()
    test_extract_bizdownload_uuid_from_file()

    print("=" * 60)
    print("[OK] 所有测试通过")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
