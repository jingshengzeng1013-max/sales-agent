# -*- coding: utf-8 -*-
"""
查询招标公告模块：从数据库获取招标公告信息
"""
import sqlite3
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from src.config import DB_PATH

logger = logging.getLogger("get_data.tools.query_tenders")


def query_tenders(
    tender_ids: Optional[List[int]] = None,
    keywords: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> Tuple[List[Dict[str, Any]], int]:
    """
    查询招标公告

    Args:
        tender_ids: 指定招标 ID 列表
        keywords: 关键字（在项目名或内容中搜索）
        limit: 返回数量限制
        offset: 偏移量

    Returns:
        (结果列表，总数)
    """
    if not Path(DB_PATH).is_file():
        logger.warning(f"数据库文件不存在：{DB_PATH}")
        return [], 0

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # 构建查询
        conditions = []
        params = []

        if tender_ids:
            placeholders = ",".join("?" for _ in tender_ids)
            conditions.append(f"t.id IN ({placeholders})")
            params.extend(tender_ids)

        if keywords:
            conditions.append("(t.project_name LIKE ? OR t.content LIKE ?)")
            params.extend([f"%{keywords}%", f"%{keywords}%"])

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 计数查询
        count_sql = f"SELECT COUNT(*) FROM tenders t WHERE {where_clause}"
        count_row = conn.execute(count_sql, params).fetchone()
        total = count_row[0] if count_row else 0

        # 数据查询
        data_sql = f"""
            SELECT t.id, t.project_name, t.buyer_name, t.content,
                   t.detail_url, t.publish_date, t.budget
            FROM tenders t
            WHERE {where_clause}
            ORDER BY t.publish_date DESC
            LIMIT ? OFFSET ?
        """
        params_with_limit = params + [limit, offset]
        cursor = conn.execute(data_sql, params_with_limit)

        results = []
        for row in cursor.fetchall():
            d = dict(row)
            results.append(d)

        return results, total

    except Exception as e:
        logger.error(f"查询招标公告失败：{e}")
        return [], 0
    finally:
        conn.close()


def get_tender_by_id(tender_id: int) -> Optional[Dict[str, Any]]:
    """
    根据 ID 获取招标公告详情

    Args:
        tender_id: 招标 ID

    Returns:
        招标公告字典，不存在则返回 None
    """
    results, _ = query_tenders(tender_ids=[tender_id])
    return results[0] if results else None
