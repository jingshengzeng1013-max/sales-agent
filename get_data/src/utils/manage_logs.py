# -*- coding: utf-8 -*-
"""
日志管理工具
- 查看日志列表
- 清理旧日志
- 合并日志文件
"""

import os
import sys
import argparse
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logger import LOGS_DIR


def list_logs(days: int = 7):
    """列出指定天数内的日志文件"""
    print(f"\n{'='*60}")
    print(f"日志目录：{LOGS_DIR}")
    print(f"时间范围：最近 {days} 天")
    print(f"{'='*60}\n")

    if not os.path.exists(LOGS_DIR):
        print("日志目录不存在")
        return

    cutoff = datetime.now().timestamp() - (days * 86400)
    logs = []

    for filename in os.listdir(LOGS_DIR):
        if filename.endswith('.log'):
            filepath = os.path.join(LOGS_DIR, filename)
            mtime = os.path.getmtime(filepath)
            if mtime >= cutoff:
                size = os.path.getsize(filepath)
                logs.append((filename, size, mtime))

    # 按时间排序
    logs.sort(key=lambda x: x[2], reverse=True)

    if not logs:
        print("没有找到日志文件")
        return

    print(f"{'文件名':<50} {'大小':>10} {'修改时间':>20}")
    print("-" * 85)

    for filename, size, mtime in logs:
        size_str = f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB"
        time_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"{filename:<50} {size_str:>10} {time_str:>20}")

    print(f"\n共 {len(logs)} 个日志文件")


def clean_logs(days: int = 30, dry_run: bool = True):
    """
    清理旧日志文件

    Args:
        days: 保留天数
        dry_run: 仅预览，不实际删除
    """
    print(f"\n{'='*60}")
    if dry_run:
        print(f"预览：将清理 {days} 天前的日志")
    else:
        print(f"执行：清理 {days} 天前的日志")
    print(f"{'='*60}\n")

    if not os.path.exists(LOGS_DIR):
        print("日志目录不存在")
        return

    cutoff = datetime.now().timestamp() - (days * 86400)
    deleted_count = 0
    deleted_size = 0

    for filename in os.listdir(LOGS_DIR):
        if filename.endswith('.log'):
            filepath = os.path.join(LOGS_DIR, filename)
            mtime = os.path.getmtime(filepath)

            if mtime < cutoff:
                size = os.path.getsize(filepath)
                if dry_run:
                    print(f"[预览删除] {filename} ({size/1024:.1f} KB)")
                else:
                    os.remove(filepath)
                    print(f"[已删除] {filename} ({size/1024:.1f} KB)")
                deleted_count += 1
                deleted_size += size

    action = "将删除" if dry_run else "已删除"
    print(f"\n{action} {deleted_count} 个日志文件，释放空间 {deleted_size/1024:.1f} KB")


def tail_log(filename: str, lines: int = 50):
    """查看日志文件末尾内容"""
    filepath = os.path.join(LOGS_DIR, filename)

    if not os.path.exists(filepath):
        print(f"日志文件不存在：{filename}")
        return

    print(f"\n{'='*60}")
    print(f"文件：{filename}")
    print(f"{'='*60}\n")

    with open(filepath, 'r', encoding='utf-8') as f:
        all_lines = f.readlines()
        last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        for line in last_lines:
            print(line, end='')


def main():
    parser = argparse.ArgumentParser(description='日志管理工具')
    subparsers = parser.add_subparsers(dest='command', help='命令')

    # list 命令
    list_parser = subparsers.add_parser('list', help='列出日志文件')
    list_parser.add_argument('--days', type=int, default=7, help='显示最近 N 天的日志')

    # clean 命令
    clean_parser = subparsers.add_parser('clean', help='清理旧日志')
    clean_parser.add_argument('--days', type=int, default=30, help='保留最近 N 天的日志')
    clean_parser.add_argument('--execute', action='store_true', help='执行删除（默认仅预览）')

    # tail 命令
    tail_parser = subparsers.add_parser('tail', help='查看日志末尾内容')
    tail_parser.add_argument('file', help='日志文件名')
    tail_parser.add_argument('--lines', type=int, default=50, help='显示行数')

    args = parser.parse_args()

    if args.command == 'list':
        list_logs(args.days)
    elif args.command == 'clean':
        clean_logs(args.days, not args.execute)
    elif args.command == 'tail':
        tail_log(args.file, args.lines)
    else:
        parser.print_help()
        print("\n示例:")
        print("  python manage_logs.py list --days 7")
        print("  python manage_logs.py clean --days 30")
        print("  python manage_logs.py tail extract_20260401_161732.log")


if __name__ == "__main__":
    main()
