# -*- coding: utf-8 -*-
"""
双路检索器：实现向量检索 (FAISS) + 关键词检索 (BM25)
"""

import os
import sys
import json
import logging
import numpy as np
import faiss
import jieba
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any
from pathlib import Path

# 将项目根目录添加到 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

from src.config import EMBEDDING_CONFIG, INDEX_DIR, TENDER_INDEX_DIR
from src.vectorization.vectorize_data import Vectorizer
from src.utils.jsonl_helper import load_jsonl

logger = logging.getLogger("retriever")

class DualRetriever:
    def __init__(self, data_type: str = "product"):
        """
        :param data_type: "product" 或 "tender"
        """
        self.data_type = data_type
        self.vectorizer = Vectorizer()
        self.dimension = EMBEDDING_CONFIG.get("dimension", 1024)
        
        # 设置路径
        if data_type == "product":
            self.index_path = INDEX_DIR / "product.index"
            self.id_map_path = INDEX_DIR / "product_ids.json"
            self.raw_data_path = BASE_DIR / "data/embedding/product_embedded.jsonl"
        else:
            self.index_path = TENDER_INDEX_DIR / "tenders.index"
            self.id_map_path = TENDER_INDEX_DIR / "tenders_ids.json"
            self.raw_data_path = BASE_DIR / "data/embedding/tenders_embedded.jsonl"
            
        self.load_resources()

    def load_resources(self):
        """加载索引、ID映射和原始数据"""
        logger.info(f"正在加载 {self.data_type} 检索资源...")
        
        # 1. 加载 FAISS 索引
        if os.path.exists(self.index_path):
            self.index = faiss.read_index(str(self.index_path))
        else:
            logger.error(f"索引文件不存在: {self.index_path}")
            self.index = None

        # 2. 加载 ID 映射
        if os.path.exists(self.id_map_path):
            with open(self.id_map_path, 'r', encoding='utf-8') as f:
                self.ids = json.load(f)
        else:
            self.ids = []

        # 3. 加载原始数据并构建 BM25 索引
        if os.path.exists(self.raw_data_path):
            logger.info(f"正在为 {self.data_type} 构建 BM25 索引 (流式处理)...")
            self.data_dict = {}
            self.raw_data = [] # 保持与 corpus 顺序一致
            corpus = []
            
            # 使用 JSONL 加载
            temp_data = load_jsonl(str(self.raw_data_path))
                
            for item in temp_data:
                # 统一 ID 提取逻辑：优先使用 uuid，其次是 id 或 project_id
                item_id = str(item.get('uuid') or item.get('id') or item.get('project_id') or "")
                if not item_id:
                    continue
                    
                # 内存优化：剔除 embedding
                display_item = {k: v for k, v in item.items() if k != 'embedding'}
                # 确保 ID 字段存在于 display_item 中供后续使用
                if 'uuid' not in display_item: display_item['uuid'] = item_id
                
                self.data_dict[item_id] = display_item
                self.raw_data.append(display_item)
                
                # 为 BM25 准备语料
                text = f"{item.get('name', '')} {item.get('project_name', '')} {item.get('description', '')} "
                text += " ".join(item.get('features', [])) + " "
                text += " ".join(item.get('product_keywords', []))
                words = list(jieba.cut(text))
                corpus.append(words)
            
            self.bm25 = BM25Okapi(corpus) if corpus else None
            del temp_data # 显式释放大对象
        else:
            self.raw_data = []
            self.bm25 = None

    def bm25_search(self, query_text: str, top_k: int = 10) -> List[Dict]:
        """BM25 关键词检索"""
        if not self.bm25:
            return []
            
        # 1. 分词
        query_words = list(jieba.cut(query_text))
        
        # 2. 获取得分
        scores = self.bm25.get_scores(query_words)
        
        # 3. 排序并取 TopK
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0: # 过滤掉得分为0的
                item = self.raw_data[idx]
                item_id = str(item.get('uuid') or item.get('id') or item.get('project_id'))
                results.append({
                    "id": item_id,
                    "score": float(scores[idx]),
                    "data": item,
                    "method": "bm25"
                })
        return results

    def _matches_filters(
        self,
        item: Dict[str, Any],
        province: str = None,
        city: str = None,
        notice_type: str = None,
    ) -> bool:
        """统一处理检索前置筛选，避免两路召回逻辑不一致。"""
        if province and province not in (item.get('province') or ''):
            return False
        if city and city not in (item.get('city') or ''):
            return False
        if notice_type:
            haystack = " ".join([
                str(item.get('project_name') or ''),
                str(item.get('announce_type') or ''),
                str(item.get('notice_type') or ''),
            ])
            if notice_type not in haystack:
                return False
        return True

    def hybrid_search(self, query_text: str, top_k: int = 10, query_vector: np.ndarray = None,
                      use_vector: bool = True, use_bm25: bool = True,
                      vector_weight: float = 0.5, bm25_weight: float = 0.5,
                      province: str = None, city: str = None, notice_type: str = None,
                      aggregate_by_project: bool = True,
                      exclude_won: bool = False,
                      sort_by: str = "score",
                      client_value_weight: float = 0.0) -> List[Dict]:
        """
        双路检索 + RRF (Reciprocal Rank Fusion) 融合
        :param use_vector: 是否启用向量检索
        :param use_bm25: 是否启用 BM25 关键词检索
        :param vector_weight: 向量检索权重 (0-1)
        :param bm25_weight: BM25 检索权重 (0-1)
        :param province: 地区筛选
        :param city: 城市筛选
        :param notice_type: 公告类型筛选 (招标/中标/...)
        :param aggregate_by_project: 是否按项目汇总显示
        :param exclude_won: 是否排除已中标项目
        :param sort_by: 排序方式 ("score" 或 "date")
        :param client_value_weight: 客户价值权重 (0-1)，基于客户历史平均分进行加权
        """
        # 扩大候选集以支持后续筛选和汇总
        search_k = max(1, top_k) * 50 if (province or city or notice_type or aggregate_by_project) else max(1, top_k) * 5

        if not use_vector and not use_bm25:
            return []

        # 1. 向量检索
        v_results_dict = {}
        if use_vector:
            if self.index is None:
                logger.warning("向量检索已启用，但 FAISS 索引未加载")
            else:
                if query_vector is None:
                    if self.vectorizer is None:
                        logger.warning("向量检索已启用，但 vectorizer 未初始化")
                    else:
                        query_vector = np.array(self.vectorizer.get_embeddings([query_text])).astype('float32')

                if query_vector is not None:
                    faiss.normalize_L2(query_vector)
                    distances, indices = self.index.search(query_vector, search_k)

                    for i in range(len(indices[0])):
                        idx = indices[0][i]
                        score = float(distances[0][i])
                        if idx < len(self.ids):
                            item_id = self.ids[idx]
                            item = self.data_dict.get(item_id)
                            if not item:
                                continue
                            if not self._matches_filters(item, province=province, city=city, notice_type=notice_type):
                                continue

                            v_results_dict[item_id] = {"rank": len(v_results_dict), "score": score}
                            if len(v_results_dict) >= search_k:
                                break

        # 2. BM25 检索
        b_results_dict = {}
        if use_bm25 and self.bm25:
            query_words = list(jieba.cut(query_text))
            bm25_scores = self.bm25.get_scores(query_words)
            top_b_indices = np.argsort(bm25_scores)[::-1]
            
            # 归一化 BM25 分数
            max_bm25 = np.max(bm25_scores) if len(bm25_scores) > 0 else 1.0
            if max_bm25 == 0: max_bm25 = 1.0

            count = 0
            for idx in top_b_indices:
                if bm25_scores[idx] <= 0: break
                
                item = self.raw_data[idx]
                item_id = str(item.get('uuid') or item.get('id') or item.get('project_id') or "")
                if not item_id: continue
                if not self._matches_filters(item, province=province, city=city, notice_type=notice_type):
                    continue
                
                b_results_dict[item_id] = {
                    "rank": count, 
                    "score": float(bm25_scores[idx]),
                    "norm_score": float(bm25_scores[idx] / max_bm25)
                }
                count += 1
                if count >= search_k: break
        
        # 3. RRF 融合逻辑
        combined_scores = {}
        k = 60 # RRF 常数
        
        # 合并所有 ID
        all_ids = set(v_results_dict.keys()) | set(b_results_dict.keys())
        
        for item_id in all_ids:
            v_info = v_results_dict.get(item_id)
            b_info = b_results_dict.get(item_id)
            
            # 计算 RRF 分数
            rrf_score = 0.0
            if v_info:
                rrf_score += vector_weight * (1.0 / (k + v_info["rank"] + 1))
            if b_info:
                rrf_score += bm25_weight * (1.0 / (k + b_info["rank"] + 1))
                
            combined_scores[item_id] = {
                "rrf_score": rrf_score,
                "vector_score": v_info["score"] if v_info else 0.0,
                "bm25_score": b_info["score"] if b_info else 0.0,
                "bm25_norm_score": b_info["norm_score"] if b_info else 0.0
            }
            
        # 4. 按项目汇总逻辑 (如果启用)
        if aggregate_by_project and self.data_type == "tender":
            # 加载汇总后的项目数据
            agg_path = BASE_DIR / "data/output/etl/projects_aggregated.jsonl"
            if os.path.exists(agg_path):
                agg_projects = load_jsonl(str(agg_path))
                
                # 构建 URL 到项目模块的映射
                url_to_project = {}
                for proj in agg_projects:
                    for event in proj.get('events', []):
                        url_to_project[event.get('url')] = proj
                
                # 按项目汇总得分
                project_scores = {} # key: project_key (name@buyer), value: {scores_list, project_data}
                
                for item_id, scores in combined_scores.items():
                    item = self.data_dict.get(item_id)
                    if not item: continue
                    
                    source_url = item.get('source_url')
                    project_module = url_to_project.get(source_url)
                    
                    if project_module:
                        # 过滤逻辑：排除已中标
                        if exclude_won and project_module.get('status') == "已中标":
                            continue

                        proj_key = f"{project_module['project_name_std']}@{project_module['buyer_name']}"
                        if proj_key not in project_scores:
                            project_scores[proj_key] = {
                                "rrf_scores": [],
                                "vector_scores": [],
                                "bm25_scores": [],
                                "bm25_norm_scores": [],
                                "project_data": project_module
                            }
                        project_scores[proj_key]["rrf_scores"].append(scores["rrf_score"])
                        project_scores[proj_key]["vector_scores"].append(scores["vector_score"])
                        project_scores[proj_key]["bm25_scores"].append(scores["bm25_score"])
                        project_scores[proj_key]["bm25_norm_scores"].append(scores["bm25_norm_score"])
                
                # 计算项目平均分
                final_project_results = []
                for proj_key, info in project_scores.items():
                    avg_rrf = sum(info["rrf_scores"]) / len(info["rrf_scores"])
                    avg_vector = sum(info["vector_scores"]) / len(info["vector_scores"])
                    avg_bm25 = sum(info["bm25_scores"]) / len(info["bm25_scores"])
                    avg_bm25_norm = sum(info["bm25_norm_scores"]) / len(info["bm25_norm_scores"])
                    
                    # 客户价值加权逻辑
                    client_boost = 1.0
                    if client_value_weight > 0:
                        # 从统一画像格式获取客户评分
                        profile = info["project_data"].get("buyer_profile_summary")
                        if profile and profile.get("avg_score"):
                            # 旧格式兼容
                            avg_score = profile["avg_score"]
                        else:
                            # 尝试从画像数据的 value_profile 获取
                            buyer_name = info["project_data"].get("buyer_name_std", "")
                            # 这里直接用项目自身的评分作为客户评分
                            avg_score = info["project_data"].get("opportunity_score", 0)

                        if avg_score:
                            # 将 0-100 的 avg_score 映射为 0.8 - 1.2 的系数
                            # 如果 avg_score=100, boost=1.2; 如果 avg_score=0, boost=0.8
                            boost_val = 0.8 + (avg_score / 100.0) * 0.4
                            client_boost = 1.0 + (boost_val - 1.0) * client_value_weight
                    
                    final_project_results.append({
                        "id": proj_key,
                        "score": round(avg_rrf * 1000 * client_boost, 4),
                        "rrf_raw_score": round(avg_rrf * client_boost, 6),
                        "vector_score": round(avg_vector, 4),
                        "bm25_score": round(avg_bm25, 2),
                        "bm25_norm_score": round(avg_bm25_norm, 4),
                        "client_boost": round(client_boost, 4),
                        "data": info["project_data"],
                        "is_aggregated": True,
                        "match_count": len(info["rrf_scores"]),
                        "latest_date": info["project_data"].get("latest_publish_date", "")
                    })
                
                # 排序逻辑
                if sort_by == "date":
                    # 1. 先按分数取 TopK (已经在上面计算好了 final_project_results)
                    # 2. 对这 TopK 条结果按时间倒序排列
                    top_by_score = sorted(final_project_results, key=lambda x: x["score"], reverse=True)[:top_k]
                    return sorted(top_by_score, key=lambda x: x["latest_date"] or "", reverse=True)
                else:
                    # 默认完全按分数排序
                    return sorted(final_project_results, key=lambda x: x["score"], reverse=True)[:top_k]

        # 5. 默认按单条公告排序输出
        sorted_items = sorted(combined_scores.items(), key=lambda x: x[1]["rrf_score"], reverse=True)[:top_k]
        
        final_results = []
        for item_id, scores in sorted_items:
            item = self.data_dict.get(item_id)
            if not item:
                continue
                
            final_results.append({
                "id": item_id,
                "score": round(scores["rrf_score"] * 1000, 4), # 放大 RRF 分数便于观察
                "rrf_raw_score": round(scores["rrf_score"], 6),
                "vector_score": round(scores["vector_score"], 4),
                "bm25_score": round(scores["bm25_score"], 2),
                "bm25_norm_score": round(scores["bm25_norm_score"], 4),
                "data": item
            })
            
        return final_results

if __name__ == "__main__":
    # 简单测试
    retriever = DualRetriever(data_type="tender")
    test_query = "气象站 采购 河北"
    print(f"\n[TEST] 查询: {test_query}")
    
    # 测试项目汇总模式
    results = retriever.hybrid_search(test_query, top_k=5, aggregate_by_project=True)
    for i, res in enumerate(results):
        status_str = f"[{res['data'].get('status')}]"
        print(f"[{i+1}] Avg Score: {res['score']:.4f} {status_str} | {res['data'].get('project_name_std')} ({res['match_count']}条公告关联)")
        for event in res['data'].get('events', []):
            print(f"    - {event['type']}: {event['title']}")
