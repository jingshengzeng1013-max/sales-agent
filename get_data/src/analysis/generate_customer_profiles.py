# -*- coding: utf-8 -*-
"""
客户画像分析模块
从结构化标讯中聚合数据，生成客户 360° 画像 JSON
"""

import os
import sys
import sqlite3
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# 将项目根目录添加到 sys.path
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from src.config import DB_PATH, CUSTOMER_OUTPUT_DIR

def generate_profiles(output_path=None):
    """
    从 tender_structured 表聚合数据并生成画像
    """
    if output_path is None:
        output_path = CUSTOMER_OUTPUT_DIR / "customer_profiles.json"
    
    print("=" * 60)
    print(f"正在生成客户画像...")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. 获取所有结构化标讯数据，并关联原始标讯的发布日期
    cursor.execute("""
        SELECT ts.*, t.publish_date 
        FROM tender_structured ts
        LEFT JOIN tenders t ON ts.source_url = t.detail_url
    """)
    rows = cursor.fetchall()
    
    if not rows:
        print("[WARN] tender_structured 表中没有数据")
        return None

    # 2. 按采购单位聚合
    profiles = {}

    for row in rows:
        buyer = row['buyer_name_std']
        if not buyer or buyer == '未知':
            continue
            
        if buyer not in profiles:
            profiles[buyer] = {
                "customer_name": buyer,
                "basic_info": {
                    "province": row['province'],
                    "city": row['city'],
                    "industries": set(),
                    "levels": set()
                },
                "demand_profile": {
                    "tech_keywords": set(),
                    "application_scenarios": set(),
                    "technical_summaries": []
                },
                "value_profile": {
                    "tender_count": 0,
                    "total_budget": 0.0,
                    "avg_opportunity_score": 0.0,
                    "scores": []
                },
                "competitive_landscape": {
                    "past_winners": set(),
                    "past_winning_products": set()
                },
                "contact_info": {
                    "persons": set(),
                    "phones": set()
                },
                "history_tenders": []
            }

        p = profiles[buyer]
        
        # 更新基础信息
        if row['province'] and not p['basic_info']['province']:
            p['basic_info']['province'] = row['province']
        if row['city'] and not p['basic_info']['city']:
            p['basic_info']['city'] = row['city']
            
        # 更新需求画像
        if row['product_keywords']:
            try:
                keywords = json.loads(row['product_keywords'])
                if isinstance(keywords, list):
                    p['demand_profile']['tech_keywords'].update(keywords)
            except:
                pass
        
        if row['application_scenario']:
            p['demand_profile']['application_scenarios'].add(row['application_scenario'])
        
        if row['technical_requirements_summary']:
            p['demand_profile']['technical_summaries'].append(row['technical_requirements_summary'])

        # 更新价值画像
        p['value_profile']['tender_count'] += 1
        if row['budget_amount']:
            p['value_profile']['total_budget'] += row['budget_amount']
        if row['opportunity_score']:
            p['value_profile']['scores'].append(row['opportunity_score'])

        # 更新竞争属性
        if row['winning_bidder']:
            try:
                winners = json.loads(row['winning_bidder']) if row['winning_bidder'].startswith('[') else [row['winning_bidder']]
                p['competitive_landscape']['past_winners'].update(winners)
            except:
                p['competitive_landscape']['past_winners'].add(row['winning_bidder'])
        
        if row['winning_product']:
            p['competitive_landscape']['past_winning_products'].add(row['winning_product'])

        # 更新联系方式
        if row['contact_person']: p['contact_info']['persons'].add(row['contact_person'])
        if row['contact_phone']: p['contact_info']['phones'].add(row['contact_phone'])

        # 记录历史标讯简要
        p['history_tenders'].append({
            "project_name": row['project_name'],
            "budget": row['budget_amount'],
            "winning_amount": row['winning_amount'], # 中标金额
            "date": row['publish_date'], # 发布日期
            "url": row['source_url']
        })

    # 3. 后处理：计算平均分，转换 set 为 list
    final_profiles = []
    for buyer, p in profiles.items():
        # 计算平均分
        if p['value_profile']['scores']:
            p['value_profile']['avg_opportunity_score'] = round(sum(p['value_profile']['scores']) / len(p['value_profile']['scores']), 2)
        del p['value_profile']['scores']

        # 转换 set 为 list 以便 JSON 序列化
        p['basic_info']['industries'] = list(p['basic_info']['industries'])
        p['basic_info']['levels'] = list(p['basic_info']['levels'])
        p['demand_profile']['tech_keywords'] = list(p['demand_profile']['tech_keywords'])
        p['demand_profile']['application_scenarios'] = list(p['demand_profile']['application_scenarios'])
        p['competitive_landscape']['past_winners'] = list(p['competitive_landscape']['past_winners'])
        p['competitive_landscape']['past_winning_products'] = list(p['competitive_landscape']['past_winning_products'])
        p['contact_info']['persons'] = list(p['contact_info']['persons'])
        p['contact_info']['phones'] = list(p['contact_info']['phones'])
        
        p['last_updated'] = datetime.now().strftime("%Y-%m-%d")
        final_profiles.append(p)

    # 4. 写入 JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_profiles, f, ensure_ascii=False, indent=2)

    conn.close()
    print(f"[SUCCESS] 已生成 {len(final_profiles)} 个客户画像 -> {output_path}")
    return final_profiles

if __name__ == "__main__":
    generate_profiles()
