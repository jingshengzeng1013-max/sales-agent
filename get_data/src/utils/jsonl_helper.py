# -*- coding: utf-8 -*-
import json
import os
from typing import List, Dict, Any

def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    """加载 JSONL 文件"""
    if not os.path.exists(file_path):
        return []
    
    results = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))
    except Exception as e:
        print(f"[ERROR] 加载 JSONL 失败 {file_path}: {e}")
    return results

def save_jsonl(data: List[Dict[str, Any]], file_path: str, append: bool = False):
    """保存为 JSONL 格式"""
    mode = 'a' if append else 'w'
    
    # 确保目录存在
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    try:
        with open(file_path, mode, encoding='utf-8') as f:
            if isinstance(data, list):
                for item in data:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')
            else:
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f"[ERROR] 保存 JSONL 失败 {file_path}: {e}")

def save_jsonl_single(item: Dict[str, Any], file_path: str):
    """保存单条记录到 JSONL (追加模式)"""
    save_jsonl([item], file_path, append=True)
