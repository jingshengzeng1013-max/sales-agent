# -*- coding: utf-8 -*-
"""
将解析后的附件内容扩充到数据库
生成 tender_chunks 记录用于 RAG 检索
"""

import os
import sys
import json
import sqlite3

# 添加项目根目录和 src 目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)
from config import DB_PATH

# 解析结果目录
PARSED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "output", "parsed_attachments")


def init_attachment_chunks_table():
    """确保附件分块表存在"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # tender_chunks 表应该已存在，这里只做检查
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='tender_chunks'
    """)

    if not cursor.fetchone():
        print("[ERROR] tender_chunks 表不存在，请先运行 generate_chunks.py")
        conn.close()
        return False

    conn.close()
    print("[DB] tender_chunks table ready")
    return True


def load_parsed_results():
    """加载解析结果汇总"""
    summary_path = os.path.join(PARSED_DIR, "parsing_summary.json")

    if not os.path.exists(summary_path):
        print(f"[ERROR] 解析汇总文件不存在：{summary_path}")
        print("[INFO] 请先运行 parse_attachments.py")
        return []

    with open(summary_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"[INFO] 加载 {len(data)} 条解析结果")
    return data


def read_parsed_text(parsed_text_path):
    """读取解析后的文本"""
    if not os.path.exists(parsed_text_path):
        return None

    with open(parsed_text_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()


def chunk_text(text, chunk_size=1500, overlap=150):
    """
    将长文本分块（针对 RAG 检索优化）

    Args:
        text: 待分块的文本
        chunk_size: 每块目标字符数（默认 1500，适合 RAG 检索）
        overlap: 块间重叠字符数（默认 150，约 10%，保证边界信息不丢失）

    Returns:
        分块后的列表，每项包含 text 和 order
    """
    if not text:
        return []

    # 清理文本
    text = text.strip()
    if len(text) <= chunk_size:
        return [{"text": text, "order": 1}]

    chunks = []
    start = 0
    order = 1

    while start < len(text):
        end = start + chunk_size

        # 尝试在语义边界处切断（优先级从高到低）
        if end < len(text):
            cut_pos = None

            # 1. 优先在段落边界切断（双换行）
            search_text = text[start:end]
            para_match = search_text.rfind('\n\n')
            if para_match > chunk_size // 3:  # 至少在 1/3 位置之后
                cut_pos = start + para_match + 2

            # 2. 其次在单换行处切断
            if cut_pos is None:
                line_match = search_text.rfind('\n')
                if line_match > chunk_size // 2:
                    cut_pos = start + line_match + 1

            # 3. 在句子边界切断（句号、感叹号、问号）
            if cut_pos is None:
                for sep in ['。', '！', '？', '.', '!', '?']:
                    sep_match = search_text.rfind(sep)
                    if sep_match > chunk_size // 2:
                        cut_pos = start + sep_match + 1
                        break

            # 4. 使用切断位置（如果有）
            if cut_pos is not None:
                end = cut_pos

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append({
                "text": chunk_text,
                "order": order
            })
            order += 1

        start = end - overlap

    return chunks


def save_attachment_chunks(tender_id, file_name, text, source_path):
    """将附件内容保存为 chunks"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查是否已存在该附件的 chunks
    cursor.execute("""
        SELECT COUNT(*) FROM tender_chunks
        WHERE tender_id = ?
        AND chunk_type = 'attachment_content'
        AND json_extract(metadata_json, '$.source_file') = ?
    """, (tender_id, file_name))

    existing = cursor.fetchone()[0]
    if existing > 0:
        print(f"  [SKIP] 已存在 {existing} 条 chunks")
        conn.close()
        return 0

    # 分块
    chunks = chunk_text(text)

    if not chunks:
        conn.close()
        return 0

    # 插入数据库
    inserted = 0
    for chunk in chunks:
        metadata = {
            "source_file": file_name,
            "source_path": source_path,
            "chunk_size": len(chunk["text"])
        }

        cursor.execute("""
            INSERT INTO tender_chunks (tender_id, chunk_type, chunk_text, chunk_order, metadata_json)
            VALUES (?, ?, ?, ?, ?)
        """, (
            tender_id,
            "attachment_content",
            chunk["text"],
            chunk["order"],
            json.dumps(metadata, ensure_ascii=False)
        ))
        inserted += 1

    conn.commit()
    conn.close()

    print(f"  [INSERTED] {inserted} chunks for {file_name}")
    return inserted


def import_all_attachments():
    """导入所有附件内容到数据库"""
    # 检查表是否存在
    if not init_attachment_chunks_table():
        return

    # 加载解析结果
    results = load_parsed_results()

    if not results:
        print("[INFO] 无数据可导入")
        return

    print(f"\n{'='*60}")
    print("开始导入附件内容到 tender_chunks")
    print(f"{'='*60}\n")

    stats = {
        'total': len(results),
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'total_chunks': 0
    }

    for idx, item in enumerate(results, 1):
        tender_id = item.get('tender_id', '')
        file_name = item.get('source_file', '')
        parsed_text_path = item.get('parsed_text_path', '')

        if not parsed_text_path or not os.path.exists(parsed_text_path):
            print(f"[{idx}/{len(results)}] [SKIP] 解析文件不存在")
            stats['skipped'] += 1
            continue

        print(f"[{idx}/{len(results)}] Tender ID: {tender_id}, File: {file_name}")

        # 读取解析文本
        text = read_parsed_text(parsed_text_path)

        if not text:
            print(f"  [FAIL] 文本为空或读取失败")
            stats['failed'] += 1
            continue

        # 保存到 chunks
        chunks_count = save_attachment_chunks(tender_id, file_name, text, parsed_text_path)

        if chunks_count > 0:
            stats['success'] += 1
            stats['total_chunks'] += chunks_count
        else:
            stats['skipped'] += 1

    print(f"\n{'='*60}")
    print("导入完成!")
    print(f"{'='*60}")
    print(f"总数：{stats['total']}")
    print(f"成功：{stats['success']}")
    print(f"失败：{stats['failed']}")
    print(f"跳过：{stats['skipped']}")
    print(f"新增 chunks: {stats['total_chunks']}")
    print(f"{'='*60}")

    return stats


def verify_attachment_chunks():
    """验证附件 chunks 导入情况"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 统计附件 chunks 总数
    cursor.execute("""
        SELECT COUNT(*) FROM tender_chunks
        WHERE chunk_type = 'attachment_content'
    """)
    total = cursor.fetchone()[0]

    # 按 tender_id 统计
    cursor.execute("""
        SELECT tender_id, COUNT(*) as cnt,
               json_extract(metadata_json, '$.source_file') as source_file
        FROM tender_chunks
        WHERE chunk_type = 'attachment_content'
        GROUP BY tender_id
        ORDER BY cnt DESC
        LIMIT 10
    """)
    top_tenders = cursor.fetchall()

    conn.close()

    print("="*60)
    print("附件 Chunks 验证")
    print("="*60)
    print(f"\n总附件 chunks 数：{total}")

    if top_tenders:
        print("\nTenders 附件 Top 10:")
        for i, (tender_id, cnt, file) in enumerate(top_tenders, 1):
            print(f"  {i}. Tender {tender_id}: {cnt} chunks ({file})")

    print("\n" + "="*60)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='导入附件内容到数据库')
    parser.add_argument('--import', dest='do_import', action='store_true', help='导入附件内容')
    parser.add_argument('--verify', action='store_true', help='验证导入结果')

    args = parser.parse_args()

    if args.verify:
        verify_attachment_chunks()
    elif args.do_import:
        import_all_attachments()
    else:
        # 默认执行导入
        import_all_attachments()


if __name__ == "__main__":
    main()
