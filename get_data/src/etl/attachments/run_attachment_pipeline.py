#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
附件处理完整流程脚本
一键执行：爬取链接 → 下载 → 解析 → 导入数据库
"""

import os
import sys
import subprocess

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_command(cmd, description):
    """运行命令并显示进度"""
    print(f"\n{'='*60}")
    print(f"[STEP] {description}")
    print(f"{'='*60}")
    print(f"运行：{cmd}\n")

    result = subprocess.run(cmd, shell=True, cwd=os.path.dirname(os.path.dirname(__file__)))

    if result.returncode != 0:
        print(f"\n[ERROR] 步骤失败：{description}")
        return False

    print(f"\n[OK] {description} 完成")
    return True


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='附件处理完整流程')
    parser.add_argument('--skip-crawl', action='store_true', help='跳过爬取链接')
    parser.add_argument('--skip-download', action='store_true', help='跳过下载')
    parser.add_argument('--skip-parse', action='store_true', help='跳过解析')
    parser.add_argument('--skip-import', action='store_true', help='跳过导入')
    parser.add_argument('--verify', action='store_true', help='验证最终结果')

    args = parser.parse_args()

    print("\n" + "="*60)
    print("附件处理完整流程")
    print("="*60)

    steps = []

    # 步骤 1：爬取附件链接
    if not args.skip_crawl:
        steps.append({
            "cmd": "python -m src.crawler.batch_crawl_attachments",
            "desc": "爬取附件链接"
        })
        steps.append({
            "cmd": "python -m src.crawler.batch_crawl_attachments --import",
            "desc": "导入附件链接到数据库"
        })

    # 步骤 2：下载附件
    if not args.skip_download:
        steps.append({
            "cmd": "python -m src.crawler.download_attachments --db",
            "desc": "下载附件到本地"
        })

    # 步骤 3：解析附件
    if not args.skip_parse:
        steps.append({
            "cmd": "python -m src.etl.parse_attachments",
            "desc": "解析附件文本"
        })

    # 步骤 4：导入数据库
    if not args.skip_import:
        steps.append({
            "cmd": "python -m src.etl.import_attachment_chunks --import",
            "desc": "导入附件内容到数据库"
        })

    # 执行所有步骤
    success = True
    for step in steps:
        if not run_command(step["cmd"], step["desc"]):
            success = False
            break

    # 验证
    if success and args.verify:
        run_command("python -m src.etl.import_attachment_chunks --verify", "验证导入结果")
        run_command("python tests/utils/verify_data.py", "数据验证")

    print("\n" + "="*60)
    if success:
        print("[SUCCESS] 所有步骤完成!")
    else:
        print("[FAILED] 流程中断，请检查错误信息")
    print("="*60)

    # 显示下一步建议
    print("\n下一步建议:")
    print("1. 检查解析结果：output/parsed_attachments/")
    print("2. 检查附件 chunks: python -m src.etl.import_attachment_chunks --verify")
    print("3. 运行 RAG 检索测试")


if __name__ == "__main__":
    main()
