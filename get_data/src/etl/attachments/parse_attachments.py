# -*- coding: utf-8 -*-
"""
解析已下载的附件文件，提取文本内容
支持格式：PDF, DOC, DOCX, TXT, CSV, XLS, XLSX, ZIP 等
"""

import os
import sys
import json
import sqlite3
import re
import zipfile
import shutil
import tempfile

# 添加项目根目录和 src 目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)
from config import DB_PATH

# 附件目录
ATTACHMENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "attachments")

# 解析结果保存目录
PARSED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "output", "parsed_attachments")
os.makedirs(PARSED_DIR, exist_ok=True)

# 临时解压目录
TEMP_EXTRACT_DIR = os.path.join(PARSED_DIR, "_temp_extract")


def clean_text(text):
    """
    清理文本：去除换行符、多余空白等特殊字符，只保留纯文本信息
    """
    if not text:
        return ""

    # 将多种空白字符替换为空格
    text = re.sub(r'[\r\n\t\f\v]+', ' ', text)

    # 将多个连续空格合并为一个
    text = re.sub(r' +', ' ', text)

    # 去除首尾空白
    text = text.strip()

    return text


def read_pdf(file_path):
    """读取 PDF 文件内容"""
    try:
        import pypdf
        reader = pypdf.PdfReader(file_path)
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(clean_text(text))
        return ' '.join(text_parts)
    except ImportError:
        print("  [WARN] pypdf 未安装，跳过 PDF 解析")
        return None
    except Exception as e:
        print(f"  [ERROR] PDF 解析失败：{e}")
        return None


def read_docx(file_path):
    """读取 DOCX 文件内容"""
    try:
        from docx import Document
        doc = Document(file_path)
        text_parts = []
        for para in doc.paragraphs:
            if para.text and para.text.strip():
                text_parts.append(clean_text(para.text))
        return ' '.join(text_parts)
    except ImportError:
        print("  [WARN] python-docx 未安装，跳过 DOCX 解析")
        return None
    except Exception as e:
        print(f"  [ERROR] DOCX 解析失败：{e}")
        return None


def read_doc(file_path):
    """
    读取老版本 DOC 文件内容
    使用 olefile 解析二进制格式
    """
    try:
        import olefile
        ole = olefile.OleFileIO(file_path)

        # 检查是否是 Word 文档
        if not ole.exists('WordDocument'):
            print("  [WARN] 不是有效的 Word 文档")
            return None

        # 读取 WordDocument 流
        with ole.openstream('WordDocument') as f:
            doc_data = f.read()

        # 尝试读取文本流
        text_parts = []

        # 检查是否有 1Table 流（包含文本信息）
        if ole.exists('1Table'):
            # 简单的文本提取（适用于大多数 DOC 文件）
            # 尝试从 DocumentSummaryInformation 获取元数据
            try:
                meta = ole.get_metadata()
                if meta.title:
                    text_parts.append(f"标题：{meta.title}")
                if meta.subject:
                    text_parts.append(f"主题：{meta.subject}")
                if meta.author:
                    text_parts.append(f"作者：{meta.author}")
            except:
                pass

        # 尝试提取文本（使用简单的启发式方法）
        # DOC 文件中的文本通常是 ANSI 或 Unicode 编码
        try:
            # 尝试 UTF-16 解码
            text_candidate = doc_data.decode('utf-16', errors='ignore')
            # 过滤掉非文本字符
            text_clean = ''.join(c for c in text_candidate if c.isprintable() or c in '\n\r\t')
            if len(text_clean) > 100:
                text_parts.append(text_clean[:50000])  # 限制长度
        except:
            pass

        # 尝试 ANSI 解码
        try:
            text_candidate = doc_data.decode('gbk', errors='ignore')
            text_clean = ''.join(c for c in text_candidate if c.isprintable() or c in '\n\r\t')
            if len(text_clean) > 100:
                text_parts.append(text_clean[:50000])
        except:
            pass

        if text_parts:
            return ' '.join([clean_text(t) for t in text_parts])
        else:
            # 如果无法解析，返回提示信息
            print("  [WARN] DOC 文件无法解析，可能是加密或特殊格式")
            return f"[DOC 文件：{os.path.basename(file_path)} - 需要专用解析器]"

    except ImportError:
        print("  [WARN] olefile 未安装，跳过 DOC 解析")
        return None
    except Exception as e:
        print(f"  [ERROR] DOC 解析失败：{e}")
        return f"[DOC 解析错误：{e}]"


def read_txt(file_path):
    """读取 TXT 文件内容"""
    try:
        # 尝试多种编码
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return clean_text(f.read())
            except UnicodeDecodeError:
                continue

        # 如果所有编码都失败，使用 ignore 模式
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return clean_text(f.read())
    except Exception as e:
        print(f"  [ERROR] TXT 读取失败：{e}")
        return None


def read_csv(file_path):
    """读取 CSV 文件内容"""
    try:
        import csv
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            rows = list(reader)
            # 转为简单的文本格式
            return clean_text(' '.join([' '.join(row) for row in rows]))
    except Exception as e:
        print(f"  [ERROR] CSV 读取失败：{e}")
        return None


def read_excel(file_path):
    """读取 Excel 文件内容"""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        text_parts = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                row_text = ' '.join([str(cell) if cell is not None else '' for cell in row])
                if row_text.strip():
                    text_parts.append(clean_text(row_text))
        return ' '.join(text_parts)
    except ImportError:
        print("  [WARN] openpyxl 未安装，跳过 Excel 解析")
        return None
    except Exception as e:
        print(f"  [ERROR] Excel 读取失败：{e}")
        return None


def read_excel_old(file_path):
    """读取老版本 XLS 文件内容"""
    try:
        import xlrd
        wb = xlrd.open_workbook(file_path)
        text_parts = []
        for sheet in wb.sheets():
            for row_idx in range(sheet.nrows):
                row = sheet.row_values(row_idx)
                row_text = ' '.join([str(cell) if cell is not None else '' for cell in row])
                if row_text.strip():
                    text_parts.append(clean_text(row_text))
        return ' '.join(text_parts)
    except ImportError:
        print("  [WARN] xlrd 未安装，跳过 XLS 解析")
        return None
    except Exception as e:
        print(f"  [ERROR] XLS 读取失败：{e}")
        return None


def read_rar(file_path):
    """
    读取 RAR 压缩包内容
    需要安装 rarfile 库和系统级 RAR 工具（WinRAR 或 unrar）
    """
    try:
        import rarfile
        rf = rarfile.RarFile(file_path)
        text_parts = []
        image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')

        for f in rf.infolist():
            if f.is_dir():
                continue
            # 跳过图片文件
            if f.filename.lower().endswith(image_extensions):
                print(f"    [SKIP] 图片文件：{f.filename}")
                continue
            try:
                data = rf.read(f.filename)
                # 尝试解码为文本
                try:
                    text = data.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        text = data.decode('gbk')
                    except:
                        text = data.decode('utf-8', errors='ignore')
                text_parts.append(f"[{f.filename}] {clean_text(text)}")
            except Exception as e:
                print(f"    [WARN] 读取 RAR 内文件失败 {f.filename}: {e}")

        if text_parts:
            return ' '.join(text_parts)

        # 如果只有图片文件，返回提示
        print("  [INFO] RAR 文件仅包含图片，无法提取文本")
        return ""
    except ImportError:
        print("  [WARN] rarfile 未安装，跳过 RAR 解析")
        print("  [INFO] 安装方法：pip install rarfile，并安装 WinRAR 或 unrar 工具")
        return None
    except rarfile.BadRarFile:
        print("  [WARN] 不是有效的 RAR 文件")
        return None
    except Exception as e:
        print(f"  [ERROR] RAR 解析失败：{e}")
        return None


def extract_zip(zip_path, extract_dir):
    """
    解压 ZIP 文件到指定目录
    返回解压的文件列表
    """
    extracted_files = []

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # 处理中文文件名乱码
            for info in zip_ref.infolist():
                # 尝试修复中文文件名
                try:
                    # 如果是 GBK 编码的文件名
                    filename = info.filename.encode('cp437').decode('gbk', errors='ignore')
                except:
                    filename = info.filename

                # 跳过目录
                if filename.endswith('/'):
                    continue

                # 创建目标路径
                target_path = os.path.join(extract_dir, os.path.basename(filename))

                # 解压文件
                try:
                    zip_ref.extract(info, extract_dir)
                    # 重命名为简单文件名
                    extracted = os.path.join(extract_dir, info.filename)
                    if os.path.exists(extracted) and extracted != target_path:
                        os.rename(extracted, target_path)
                        extracted_files.append(target_path)
                    else:
                        extracted_files.append(extracted)
                except Exception as e:
                    print(f"    [WARN] 解压失败 {filename}: {e}")

            # 如果 CP437 解码失败，尝试直接解压
            if not extracted_files:
                zip_ref.extractall(extract_dir)
                for root, dirs, files in os.walk(extract_dir):
                    for f in files:
                        extracted_files.append(os.path.join(root, f))

    except zipfile.BadZipFile:
        print("  [WARN] 不是有效的 ZIP 文件")
        return []
    except Exception as e:
        print(f"  [ERROR] ZIP 解压失败：{e}")
        return []

    return extracted_files


def parse_zip_contents(zip_path):
    """
    解压 ZIP 并解析内部所有文件
    返回合并的文本内容
    """
    # 创建临时目录
    temp_dir = os.path.join(TEMP_EXTRACT_DIR, os.path.basename(zip_path))
    os.makedirs(temp_dir, exist_ok=True)

    # 解压
    extracted = extract_zip(zip_path, temp_dir)
    if not extracted:
        return None

    print(f"  [EXTRACT] 解压到 {len(extracted)} 个文件")

    # 解析每个文件
    all_texts = []
    for file_path in extracted:
        if os.path.exists(file_path):
            text = parse_file(file_path)
            if text and len(text.strip()) > 0:
                file_name = os.path.basename(file_path)
                all_texts.append(f"[{file_name}] {clean_text(text)}")

    # 清理临时文件
    try:
        shutil.rmtree(temp_dir)
    except:
        pass

    if all_texts:
        return ' '.join(all_texts)
    return ""


def detect_file_format(file_path):
    """
    检测文件的真实格式
    返回：'pdf', 'docx', 'doc', 'xlsx', 'xls', 'zip', 'txt' 或 None
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(20)

        # ZIP/DOCX/XLSX 格式 (PK 头)
        if header[:4] == b'PK\x03\x04':
            # 检查是否是 Office 文档
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.doc', '.docx']:
                return 'docx'
            elif ext in ['.xls', '.xlsx']:
                return 'xlsx'
            elif ext == '.zip':
                return 'zip'
            return 'zip'  # 默认作为 ZIP

        # OLE2 格式 (DOC/XLS 老格式)
        if header[:4] == b'\xd0\xcf\x11\xe0':
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.doc', '.xls']:
                return ext[1:]  # 'doc' or 'xls'
            return 'doc'  # 默认作为 DOC

        # PDF 格式
        if header[:5] == b'%PDF-':
            return 'pdf'

        # RAR 格式
        if header[:4] == b'Rar!':
            return 'rar'

        return None
    except:
        return None


def parse_file(file_path):
    """根据文件扩展名和真实格式选择解析方法"""
    if not os.path.exists(file_path):
        print(f"  [ERROR] 文件不存在：{file_path}")
        return None

    ext = os.path.splitext(file_path)[1].lower()

    # 检测真实格式
    real_format = detect_file_format(file_path)

    # 根据真实格式选择解析器（如果检测失败则使用扩展名）
    if real_format:
        print(f"  [PARSE] Detected format: {real_format} (ext: {ext})")
    else:
        print(f"  [PARSE] Using extension: {ext}")

    # 解析器映射
    parsers = {
        'pdf': read_pdf,
        'doc': read_doc,
        'docx': read_docx,
        'xls': read_excel_old,
        'xlsx': read_excel,
        'zip': lambda p: parse_zip_contents(p),
        'rar': read_rar,
        'txt': read_txt,
        'csv': read_csv,
    }

    # 优先使用检测到的格式，否则使用扩展名
    format_to_use = real_format if real_format else ext[1:] if ext else None

    if format_to_use and format_to_use in parsers:
        return parsers[format_to_use](file_path)
    else:
        # 未知格式，尝试作为文本读取
        print(f"  [WARN] 未知格式，尝试作为文本读取")
        return read_txt(file_path)


def get_downloaded_attachments():
    """获取已下载的附件列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查表是否存在
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='tender_attachments'
    """)

    if not cursor.fetchone():
        print("[WARN] tender_attachments 表不存在")
        conn.close()
        return []

    # 检查是否有 local_path 字段
    cursor.execute("PRAGMA table_info(tender_attachments)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'local_path' not in columns:
        print("[WARN] local_path 字段不存在，先扫描本地文件")
        conn.close()
        return scan_local_files()

    cursor.execute("""
        SELECT id, tender_id, file_name, download_url, local_path, file_size
        FROM tender_attachments
        WHERE download_status = 'downloaded' AND local_path IS NOT NULL
    """)

    rows = cursor.fetchall()
    conn.close()

    attachments = []
    for row in rows:
        attachments.append({
            "id": row[0],
            "tender_id": row[1],
            "file_name": row[2],
            "download_url": row[3],
            "local_path": row[4],
            "file_size": row[5]
        })

    return attachments


def scan_local_files():
    """扫描本地附件目录"""
    if not os.path.exists(ATTACHMENTS_DIR):
        print(f"[WARN] 附件目录不存在：{ATTACHMENTS_DIR}")
        return []

    attachments = []
    for tender_id in os.listdir(ATTACHMENTS_DIR):
        tender_dir = os.path.join(ATTACHMENTS_DIR, tender_id)
        if not os.path.isdir(tender_dir):
            continue

        for filename in os.listdir(tender_dir):
            file_path = os.path.join(tender_dir, filename)
            attachments.append({
                "tender_id": tender_id,
                "file_name": filename,
                "local_path": file_path,
                "file_size": os.path.getsize(file_path)
            })

    print(f"[INFO] 扫描到 {len(attachments)} 个本地文件")
    return attachments


def save_parsed_text(tender_id, file_name, text, output_format='json'):
    """保存解析后的文本"""
    if not text:
        return None

    # 生成输出文件名
    base_name = os.path.splitext(file_name)[0]
    safe_tender_id = str(tender_id).replace('/', '_')

    if output_format == 'json':
        output_file = os.path.join(PARSED_DIR, f"{safe_tender_id}_{base_name}.json")
        data = {
            "tender_id": tender_id,
            "source_file": file_name,
            "content": text
        }
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    else:
        output_file = os.path.join(PARSED_DIR, f"{safe_tender_id}_{base_name}.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(text)

    print(f"  [SAVED] {output_file}")
    return output_file


def parse_all_attachments():
    """解析所有已下载的附件"""
    attachments = get_downloaded_attachments()

    if not attachments:
        print("[INFO] 没有可解析的附件")
        return

    print(f"\n{'='*60}")
    print(f"开始解析附件，共 {len(attachments)} 个")
    print(f"{'='*60}\n")

    stats = {
        'total': len(attachments),
        'success': 0,
        'failed': 0,
        'skipped': 0
    }

    results = []

    for idx, att in enumerate(attachments, 1):
        tender_id = att.get('tender_id', 'unknown')
        file_name = att.get('file_name', '')
        local_path = att.get('local_path', '')

        if not local_path or not os.path.exists(local_path):
            print(f"[{idx}/{len(attachments)}] [SKIP] 文件不存在：{local_path}")
            stats['skipped'] += 1
            continue

        print(f"\n[{idx}/{len(attachments)}] Tender ID: {tender_id}")
        print(f"  File: {file_name}")
        print(f"  Path: {local_path}")

        # 解析文件
        text = parse_file(local_path)

        if text:
            stats['success'] += 1
            # 保存解析结果
            output_path = save_parsed_text(tender_id, file_name, text)
            results.append({
                "tender_id": tender_id,
                "source_file": file_name,
                "local_path": local_path,
                "parsed_text_path": output_path,
                "char_count": len(text)
            })
        else:
            stats['failed'] += 1

    # 保存汇总
    summary_path = os.path.join(PARSED_DIR, "parsing_summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print("解析完成!")
    print(f"{'='*60}")
    print(f"总数：{stats['total']}")
    print(f"成功：{stats['success']}")
    print(f"失败：{stats['failed']}")
    print(f"跳过：{stats['skipped']}")
    print(f"汇总：{summary_path}")
    print(f"{'='*60}")

    return results


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='解析已下载的附件文件')
    parser.add_argument('--scan-local', action='store_true', help='扫描本地附件目录')
    parser.add_argument('--output-dir', type=str, default=PARSED_DIR, help='输出目录')

    args = parser.parse_args()

    if args.scan_local:
        attachments = scan_local_files()
    else:
        parse_all_attachments()


if __name__ == "__main__":
    parse_all_attachments()
