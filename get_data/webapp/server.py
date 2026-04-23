# -*- coding: utf-8 -*-
"""
API 服务端：提供产品、标讯检索接口
"""

import os
import sys
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path

# 将项目根目录添加到 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from src.retrieval.retriever import DualRetriever

app = Flask(__name__)
CORS(app) # 允许跨域，方便 demo.html 调用

# 初始化检索器
print("[INFO] 正在初始化双路检索器...")
product_retriever = DualRetriever(data_type="product")
tender_retriever = DualRetriever(data_type="tender")

@app.route('/api/products', methods=['GET'])
def get_products():
    """获取所有产品列表"""
    return jsonify(product_retriever.raw_data)

@app.route('/api/search/tenders', methods=['POST'])
def search_tenders():
    """
    根据产品信息或关键词检索标讯
    """
    data = request.json
    query = data.get('query', '')
    top_k = data.get('top_k', 10)
    
    if not query:
        return jsonify({"error": "Query is empty"}), 400
        
    print(f"[API] 收到标讯检索请求: {query}")
    results = tender_retriever.hybrid_search(query, top_k=top_k)
    
    # 格式化输出
    formatted_results = []
    for res in results:
        item = res['data']
        formatted_results.append({
            "id": res['id'],
            "score": res['combined_score'],
            "project_name": item.get('project_name', '未知项目'),
            "buyer": item.get('buyer_name_std', '未知单位'),
            "budget": item.get('budget', '未公开'),
            "publish_date": item.get('publish_date', ''),
            "location": item.get('location', '全国'),
            "keywords": item.get('product_keywords', []),
            "scenario": item.get('application_scenario', ''),
            "tech_summary": item.get('technical_requirements_summary', '')
        })
        
    return jsonify(formatted_results)

@app.route('/api/match', methods=['POST'])
def match_product_tenders():
    """
    针对特定产品匹配标讯
    """
    data = request.json
    product_id = data.get('product_id')
    top_k = data.get('top_k', 10)
    
    # 找到产品
    product = product_retriever.data_dict.get(str(product_id))
    if not product:
        return jsonify({"error": "Product not found"}), 404
        
    # 1. 获取产品的原始向量 (直接从向量库/数据中取)
    query_vector = product.get('embedding')
    if query_vector:
        query_vector = np.array([query_vector]).astype('float32')
        
    # 2. 获取用于关键词检索的文本
    query_text = product.get('embedded_content')
    if not query_text:
        name = product.get('name', '')
        desc = product.get('description', '')
        features = " ".join(product.get('features', []))
        query_text = f"产品: {name} | 功能: {desc} | 特性: {features}"
        
    print(f"[API] 正在为产品 [{product.get('name')}] 匹配标讯 (向量库间直接计算)...")
    # 传入预存向量，避免重新调用 Embedding 接口
    results = tender_retriever.hybrid_search(query_text, top_k=top_k, query_vector=query_vector)
    
    # 格式化输出
    formatted_results = []
    for res in results:
        item = res['data']
        formatted_results.append({
            "id": res['id'],
            "score": res['combined_score'],
            "project_name": item.get('project_name', '未知项目'),
            "buyer": item.get('buyer_name_std', '未知单位'),
            "budget": item.get('budget', '未公开'),
            "publish_date": item.get('publish_date', ''),
            "location": item.get('location', '全国'),
            "keywords": item.get('product_keywords', []),
            "scenario": item.get('application_scenario', ''),
            "tech_summary": item.get('technical_requirements_summary', '')
        })
        
    return jsonify({
        "product": {
            "id": product_id,
            "name": product.get('name')
        },
        "matches": formatted_results
    })

if __name__ == '__main__':
    # 打印 Web 页面地址，方便用户直接点击
    print("\n" + "="*50)
    print("AI 销售助手服务已启动！")
    print(f"API 接口地址: http://127.0.0.1:5000/api")
    print(f"Demo 演示页面: file:///{str(BASE_DIR / 'webapp' / 'demo.html').replace('\\', '/')}")
    print("="*50 + "\n")
    
    # 启动 Flask 服务，监听 5000 端口
    app.run(host='0.0.0.0', port=5000, debug=False)
