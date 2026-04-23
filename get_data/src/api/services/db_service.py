# -*- coding: utf-8 -*-
"""数据库服务"""

import sqlite3
import json
import sys
import os
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# 添加 src 目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from config import DB_PATH


@contextmanager
def get_db_connection():
    """获取数据库连接上下文管理器"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def dict_from_row(row) -> dict:
    """将 sqlite3.Row 转换为字典"""
    return dict(row) if row else {}


def get_tender_by_id(tender_id: int) -> Optional[Dict[str, Any]]:
    """根据 ID 获取招标项目"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tenders WHERE id = ?
        """, (tender_id,))
        row = cursor.fetchone()
        return dict_from_row(row) if row else None


def get_structured_by_tender_id(tender_id: int) -> Optional[Dict[str, Any]]:
    """获取招标项目的结构化数据"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tender_structured WHERE tender_id = ?
        """, (tender_id,))
        row = cursor.fetchone()
        return dict_from_row(row) if row else None


def get_chunks_by_tender_id(tender_id: int) -> List[Dict[str, Any]]:
    """获取招标项目的 RAG 分块"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tender_chunks
            WHERE tender_id = ?
            ORDER BY chunk_type, chunk_order
        """, (tender_id,))
        return [dict_from_row(row) for row in cursor.fetchall()]


def get_tenders_list(
    keyword: Optional[str] = None,
    announce_type: Optional[str] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    min_budget: Optional[float] = None,
    max_budget: Optional[float] = None,
    min_score: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    offset: int = 0,
    limit: int = 20
) -> tuple[List[Dict[str, Any]], int]:
    """获取招标列表（带筛选和分页）"""
    where_clauses = []
    params = []

    # 构建 WHERE 子句
    if keyword:
        where_clauses.append("(t.project_name LIKE ? OR ts.buyer_name_std LIKE ? OR ts.content_summary LIKE ?)")
        keyword_pattern = f"%{keyword}%"
        params.extend([keyword_pattern, keyword_pattern, keyword_pattern])

    if announce_type:
        where_clauses.append("ts.announce_type = ?")
        params.append(announce_type)

    if province:
        where_clauses.append("ts.province = ?")
        params.append(province)

    if city:
        where_clauses.append("ts.city = ?")
        params.append(city)

    if min_budget is not None:
        where_clauses.append("ts.budget_amount >= ?")
        params.append(min_budget)

    if max_budget is not None:
        where_clauses.append("ts.budget_amount <= ?")
        params.append(max_budget)

    if min_score is not None:
        where_clauses.append("ts.opportunity_score >= ?")
        params.append(min_score)

    if start_date:
        where_clauses.append("t.publish_date >= ?")
        params.append(start_date)

    if end_date:
        where_clauses.append("t.publish_date <= ?")
        params.append(end_date)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 查询总数
        count_sql = f"""
            SELECT COUNT(*) FROM tenders t
            LEFT JOIN tender_structured ts ON t.id = ts.tender_id
            WHERE {where_sql}
        """
        cursor.execute(count_sql, params)
        total = cursor.fetchone()[0]

        # 查询数据
        data_sql = f"""
            SELECT
                t.id, t.project_name, t.publish_date,
                ts.announce_type, ts.province, ts.city,
                ts.budget_amount, ts.budget_unit,
                ts.opportunity_score, ts.buyer_name_std
            FROM tenders t
            LEFT JOIN tender_structured ts ON t.id = ts.tender_id
            WHERE {where_sql}
            ORDER BY t.publish_date DESC, t.id DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(data_sql, params + [limit, offset])
        items = [dict_from_row(row) for row in cursor.fetchall()]

        return items, total


def get_stats_overview() -> Dict[str, Any]:
    """获取统计概览"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 总招标数
        cursor.execute("SELECT COUNT(*) FROM tenders")
        total_tenders = cursor.fetchone()[0]

        # 结构化数据数
        cursor.execute("SELECT COUNT(*) FROM tender_structured")
        total_structured = cursor.fetchone()[0]

        # 分块数
        cursor.execute("SELECT COUNT(*) FROM tender_chunks")
        total_chunks = cursor.fetchone()[0]

        # 平均机会评分
        cursor.execute("SELECT AVG(opportunity_score) FROM tender_structured WHERE opportunity_score IS NOT NULL")
        avg_score = cursor.fetchone()[0]

        # 日期范围
        cursor.execute("SELECT MIN(publish_date), MAX(publish_date) FROM tenders")
        row = cursor.fetchone()
        date_range = {
            "min_date": row[0] if row else None,
            "max_date": row[1] if row else None
        }

        return {
            "total_tenders": total_tenders,
            "total_structured": total_structured,
            "total_chunks": total_chunks,
            "avg_opportunity_score": round(avg_score, 2) if avg_score else None,
            "date_range": date_range
        }


def get_stats_by_province() -> List[Dict[str, Any]]:
    """按省份统计"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT province, COUNT(*) as count
            FROM tender_structured
            WHERE province IS NOT NULL AND province != ''
            GROUP BY province
            ORDER BY count DESC
        """)
        return [dict_from_row(row) for row in cursor.fetchall()]


def get_stats_by_type() -> List[Dict[str, Any]]:
    """按公告类型统计"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT announce_type, COUNT(*) as count
            FROM tender_structured
            WHERE announce_type IS NOT NULL AND announce_type != ''
            GROUP BY announce_type
            ORDER BY count DESC
        """)
        return [dict_from_row(row) for row in cursor.fetchall()]


def get_announce_types() -> List[str]:
    """获取所有公告类型"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT announce_type
            FROM tender_structured
            WHERE announce_type IS NOT NULL AND announce_type != ''
            ORDER BY announce_type
        """)
        return [row[0] for row in cursor.fetchall()]


def get_provinces() -> List[str]:
    """获取所有省份"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT province
            FROM tender_structured
            WHERE province IS NOT NULL AND province != ''
            ORDER BY province
        """)
        return [row[0] for row in cursor.fetchall()]
