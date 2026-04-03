"""
中间层：状态存储与管理
"""
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_connection


@dataclass
class ExtractionResult:
    """单个 chunk 的抽取结果"""
    events: List[Dict[str, Any]]      # 事件列表
    states: List[Dict[str, Any]]      # 状态列表
    entities: List[Dict[str, Any]]    # 实体列表
    relations: List[Dict[str, Any]]   # 关系列表
    candidates: List[Dict[str, Any]]  # 需要后续确认的候选对象


def save_extraction(chunk_id: int, result: ExtractionResult, model_version: str = "v0.1") -> int:
    """保存抽取结果到数据库"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 保存原始抽取结果（JSON 格式，便于调试）
    cursor.execute("""
        INSERT INTO extractions (chunk_id, extraction_json, model_version)
        VALUES (?, ?, ?)
    """, (chunk_id, json.dumps(asdict(result), ensure_ascii=False), model_version))
    
    extraction_id = cursor.lastrowid
    conn.commit()
    
    return extraction_id


def get_pending_chunks() -> List[Dict[str, Any]]:
    """获取待抽取的 chunks"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT c.id, c.document_id, c.chunk_index, c.text, c.token_estimate,
               d.path, d.title
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE d.status = 'pending'
        AND NOT EXISTS (
            SELECT 1 FROM extractions e WHERE e.chunk_id = c.id
        )
        ORDER BY d.id, c.chunk_index
    """)
    
    return [dict(row) for row in cursor.fetchall()]


def mark_document_processed(doc_id: int) -> None:
    """标记文档为已处理"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE documents SET status = 'processed', updated_at = julianday('now') WHERE id = ?",
        (doc_id,)
    )
    conn.commit()


def upsert_state(
    category: str,
    subtype: str,
    summary: str,
    detail: Optional[str] = None,
    source_chunk_ids: Optional[List[int]] = None,
    confidence: float = 1.0
) -> int:
    """插入或更新状态项
    
    如果已存在相似状态，更新它；否则创建新状态
    （当前版本使用简单匹配，后续可改进为语义匹配）
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 简单匹配：相同 category + subtype + 相似 summary
    cursor.execute("""
        SELECT id, source_chunk_ids FROM states 
        WHERE category = ? AND subtype = ? AND summary = ? AND status = 'active'
    """, (category, subtype, summary))
    
    existing = cursor.fetchone()
    
    chunk_ids_json = json.dumps(source_chunk_ids or [])
    
    if existing:
        # 更新现有状态
        state_id = existing['id']
        # 合并 source_chunk_ids
        old_chunks = json.loads(existing['source_chunk_ids'] or '[]')
        new_chunks = list(set(old_chunks + (source_chunk_ids or [])))
        
        cursor.execute("""
            UPDATE states 
            SET detail = COALESCE(?, detail),
                confidence = ?,
                last_updated = julianday('now'),
                source_chunk_ids = ?
            WHERE id = ?
        """, (detail, confidence, json.dumps(new_chunks), state_id))
    else:
        # 创建新状态
        cursor.execute("""
            INSERT INTO states (category, subtype, summary, detail, confidence, source_chunk_ids)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (category, subtype, summary, detail, confidence, chunk_ids_json))
        state_id = cursor.lastrowid
    
    conn.commit()
    return state_id


def add_retrieval_candidate(
    surface_form: str,
    type_guess: Optional[str] = None,
    scope_guess: Optional[str] = None,
    source_chunk_ids: Optional[List[int]] = None,
    priority: int = 0
) -> int:
    """添加检索候选对象"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 检查是否已存在
    cursor.execute(
        "SELECT id, evidence_count, source_chunk_ids FROM retrieval_candidates WHERE surface_form = ?",
        (surface_form,)
    )
    existing = cursor.fetchone()
    
    if existing:
        # 更新证据计数
        candidate_id = existing['id']
        old_chunks = json.loads(existing['source_chunk_ids'] or '[]')
        new_chunks = list(set(old_chunks + (source_chunk_ids or [])))
        
        cursor.execute("""
            UPDATE retrieval_candidates 
            SET evidence_count = evidence_count + 1,
                source_chunk_ids = ?,
                priority = MAX(priority, ?)
            WHERE id = ?
        """, (json.dumps(new_chunks), priority, candidate_id))
    else:
        # 创建新候选
        cursor.execute("""
            INSERT INTO retrieval_candidates 
            (surface_form, type_guess, scope_guess, source_chunk_ids, priority)
            VALUES (?, ?, ?, ?, ?)
        """, (surface_form, type_guess, scope_guess, json.dumps(source_chunk_ids or []), priority))
        candidate_id = cursor.lastrowid
    
    conn.commit()
    return candidate_id


def get_active_states(category: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """获取活跃状态项"""
    conn = get_connection()
    cursor = conn.cursor()
    
    if category:
        cursor.execute("""
            SELECT * FROM states 
            WHERE status = 'active' AND category = ?
            ORDER BY last_updated DESC
            LIMIT ?
        """, (category, limit))
    else:
        cursor.execute("""
            SELECT * FROM states 
            WHERE status = 'active'
            ORDER BY category, subtype, last_updated DESC
            LIMIT ?
        """, (limit,))
    
    return [dict(row) for row in cursor.fetchall()]


def archive_state(state_id: int) -> None:
    """归档状态项"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE states SET status = 'archived', last_updated = julianday('now') WHERE id = ?",
        (state_id,)
    )
    conn.commit()


def get_stats() -> Dict[str, int]:
    """获取中间层统计信息"""
    conn = get_connection()
    cursor = conn.cursor()
    
    stats = {}
    
    cursor.execute("SELECT COUNT(*) FROM documents")
    stats['documents'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM chunks")
    stats['chunks'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM extractions")
    stats['extractions'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM states WHERE status = 'active'")
    stats['active_states'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM states WHERE status = 'archived'")
    stats['archived_states'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM retrieval_candidates WHERE decision_status = 'pending'")
    stats['pending_candidates'] = cursor.fetchone()[0]
    
    return stats
