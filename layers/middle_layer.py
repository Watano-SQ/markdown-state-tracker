"""
中间层：状态存储与管理
"""
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from pathlib import Path
import logging
from time import perf_counter

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app_logging import get_logger, log_event
from db import get_connection


logger = get_logger("db")

# ============================================================================
# Extraction JSON Schema Definitions
# ============================================================================

@dataclass
class TimeInfo:
    """时间信息（带来源）
    
    Attributes:
        normalized: 标准化时间字符串（ISO 8601 或自定义格式）
        source: 时间来源（explicit/document_context/inferred/unknown）
        raw: 原始时间文本（可选）
    """
    normalized: Optional[str] = None
    source: str = "unknown"  # explicit | document_context | inferred | unknown
    raw: Optional[str] = None


@dataclass
class Entity:
    """实体（chunk 级局部观察）
    
    Attributes:
        text: 实体文本
        type: 实体类型（person/organization/location/concept/tool等）
        context: 上下文信息（可选）
        confidence: 置信度（0-1）
    """
    text: str
    type: str
    context: Optional[str] = None
    confidence: float = 1.0


@dataclass
class Event:
    """事件（chunk 级局部观察）
    
    Attributes:
        description: 事件描述
        time: 时间信息（可选）
        participants: 参与者列表（可选）
        location: 地点（可选）
        context: 上下文信息（可选）
        confidence: 置信度（0-1）
    """
    description: str
    time: Optional[TimeInfo] = None
    participants: List[str] = field(default_factory=list)
    location: Optional[str] = None
    context: Optional[str] = None
    confidence: float = 1.0


@dataclass
class StateCandidate:
    """状态候选（chunk 级局部观察，不是最终 state）
    
    Attributes:
        summary: 状态摘要
        category: 大类建议（dynamic/static）
        subtype: 小类建议（可选）
        detail: 详细信息（可选）
        time: 时间信息（可选）
        confidence: 置信度（0-1）
    """
    summary: str
    category: Optional[str] = None
    subtype: Optional[str] = None
    detail: Optional[str] = None
    time: Optional[TimeInfo] = None
    confidence: float = 1.0


@dataclass
class RelationCandidate:
    """关系候选（chunk 级局部观察）
    
    Attributes:
        source: 源对象文本
        target: 目标对象文本
        relation_type: 关系类型（uses/belongs_to/related_to等）
        context: 上下文信息（可选）
        confidence: 置信度（0-1）
    """
    source: str
    target: str
    relation_type: str
    context: Optional[str] = None
    confidence: float = 1.0


@dataclass
class RetrievalCandidate:
    """检索候选对象（语义不确定但重要的实体）
    
    Attributes:
        surface_form: 原始出现形式
        type_guess: 类型猜测（可选）
        context: 上下文信息（可选）
        priority: 优先级（0-10）
    """
    surface_form: str
    type_guess: Optional[str] = None
    context: Optional[str] = None
    priority: int = 0


@dataclass
class ExtractionContext:
    """抽取上下文信息
    
    Attributes:
        chunk_position: chunk 在文档中的位置（start/middle/end）
        document_title: 文档标题（可选）
        document_time: 文档默认时间上下文（可选）
        section: 所属章节（可选）
    """
    chunk_position: Optional[str] = None  # start | middle | end
    document_title: Optional[str] = None
    document_time: Optional[TimeInfo] = None
    section: Optional[str] = None


@dataclass
class ExtractionResult:
    """单个 chunk 的抽取结果（结构化 schema）
    
    这是 chunk 级的局部观察层，不是最终的 state。
    
    Attributes:
        context: 抽取上下文信息
        entities: 实体列表
        events: 事件列表
        state_candidates: 状态候选列表
        relation_candidates: 关系候选列表
        retrieval_candidates: 检索候选列表
    """
    context: ExtractionContext = field(default_factory=ExtractionContext)
    entities: List[Entity] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)
    state_candidates: List[StateCandidate] = field(default_factory=list)
    relation_candidates: List[RelationCandidate] = field(default_factory=list)
    retrieval_candidates: List[RetrievalCandidate] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（自动处理嵌套 dataclass）"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExtractionResult':
        """从字典创建（带类型转换）"""
        # 转换上下文对象（包括嵌套的 TimeInfo）
        context_data = data.get('context', {})
        if context_data:
            doc_time_data = context_data.get('document_time')
            if doc_time_data and isinstance(doc_time_data, dict):
                context_data['document_time'] = TimeInfo(**doc_time_data)
            context = ExtractionContext(**context_data)
        else:
            context = ExtractionContext()
        
        entities = [Entity(**e) for e in data.get('entities', [])]
        
        events = []
        for e in data.get('events', []):
            time_data = e.get('time')
            if time_data and isinstance(time_data, dict):
                e['time'] = TimeInfo(**time_data)
            events.append(Event(**e))
        
        state_candidates = []
        for s in data.get('state_candidates', []):
            time_data = s.get('time')
            if time_data and isinstance(time_data, dict):
                s['time'] = TimeInfo(**time_data)
            state_candidates.append(StateCandidate(**s))
        
        relation_candidates = [RelationCandidate(**r) for r in data.get('relation_candidates', [])]
        retrieval_candidates = [RetrievalCandidate(**r) for r in data.get('retrieval_candidates', [])]
        
        return cls(
            context=context,
            entities=entities,
            events=events,
            state_candidates=state_candidates,
            relation_candidates=relation_candidates,
            retrieval_candidates=retrieval_candidates
        )


# ============================================================================
# Database Functions
# ============================================================================


def save_extraction(
    chunk_id: int,
    result: ExtractionResult,
    extractor_type: str = "rule_based",
    model_name: Optional[str] = None,
    prompt_version: Optional[str] = None
) -> int:
    """保存抽取结果到数据库
    
    Args:
        chunk_id: chunk ID
        result: 抽取结果对象
        extractor_type: 抽取器类型（llm, rule_based, hybrid）
        model_name: 模型名称（如 gpt-4, claude-3, custom_rules）
        prompt_version: prompt 版本（如 v1.0, v2.1）
    
    Returns:
        extraction_id
    """
    start_time = perf_counter()
    conn = get_connection()
    cursor = conn.cursor()
    
    # 保存原始抽取结果（JSON 格式，便于调试）
    cursor.execute("""
        INSERT INTO extractions (chunk_id, extraction_json, extractor_type, model_name, prompt_version)
        VALUES (?, ?, ?, ?, ?)
    """, (chunk_id, json.dumps(result.to_dict(), ensure_ascii=False), 
          extractor_type, model_name, prompt_version))
    
    extraction_id = cursor.lastrowid
    conn.commit()
    log_event(
        logger,
        logging.INFO,
        "save_extraction_done",
        "Saved extraction result",
        stage="db",
        chunk_id=chunk_id,
        extraction_id=extraction_id,
        model=model_name,
        action=extractor_type,
        entity_count=len(result.entities),
        state_candidate_count=len(result.state_candidates),
        relation_candidate_count=len(result.relation_candidates),
        retrieval_candidate_count=len(result.retrieval_candidates),
        duration_ms=(perf_counter() - start_time) * 1000,
    )
    
    return extraction_id


def get_extractions_for_aggregation() -> List[Dict[str, Any]]:
    """获取聚合所需的 extraction 源数据。"""
    start_time = perf_counter()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT e.id AS extraction_id,
               e.chunk_id,
               e.extraction_json,
               e.extractor_type,
               e.model_name,
               e.prompt_version,
               c.document_id,
               c.chunk_index,
               d.path,
               d.title
        FROM extractions e
        JOIN chunks c ON e.chunk_id = c.id
        JOIN documents d ON c.document_id = d.id
        ORDER BY e.id
    """)

    rows = [dict(row) for row in cursor.fetchall()]
    log_event(
        logger,
        logging.INFO,
        "aggregation_sources_loaded",
        "Loaded extraction sources for aggregation",
        stage="db",
        extractions=len(rows),
        duration_ms=(perf_counter() - start_time) * 1000,
    )
    return rows


def get_pending_chunks() -> List[Dict[str, Any]]:
    """获取待抽取的 chunks"""
    start_time = perf_counter()
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT c.id, c.document_id, c.chunk_index, c.text, c.token_estimate,
               c.section_label,
               d.path, d.title
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE d.status = 'pending'
        AND NOT EXISTS (
            SELECT 1 FROM extractions e WHERE e.chunk_id = c.id
        )
        ORDER BY d.id, c.chunk_index
    """)
    
    rows = [dict(row) for row in cursor.fetchall()]
    log_event(
        logger,
        logging.INFO,
        "pending_chunks_loaded",
        "Loaded pending chunks",
        stage="db",
        pending_chunks=len(rows),
        duration_ms=(perf_counter() - start_time) * 1000,
    )
    return rows


def mark_document_processed(doc_id: int) -> None:
    """标记文档为已处理"""
    start_time = perf_counter()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE documents SET status = 'processed', updated_at = julianday('now') WHERE id = ?",
        (doc_id,)
    )
    conn.commit()
    log_event(
        logger,
        logging.INFO,
        "document_marked_processed",
        "Marked document as processed",
        stage="db",
        document_id=doc_id,
        duration_ms=(perf_counter() - start_time) * 1000,
    )


def add_state_evidence(
    state_id: int,
    chunk_id: Optional[int] = None,
    extraction_id: Optional[int] = None,
    evidence_role: str = 'source',
    weight: float = 1.0,
    note: Optional[str] = None
) -> int:
    """添加状态证据
    
    Args:
        state_id: 状态 ID
        chunk_id: chunk ID（可选）
        extraction_id: extraction ID（可选）
        evidence_role: 证据角色（source, supporting, contradicting）
        weight: 证据权重（0-1）
        note: 备注说明
    
    Returns:
        evidence_id
    """
    if chunk_id is None and extraction_id is None:
        raise ValueError("At least one of chunk_id or extraction_id must be provided")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO state_evidence (state_id, chunk_id, extraction_id, evidence_role, weight, note)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (state_id, chunk_id, extraction_id, evidence_role, weight, note))
    
    evidence_id = cursor.lastrowid
    conn.commit()
    return evidence_id


def ensure_state_evidence(
    state_id: int,
    chunk_id: Optional[int] = None,
    extraction_id: Optional[int] = None,
    evidence_role: str = 'source',
    weight: float = 1.0,
    note: Optional[str] = None
) -> Tuple[int, bool]:
    """确保状态证据存在，避免重复写入。"""
    if chunk_id is None and extraction_id is None:
        raise ValueError("At least one of chunk_id or extraction_id must be provided")

    conn = get_connection()
    cursor = conn.cursor()

    clauses = ["state_id = ?"]
    params: List[Any] = [state_id]

    if chunk_id is None:
        clauses.append("chunk_id IS NULL")
    else:
        clauses.append("chunk_id = ?")
        params.append(chunk_id)

    if extraction_id is None:
        clauses.append("extraction_id IS NULL")
    else:
        clauses.append("extraction_id = ?")
        params.append(extraction_id)

    cursor.execute(
        f"SELECT id FROM state_evidence WHERE {' AND '.join(clauses)}",
        tuple(params),
    )
    existing = cursor.fetchone()
    if existing:
        return existing['id'], False

    evidence_id = add_state_evidence(
        state_id=state_id,
        chunk_id=chunk_id,
        extraction_id=extraction_id,
        evidence_role=evidence_role,
        weight=weight,
        note=note,
    )
    return evidence_id, True


def get_state_evidence(state_id: int) -> List[Dict[str, Any]]:
    """获取状态的所有证据
    
    Args:
        state_id: 状态 ID
    
    Returns:
        证据列表
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, state_id, chunk_id, extraction_id, evidence_role, weight, note, created_at
        FROM state_evidence
        WHERE state_id = ?
        ORDER BY created_at DESC
    """, (state_id,))
    
    return [dict(row) for row in cursor.fetchall()]


def archive_orphan_states() -> int:
    """归档已无任何证据支撑的活跃状态项。"""
    start_time = perf_counter()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE states
        SET status = 'archived',
            last_updated = julianday('now')
        WHERE status = 'active'
          AND NOT EXISTS (
              SELECT 1
              FROM state_evidence se
              WHERE se.state_id = states.id
          )
    """)

    archived_count = cursor.rowcount
    conn.commit()
    log_event(
        logger,
        logging.INFO,
        "orphan_states_archived",
        "Archived active states without evidence",
        stage="db",
        archived_states=archived_count,
        duration_ms=(perf_counter() - start_time) * 1000,
    )
    return archived_count


def upsert_state(
    category: str,
    subtype: str,
    summary: str,
    detail: Optional[str] = None,
    chunk_ids: Optional[List[int]] = None,  # 重命名参数但保持兼容
    confidence: float = 1.0
) -> int:
    """插入或更新状态项
    
    如果已存在相似状态，更新它；否则创建新状态
    （当前版本使用简单匹配，后续可改进为语义匹配）
    
    Args:
        category: 大类
        subtype: 小类
        summary: 摘要
        detail: 详情
        chunk_ids: chunk ID 列表（将自动添加到 state_evidence）
        confidence: 置信度
    
    Returns:
        state_id
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 简单匹配：相同 category + subtype + 相似 summary
    cursor.execute("""
        SELECT id FROM states 
        WHERE category = ? AND subtype = ? AND summary = ? AND status = 'active'
    """, (category, subtype, summary))
    
    existing = cursor.fetchone()
    
    if existing:
        # 更新现有状态
        state_id = existing['id']
        cursor.execute("""
            UPDATE states 
            SET detail = COALESCE(?, detail),
                confidence = ?,
                last_updated = julianday('now')
            WHERE id = ?
        """, (detail, confidence, state_id))
        
        # 添加新的证据（如果有）
        if chunk_ids:
            for chunk_id in chunk_ids:
                # 检查是否已存在
                cursor.execute("""
                    SELECT id FROM state_evidence 
                    WHERE state_id = ? AND chunk_id = ?
                """, (state_id, chunk_id))
                if not cursor.fetchone():
                    add_state_evidence(state_id, chunk_id=chunk_id)
    else:
        # 创建新状态
        cursor.execute("""
            INSERT INTO states (category, subtype, summary, detail, confidence)
            VALUES (?, ?, ?, ?, ?)
        """, (category, subtype, summary, detail, confidence))
        state_id = cursor.lastrowid
        
        # 添加证据
        if chunk_ids:
            for chunk_id in chunk_ids:
                add_state_evidence(state_id, chunk_id=chunk_id)
    
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
    start_time = perf_counter()
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
    
    log_event(
        logger,
        logging.INFO,
        "db_stats_collected",
        "Collected database statistics",
        stage="db",
        duration_ms=(perf_counter() - start_time) * 1000,
        **stats,
    )
    return stats
