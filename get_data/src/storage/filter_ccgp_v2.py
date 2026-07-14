# -*- coding: utf-8 -*-
"""
CCGP精匹配过滤模块
基于产品特征在采购需求正文中做意图识别和产品匹配
"""

import sys
import os
import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime
import uuid as uuid_lib

root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from src.config import DB_PATH


# ============ 精匹配规则 ============
# 产品赛道定义（来自星通科技产品文档）

PRODUCT_CATEGORIES = {
    'satellite': {
        'name': '卫星移动通信',
        'products': ['天通卫星通信芯片', '天通卫星通信终端', '卫星电话', '天通猫', '天通模组', '天通S701', '天通S702', '天通S703', 'SVB01', 'SVB02', 'SBOX01C', 'STBOX01C', 'SEC01C'],
        'keywords': ['卫星通信', '天通卫星', '天通', '卫星电话', '卫星终端', '卫星芯片', '卫星模组', '卫星移动通信', '卫星物联网', '高轨卫星', '低轨卫星', '天通猫', '天通设备'],
        'exclude': ['轻质白油', '柴油', '汽油', '燃料', '食用油', '雷达生命探测仪', '水文监测设备']
    },
    'industrial_5g': {
        'name': '工业5G/边缘计算',
        'products': ['工业5G通信模组', '5G工业模组', 'DX-T502', '边缘计算网关', '5G专网'],
        'keywords': ['工业5G', '5G专网', '5G模组', '边缘计算', '边缘网关', '工业网关', 'MEC', '5G工业互联网', '5G+工业'],
        'exclude': ['租用', '租赁', '维修', '维护', '服务类']
    },
    'robot': {
        'name': 'AI机器人/具身智能',
        'products': ['人形机器人', '复合机器人', '机器人实验平台', '机器人控制器', '伺服电机', '人形机械'],
        'keywords': ['人形机器人', '具身智能', '复合机器人', '机器人实验平台', '工业机器人', '智能机器人', '机器人本体', '伺服控制器', '协作机器人', '四足机器人'],
        'exclude': ['机泵', '阀门', '典型机泵', '化工设备']
    },
    'emergency': {
        'name': '应急通信保障',
        'products': ['应急通信设备', '应急指挥', '救援通信'],
        'keywords': ['应急通信', '应急救援', '救援装备', '应急物资', '应急指挥', '森林防火', '防汛救灾', '应急管理局', '呼吸器', '防灭火物资', '矿山救援', '救援设备'],
        'exclude': ['物业', '保安', '保洁', '食堂', '餐饮', '绿化', '装修', '工程类']
    },
    'sparklink': {
        'name': '星闪短距离通信',
        'products': ['星闪模组', '星闪SLE', '星闪设备'],
        'keywords': ['星闪', 'SLE', '短距离无线', '无线投屏'],
        'exclude': ['LED显示屏', '录播', '音响', '机泵', '化工设备']
    }
}


# 非产品采购排除词
EXCLUDE_WORDS = [
    '物业', '保安', '保洁', '食堂', '餐饮', '绿化', '法律咨询', '法律服务',
    '审计服务', '评估服务', '培训服务', '租用服务', '租赁', '维修', '维护',
    '装修', '建设工程', '装修工程', '轻质白油', '柴油', '汽油', '燃料',
    '食用油', '服装采购', '工作服', '鞋', '手套', '口罩', '窗帘', '办公家具',
    '固废', '土壤', '水质', '充电站', '充电桩', '变压器', '配电柜',
    '防撞柱', '反恐防暴', '警用装备'
]


def is_meaningful_content(text):
    """判断正文是否有实质采购需求内容"""
    if not text or len(text) < 100:
        return False
    # 排除只有公告发布说明的情况
    if '招标公告' in text and '采购需求' not in text and '采购' not in text:
        return False
    return True


def extract_procurement_content(html_content):
    """从HTML中提取采购需求正文"""
    if not html_content:
        return ''
    # 找"采购需求"或"一、采购内容"
    patterns = ['采购需求', '一、采购内容', '采购内容', '采购清单', '标的名称']
    for p in patterns:
        pos = html_content.find(p)
        if pos > 0:
            segment = html_content[pos:pos+5000]
            # 去掉HTML标签
            text = re.sub(r'<[^>]+>', ' ', segment)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:3000]
    # 如果找不到，从body开始提取
    body_match = re.search(r'<body[^>]*>(.*)', html_content, re.DOTALL)
    if body_match:
        text = re.sub(r'<[^>]+>', ' ', body_match.group(1))
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:3000]
    return html_content[:3000]


def match_product_category(text):
    """
    判断正文与哪个产品赛道匹配
    返回: [(category, score, reason), ...]
    """
    if not text:
        return []

    text_lower = text.lower()
    matches = []

    for cat_id, cat_def in PRODUCT_CATEGORIES.items():
        score = 0
        reasons = []

        # 检查排除词
        excluded = any(ex in text for ex in cat_def.get('exclude', []))
        if excluded:
            continue

        # 匹配关键词
        for kw in cat_def.get('keywords', []):
            if kw in text:
                score += 1
                reasons.append(f"命中:{kw}")

        if score > 0:
            matches.append((cat_id, score, '; '.join(reasons)))

    # 按分数排序
    matches.sort(key=lambda x: -x[1])
    return matches


def is_service_not_product(title, content):
    """判断是否为服务类采购（非产品）- 基于标题和正文联合判断"""
    combined = (title or '') + ' ' + (content or '')[:2000]

    # 服务类采购关键词（标题中出现这些，几乎可以肯定是服务）
    title_service_patterns = [
        r'租用服务', r'租赁服务', r'保洁服务', r'保安服务', r'物业管理',
        r'餐饮服务', r'法律咨询', r'审计服务', r'培训服务', r'维修服务',
        r'运营服务', r'服务类采购', r'服务采购'
    ]
    for p in title_service_patterns:
        if re.search(p, title or ''):
            return True

    # 正文中的服务类关键词（需要同时满足多个条件才排除）
    content_service = [
        '车辆维修', '汽车维修', '设备维修', '设施维修',  # 维修服务
    ]
    for s in content_service:
        if s in (content or '')[:2000]:
            return True

    return False


def filter_record(record):
    """
    过滤单条记录
    返回: (keep: bool, reason: str, categories: list)
    """
    title = record.get('project_name', '') or ''
    content = record.get('content', '') or ''
    combined = title + ' ' + content[:2000]

    # 1. 检查正文是否有实质内容
    if not is_meaningful_content(content):
        return False, '正文无实质采购需求内容', []

    # 2. 检查是否服务类采购
    if is_service_not_product(title, content):
        return False, '服务类采购(非产品)', []

    # 3. 检查排除词（正文+标题）
    for ex in EXCLUDE_WORDS:
        if ex in combined:
            return False, f'排除词:{ex}', []

    # 4. 匹配产品类别
    matches = match_product_category(combined)

    if matches:
        cats = [m[0] for m in matches]
        reasons = [f"{m[0]}({m[1]}分:{m[2]})" for m in matches]
        return True, '; '.join(reasons), cats
    else:
        return False, '无产品匹配', []


def filter_all(new_only=True, limit=None):
    """过滤所有记录"""
    conn = sqlite3.connect(DB_PATH)
    if new_only:
        records = conn.execute("SELECT * FROM tenders WHERE status = 'new'").fetchall()
    else:
        records = conn.execute("SELECT * FROM tenders").fetchall()

    cols = [desc[0] for desc in conn.execute("PRAGMA table_info(tenders)").fetchall()]

    if limit:
        records = records[:limit]

    conn.close()

    print(f"待过滤: {len(records)} 条记录")
    print("=" * 60)

    keep_records = []
    remove_records = []

    for rec in records:
        rec_dict = dict(zip(cols, rec))
        keep, reason, cats = filter_record(rec_dict)

        if keep:
            rec_dict['_match_reason'] = reason
            rec_dict['_match_categories'] = cats
            rec_dict['status'] = 'matched'
            keep_records.append(rec_dict)
        else:
            rec_dict['_match_reason'] = reason
            rec_dict['status'] = 'filtered'
            remove_records.append(rec_dict)

    print(f"\n过滤结果:")
    print(f"  保留(matched): {len(keep_records)} 条")
    print(f"  排除(filtered): {len(remove_records)} 条")
    print(f"  命中率: {len(keep_records)/len(records)*100:.1f}%")

    # 保存结果
    output_dir = Path(__file__).resolve().parents[2] / "data/output/filtered"
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    matched_file = output_dir / f"ccgp_matched_{ts}.jsonl"
    filtered_file = output_dir / f"ccgp_filtered_{ts}.jsonl"

    with open(matched_file, 'w', encoding='utf-8') as f:
        for r in keep_records:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    with open(filtered_file, 'w', encoding='utf-8') as f:
        for r in remove_records:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    print(f"\n保留记录: {matched_file}")
    print(f"排除记录: {filtered_file}")

    # 更新数据库状态
    update_db_status(keep_records, remove_records)

    return keep_records, remove_records


def update_db_status(keep_records, remove_records):
    """更新数据库状态"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    updated = 0
    for r in keep_records:
        url = r.get('detail_url', '')
        cats = ','.join(r.get('_match_categories', []))
        reason = r.get('_match_reason', '')
        cursor.execute("""
            UPDATE tenders SET status = 'matched', category = ?, content = ? WHERE detail_url = ?
        """, (cats, reason, url))
        updated += cursor.rowcount

    for r in remove_records:
        url = r.get('detail_url', '')
        reason = r.get('_match_reason', '')
        cursor.execute("""
            UPDATE tenders SET status = 'filtered', content = ? WHERE detail_url = ?
        """, (reason, url))
        updated += cursor.rowcount

    conn.commit()
    conn.close()
    print(f"\n数据库状态已更新: {updated} 条")


def show_sample():
    """显示保留记录样本"""
    conn = sqlite3.connect(DB_PATH)
    records = conn.execute("""
        SELECT project_name, buyer_name, category, content, status
        FROM tenders
        WHERE status = 'matched'
        LIMIT 10
    """).fetchall()
    conn.close()

    print("\n=== 保留记录样本 ===")
    for rec in records:
        title = rec[0][:50] if rec[0] else ''
        buyer = rec[1][:20] if rec[1] else ''
        cat = rec[2] or ''
        reason = rec[3][:60] if rec[3] else ''
        print(f"[{cat}] {title}")
        print(f"  采购人: {buyer} | 理由: {reason}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CCGP精匹配过滤")
    parser.add_argument("--all", action="store_true", help="过滤所有记录(不只是new)")
    parser.add_argument("--limit", type=int, default=None, help="限制处理数量")
    parser.add_argument("--sample", action="store_true", help="显示保留记录样本")
    args = parser.parse_args()

    if args.sample:
        show_sample()
    else:
        filter_all(new_only=not args.all, limit=args.limit)