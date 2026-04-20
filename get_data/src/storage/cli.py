# -*- coding: utf-8 -*-
"""
入库命令行工具
将爬取的 JSON 数据导入 SQLite 数据库
"""

import argparse
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.import_tenders import (
    init_database,
    import_tenders_from_jsonl,
    update_tender_details_from_jsonl,
    import_attachments_from_jsonl,
    import_all
)


def main():
    parser = argparse.ArgumentParser(description='将爬取的 JSON 数据导入 SQLite 数据库')

    subparsers = parser.add_subparsers(dest='command', help='命令类型')

    # 初始化数据库
    subparsers.add_parser('init', help='初始化数据库表结构')

    # 导入招标列表
    list_parser = subparsers.add_parser('list', help='导入招标列表 (JSONL)')
    list_parser.add_argument('--file', type=str, help='JSONL 文件路径')

    # 更新招标详情
    detail_parser = subparsers.add_parser('detail', help='更新招标详情 (JSONL)')
    detail_parser.add_argument('--file', type=str, help='JSONL 文件路径')

    # 导入附件
    attach_parser = subparsers.add_parser('attachment', help='导入附件 (JSONL)')
    attach_parser.add_argument('--file', type=str, help='JSONL 文件路径')

    # 全部导入
    subparsers.add_parser('all', help='导入所有数据 (列表 + 详情 + 附件)')

    args = parser.parse_args()

    if args.command == 'init':
        init_database()

    elif args.command == 'list':
        import_tenders_from_jsonl(args.file)

    elif args.command == 'detail':
        update_tender_details_from_jsonl(args.file)

    elif args.command == 'attachment':
        import_attachments_from_jsonl(args.file)

    elif args.command == 'all':
        import_all()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
