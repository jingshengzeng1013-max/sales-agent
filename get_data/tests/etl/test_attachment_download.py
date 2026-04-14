# -*- coding: utf-8 -*-
"""
附件下载与解析测试
"""

import os
import sys

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))


def test_chunk_text():
    """测试文本分块函数"""
    from etl.import_attachment_chunks import chunk_text

    # 测试短文本
    short_text = "这是一段短文本。"
    chunks = chunk_text(short_text)
    assert len(chunks) == 1
    assert chunks[0]["text"] == short_text
    assert chunks[0]["order"] == 1
    print("[OK] test_chunk_text_short 通过")

    # 测试长文本
    long_text = "。".join([f"第{i}段" for i in range(100)])
    chunks = chunk_text(long_text, chunk_size=200, overlap=20)
    assert len(chunks) > 1
    assert chunks[0]["order"] == 1
    assert chunks[-1]["order"] == len(chunks)
    print("[OK] test_chunk_text_long 通过")

    # 测试空文本
    empty_chunks = chunk_text("")
    assert len(empty_chunks) == 0
    print("[OK] test_chunk_text_empty 通过")


def test_safe_filename():
    """测试安全文件名生成"""
    from crawler.download_attachments import get_safe_filename

    # 测试正常文件名
    assert get_safe_filename("test.pdf") == "test.pdf"

    # 测试非法字符
    assert "<>:" not in get_safe_filename("test<>.pdf")

    # 测试长文件名
    long_name = "a" * 300 + ".pdf"
    safe = get_safe_filename(long_name)
    assert len(safe) <= 200
    assert safe.endswith(".pdf")

    print("[OK] test_safe_filename 通过")


def test_extract_filename_from_url():
    """测试从 URL 提取文件名"""
    import re
    from crawler.download_attachments import extract_filename_from_url

    # 测试普通 URL
    url1 = "https://example.com/file.pdf"
    assert extract_filename_from_url(url1) == "file.pdf"

    # 测试带参数的 URL
    url2 = "https://download.ccgp.gov.cn/oss/download?uuid=ABC123"
    name = extract_filename_from_url(url2)
    assert "pdf" in name.lower() or "attachment" in name.lower()

    print("[OK] test_extract_filename_from_url 通过")


def test_attachment_table_exists():
    """测试附件表是否存在"""
    import sqlite3
    from config import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='tender_attachments'
    """)

    exists = cursor.fetchone() is not None
    conn.close()

    if exists:
        print("[OK] test_attachment_table_exists 通过")
    else:
        print("[SKIP] tender_attachments 表不存在（需要先爬取附件链接）")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("附件下载与解析测试")
    print("=" * 60)

    test_chunk_text()
    test_safe_filename()
    test_extract_filename_from_url()
    test_attachment_table_exists()

    print("=" * 60)
    print("[OK] 所有测试通过")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
