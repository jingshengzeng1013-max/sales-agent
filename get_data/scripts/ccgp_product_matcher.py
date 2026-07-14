#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CCGP采购记录意图识别和产品精匹配脚本
处理步骤：
1. 读取JSONL每条记录
2. 从detail_body_preview中提取"采购需求"或"一、采购内容"之后的实际采购需求正文
3. 调用LLM进行意图识别+产品匹配
4. 输出结果到matched JSONL文件
"""

import json
import re
import time
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

# 尝试加载dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================================
# MiniMax API 配置（通过OpenAI兼容接口）
# ============================================================================
MINIMAX_CONFIG = {
    "api_key": os.environ.get("OPENAI_API_KEY", ""),
    "base_url": os.environ.get("OPENAI_BASE_URL", "https://api.minimaxi.com/v1"),
    "model": os.environ.get("OPENAI_MODEL", "MiniMax-M2.7-highspeed"),
}

# 备用本地LLM配置
LOCAL_LLM_CONFIG = {
    "api_key": os.environ.get("LOCAL_LLM_API_KEY", "local-api-key"),
    "base_url": os.environ.get("LOCAL_LLM_BASE_URL", "http://10.210.10.51:8001/v1"),
    "model": os.environ.get("LOCAL_LLM_MODEL", "/models/Qwen3.5-27B"),
}

# 产品匹配规则
PRODUCT_RULES = {
    "卫星移动通信": {
        "keywords": ["天通", "卫星通信", "卫星电话", "应急通信设备", "卫星终端", "卫星芯片"],
        "models": ["DX-S701", "DX-S702", "DX-S703", "SVB01", "SVB02", "SBOX01C", "STBOX01C", "SEC01C"]
    },
    "工业5G": {
        "keywords": ["5G专网", "工业5G", "边缘计算", "MEC", "5G基带", "5G模组"],
        "models": ["DX-T502"]
    },
    "AI机器人": {
        "keywords": ["机器人", "具身智能", "机器人开发套件", "机械臂", "人形机器人"],
        "models": ["π-base"]
    },
    "星闪短距": {
        "keywords": ["星闪", "SLE", "短距通信", "无线短距", "短距离无线通信"],
        "models": ["DX-T600", "SLM600", "SLD600"]
    }
}

# ============================================================================
# LLM客户端
# ============================================================================
def get_openai_client():
    """获取OpenAI兼容客户端"""
    try:
        from openai import OpenAI
        if MINIMAX_CONFIG["api_key"]:
            return OpenAI(
                api_key=MINIMAX_CONFIG["api_key"],
                base_url=MINIMAX_CONFIG["base_url"],
                timeout=120
            )
        elif LOCAL_LLM_CONFIG["api_key"]:
            return OpenAI(
                api_key=LOCAL_LLM_CONFIG["api_key"],
                base_url=LOCAL_LLM_CONFIG["base_url"],
                timeout=LOCAL_LLM_CONFIG.get("timeout", 600)
            )
        else:
            print("[WARN] 未配置任何API Key")
            return None
    except ImportError:
        print("[ERROR] openai库未安装")
        return None

def extract_procurement_body(text: str) -> str:
    """
    从HTML或文本中提取采购需求正文
    规则：
    - 找到"采购需求"或"一、采购内容"作为起始标记
    - 去掉HTML标签
    - 取2000字
    """
    if not text:
        return ""
    
    # 去掉HTML标签
    clean_text = re.sub(r'<[^>]+>', ' ', text)
    clean_text = re.sub(r'&[a-zA-Z]+;', ' ', clean_text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    # 尝试找到"采购需求"或"一、采购内容"起始位置
    patterns = [
        r'采购需求[：:]\s*',
        r'一、采购内容\s*',
        r'二、采购需求\s*',
        r'三、采购需求\s*',
        r'技术需求[：:]\s*',
        r'技术参数[：:]\s*',
    ]
    
    start_pos = -1
    for pattern in patterns:
        match = re.search(pattern, clean_text)
        if match:
            start_pos = match.end()
            break
    
    if start_pos == -1:
        # 如果没找到起始标记，尝试从开头取
        start_pos = 0
    
    # 提取正文
    body = clean_text[start_pos:start_pos + 2000]
    
    return body.strip()

def call_llm_match(title: str, body: str) -> Dict[str, Any]:
    """
    调用LLM进行意图识别和产品匹配
    返回: {"intent_verdict": "具体产品"/"非具体产品", "matched_products": [], "reason": ""}
    """
    client = get_openai_client()
    if not client:
        return {
            "intent_verdict": "LLM不可用",
            "matched_products": [],
            "reason": "未配置API Key"
        }
    
    # 判断正文长度
    if len(body) < 50:
        return {
            "intent_verdict": "正文缺失",
            "matched_products": [],
            "reason": f"正文太短({len(body)}字)，无法判断"
        }
    
    # 构建prompt
    prompt = f"""你是一个政府采购产品匹配专家。判断以下采购公告的采购需求是否为具体的产品采购，以及是否与目标公司的产品相关。

目标公司产品线：
1. 卫星移动通信：天通卫星通信芯片/模组/终端，用于应急通信保障
2. 工业5G通信：工业5G基带芯片和模组，用于专网通信
3. AI机器人：机器人开发套件和智能系统
4. 星闪短距通信：新一代无线短距通信技术

请分析以下采购需求，返回严格的JSON格式（不要输出任何其他内容）：
{{"intent_verdict": "具体产品"或"非具体产品", "matched_products": ["匹配的产品的数组，没有则为空"], "reason": "判断理由，50字以内"}}

判断标准：
- 具体产品：采购需求明确列出设备/产品名称和参数（不管是否与目标公司产品相关）
- 非具体产品：服务类/物业类/纯软件类/培训类/建筑工程类，无法用设备产品满足的
- 匹配标准：采购的设备在功能/应用场景上与目标公司产品相关（即使不完全一样）

标题：{title}
需求：{body[:2000]}

返回JSON："""
    
    model = MINIMAX_CONFIG["model"] if MINIMAX_CONFIG["api_key"] else LOCAL_LLM_CONFIG["model"]
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500
        )
        content = response.choices[0].message.content.strip()
        
        # 提取JSON
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            return result
        else:
            return {
                "intent_verdict": "解析失败",
                "matched_products": [],
                "reason": f"无法解析LLM响应: {content[:100]}"
            }
    except Exception as e:
        return {
            "intent_verdict": "LLM调用失败",
            "matched_products": [],
            "reason": str(e)[:50]
        }

def process_ccgp_records(input_file: str, output_file: str, delay: float = 1.0):
    """
    处理CCGP采购记录
    
    Args:
        input_file: 输入JSONL文件路径
        output_file: 输出JSONL文件路径
        delay: 每次LLM调用间隔（秒），避免限流
    """
    print(f"开始处理CCGP采购记录...")
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    
    # 读取所有记录
    records = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"[WARN] 跳过无效JSON行: {e}")
    
    total = len(records)
    print(f"共读取 {total} 条记录")
    
    # 统计变量
    stats = {
        "total": total,
        "具体产品": 0,
        "非具体产品": 0,
        "正文缺失": 0,
        "LLM失败": 0,
        "matched": 0,
        "by_product": {k: 0 for k in PRODUCT_RULES.keys()}
    }
    
    # 处理每条记录
    matched_records = []
    for i, record in enumerate(records):
        # 提取正文
        body_preview = record.get('detail_body_preview', '')
        body = extract_procurement_body(body_preview)
        
        # 准备输出记录
        output_record = {
            "list_url": record.get('list_url', ''),
            "list_title": record.get('list_title', ''),
            "list_pub_date": record.get('list_pub_date', ''),
            "list_buyer": record.get('list_buyer', ''),
            "list_agency": record.get('list_agency', ''),
            "list_ann_type": record.get('list_ann_type', ''),
            "list_region": record.get('list_region', ''),
            "detail_amount": record.get('detail_amount', ''),
            "detail_body_preview": body,  # 使用提取后的正文
        }
        
        # 调用LLM进行匹配
        title = record.get('list_title', '')
        llm_result = call_llm_match(title, body)
        
        output_record["intent_verdict"] = llm_result.get("intent_verdict", "")
        output_record["matched_products"] = llm_result.get("matched_products", [])
        output_record["reason"] = llm_result.get("reason", "")
        
        matched_records.append(output_record)
        
        # 更新统计
        verdict = llm_result.get("intent_verdict", "")
        if verdict == "具体产品":
            stats["具体产品"] += 1
            matched_prods = llm_result.get("matched_products", [])
            if matched_prods:
                stats["matched"] += 1
                for prod in matched_prods:
                    if prod in stats["by_product"]:
                        stats["by_product"][prod] += 1
        elif verdict == "非具体产品":
            stats["非具体产品"] += 1
        elif verdict == "正文缺失":
            stats["正文缺失"] += 1
        else:
            stats["LLM失败"] += 1
        
        # 每50条输出进度
        if (i + 1) % 50 == 0:
            print(f"进度: {i+1}/{total} ({100*(i+1)/total:.1f}%)")
            print(f"  统计: 具体产品={stats['具体产品']}, 非具体产品={stats['非具体产品']}, 匹配到产品={stats['matched']}")
        
        # 延迟避免限流
        if delay > 0:
            time.sleep(delay)
    
    # 写入输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        for record in matched_records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    # 打印最终统计
    print("\n" + "="*60)
    print("处理完成！")
    print("="*60)
    print(f"总记录数: {stats['total']}")
    print(f"具体产品采购: {stats['具体产品']}")
    print(f"非具体产品采购: {stats['非具体产品']}")
    print(f"正文缺失: {stats['正文缺失']}")
    print(f"LLM调用失败: {stats['LLM失败']}")
    print(f"匹配到公司产品: {stats['matched']}")
    print("\n按产品线分类:")
    for prod, count in stats['by_product'].items():
        if count > 0:
            print(f"  {prod}: {count}")
    print(f"\n结果已输出到: {output_file}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='CCGP采购记录意图识别和产品匹配')
    parser.add_argument('--input', '-i', default='/home/sylincom/sales-agent/get_data/data/output/crawler/ccgp_v2_20260514_185934.jsonl', help='输入JSONL文件')
    parser.add_argument('--output', '-o', default='/home/sylincom/sales-agent/get_data/data/output/crawler/ccgp_v2_20260514_185934_matched.jsonl', help='输出JSONL文件')
    parser.add_argument('--delay', '-d', type=float, default=1.0, help='LLM调用间隔（秒）')
    
    args = parser.parse_args()
    
    process_ccgp_records(args.input, args.output, args.delay)