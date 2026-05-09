"""
输出层：状态文档生成
"""
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging
from time import perf_counter

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app_logging import get_logger, log_event
from config import OUTPUT_FILE
from db import get_connection


logger = get_logger("output")

# 输出模板配置
OUTPUT_CONFIG = {
    'dynamic': {
        'title': '动态状态',
        'description': '近期活跃、正在进行的事项',
        'subtypes': {
            'ongoing_project': '进行中的项目',
            'recent_event': '近期事件',
            'pending_task': '待办事项',
            'active_interest': '当前关注',
        },
        'max_items_per_subtype': 10,
    },
    'static': {
        'title': '稳定状态',
        'description': '长期不变或缓慢变化的信息',
        'subtypes': {
            'preference': '偏好设定',
            'background': '背景信息',
            'skill': '技能/能力',
            'relationship': '人际关系',
        },
        'max_items_per_subtype': 20,
    },
}


CONTEXT_SECTION_TITLES = [
    "当前目标",
    "进展",
    "问题",
    "下一步",
    "相关线索",
]

CONTEXT_SECTION_BY_SUBTYPE = {
    "ongoing_project": "进展",
    "recent_event": "进展",
    "pending_task": "下一步",
    "active_interest": "相关线索",
    "preference": "相关线索",
    "background": "相关线索",
    "skill": "相关线索",
    "relationship": "相关线索",
}

PROBLEM_HINTS = (
    "blocked",
    "blocker",
    "error",
    "failed",
    "failure",
    "issue",
    "problem",
    "stuck",
    "失败",
    "异常",
    "报错",
    "阻塞",
    "问题",
    "找不到",
    "未回复",
)

NEIGHBOR_CHUNK_DISTANCE = 1
LARGE_BUNDLE_STATE_COUNT = 10
ISSUE_ANCHOR_PATTERN = re.compile(r"(?:\bissue\s*#?\d+\b|#\d+)", re.IGNORECASE)
MODEL_ANCHOR_PATTERN = re.compile(
    r"\b(?:gpt-[\w.-]+|claude[\w.-]*|gemini[\w.-]*|qwen[\w.-]*|"
    r"llama[\w.-]*|deepseek[\w.-]*)\b",
    re.IGNORECASE,
)
BACKTICK_ANCHOR_PATTERN = re.compile(r"`([^`\n]{2,80})`")


DEFAULT_PROFILE_NAME = "default"
DEFAULT_NARRATIVE_MODE = "rule"
NARRATIVE_MODE_ENV = "OUTPUT_NARRATIVE_MODE"
VALID_NARRATIVE_MODES = {"rule", "llm", "auto"}
READING_ROLE_STANDALONE = "standalone"
READING_ROLE_SUPPORTING = "supporting"
READING_ROLE_DEFER = "defer"
NARRATIVE_SECTION_ORDER = [
    "current_goal",
    "progress",
    "problem",
    "next_step",
    "related_context",
]
NARRATIVE_SECTION_TITLES = {
    "current_goal": "当前目标",
    "progress": "进展",
    "problem": "问题",
    "next_step": "下一步",
    "related_context": "相关线索",
}
WEAK_TOPIC_TITLES = {
    "当前目标",
    "进展",
    "问题",
    "下一步",
    "相关线索",
    "工具",
    "工具:",
    "工具：",
    "背景",
    "背景:",
    "背景：",
}
GENERIC_CONTEXT_LABELS = {
    "杂记",
    "general",
    "notes",
    "note",
    "misc",
    "未命名主题",
}
SUPPORTING_CONTEXT_SUBTYPES = {
    "background",
    "active_interest",
    "relationship",
    "skill",
}
READABLE_RELATION_SUBTYPES = {
    "ongoing_project",
    "recent_event",
    "pending_task",
    "active_interest",
    "preference",
    "background",
    "skill",
    "relationship",
}
CONNECTION_STOP_WORDS = {
    "the",
    "this",
    "that",
    "only",
    "later",
    "next",
    "current",
    "adjacent",
    "fallback",
    "empty",
    "short",
    "generic",
    "first",
    "second",
    "final",
    "local",
    "separate",
    "seeded",
}
ENGLISH_ANCHOR_PATTERN = re.compile(
    r"\b[A-Z][A-Za-z0-9]*(?:\s+[A-Za-z][A-Za-z0-9]*){0,3}\b"
)
FORBIDDEN_SUMMARY_PHRASES = (
    "主要涉及：",
    "主要涉及:",
    "核心信息是：",
    "核心信息是:",
)


@dataclass(frozen=True)
class OutputProfile:
    name: str
    config: Dict[str, Dict[str, Any]]
    output_path: Path


@dataclass(frozen=True)
class ReadingDecision:
    """
    输出层内部审查结果。
    它只决定某条状态在阅读视图中的使用方式，不改变数据库中的 state。
    """

    state_id: int
    # 被审查的状态编号。

    role: str
    # 状态在阅读视图中的角色。
    # "standalone" 表示可独立输出。
    # "supporting" 表示可作为其他阅读簇的支撑材料。
    # "defer" 表示暂不输出，只进入内部诊断。

    reason: str
    # 中文理由。说明为什么采用该角色。

    evidence_signals: tuple[str, ...]
    # 本次判断使用到的证据信号。
    # 例如：有证据 chunk、有明确主体、有明确对象、有相邻上下文、有事件线索。

    missing_signals: tuple[str, ...]
    # 暂不输出或不能独立输出时缺少的信号。
    # 例如：缺少明确对象、缺少主体、缺少可解释上下文。


@dataclass(frozen=True)
class ReadingCluster:
    """
    阅读视图中的上下文簇。
    它把若干状态组织到同一个读者可理解的上下文中。
    它不是数据库事实，不改变任何 state 的主体字段。
    """

    cluster_id: str
    # 输出层临时编号，只用于诊断和测试，不落库。

    title: str
    # 阅读簇标题。
    # 应来自章节、文档标题、明确项目名、明确事件名或强锚点。

    state_ids: tuple[int, ...]
    # 被放进同一个阅读簇的状态编号。

    primary_state_ids: tuple[int, ...]
    # 构成该阅读簇主叙述的状态编号。

    supporting_state_ids: tuple[int, ...]
    # 只作为支撑材料的状态编号。

    subject_identities: tuple[tuple[Optional[str], Optional[str]], ...]
    # 阅读簇中出现过的主体身份。
    # 多主体只表示共同出现在同一阅读上下文，不表示主体被合并。

    merge_reasons: tuple[str, ...]
    # 这些状态被放入同一阅读簇的理由。
    # 例如：同一文档、相邻 chunk、同一章节、共享工具对象、共享事件线索。

    risk_flags: tuple[str, ...]
    # 可能误归组的风险提示。


@dataclass(frozen=True)
class ContextBundleState:
    state_id: int
    category: str
    subtype: str
    summary: str
    detail: Optional[str]
    confidence: float
    last_updated: Optional[float]
    needs_context_reason: Optional[str] = None
    sections: tuple[str, ...] = ()
    evidence_excerpt: Optional[str] = None
    source_chunk_ids: tuple[int, ...] = ()
    strong_anchors: tuple[str, ...] = ()
    reading_role: str = READING_ROLE_STANDALONE
    # 该状态在阅读视图中的输出角色。
    reading_reason: str = ""
    # 输出角色的中文理由。
    reading_evidence_signals: tuple[str, ...] = ()
    # 支撑该输出角色判断的证据信号。
    reading_missing_signals: tuple[str, ...] = ()
    # 暂不输出或不能独立输出时缺少的信号。


@dataclass(frozen=True)
class ContextBundle:
    title: str
    source_document: str
    subject_type: Optional[str]
    subject_key: Optional[str]
    state_ids: List[int]
    evidence_chunk_ids: List[int]
    sections: List[str]
    merge_basis: List[str]
    items: List[ContextBundleState]
    primary_state_ids: tuple[int, ...] = ()
    # 阅读簇主叙述状态编号。
    supporting_state_ids: tuple[int, ...] = ()
    # 阅读簇支撑材料状态编号。
    subject_identities: tuple[tuple[Optional[str], Optional[str]], ...] = ()
    # 该输出 bundle 中出现过的主体身份；不表示主体合并。
    risk_flags: tuple[str, ...] = ()
    # 输出层诊断用风险标记。
    reading_cluster_id: Optional[str] = None
    # output-only 阅读簇编号，不落库。


@dataclass(frozen=True)
class ContextBundleSelection:
    bundles: List[ContextBundle]
    needs_context_items: List[ContextBundleState]
    diagnostics: Dict[str, Any]


@dataclass(frozen=True)
class NarrativeEvidenceItem:
    state_id: int
    subtype: str
    summary: str
    detail: Optional[str]
    sections: tuple[str, ...]
    evidence_excerpt: Optional[str]
    source_chunk_ids: tuple[int, ...]
    strong_anchors: tuple[str, ...]
    reading_role: str = READING_ROLE_STANDALONE
    # 该证据项对应 state 在阅读视图中的输出角色。
    reading_reason: str = ""
    # 输出角色的中文理由。


@dataclass(frozen=True)
class CandidateTopicBundle:
    subject_type: Optional[str]
    subject_key: Optional[str]
    subject_label: str
    source_document: str
    topic_key: str
    topic_title_hint: str
    state_ids: tuple[int, ...]
    evidence_items: tuple[NarrativeEvidenceItem, ...]
    sections: tuple[str, ...]
    merge_basis: tuple[str, ...]


@dataclass(frozen=True)
class NarrativeSectionItem:
    kind: str
    text: str
    source_state_ids: tuple[int, ...]


@dataclass(frozen=True)
class OmittedNarrativeState:
    state_id: int
    reason: str


@dataclass(frozen=True)
class BundleNarrative:
    subject_type: Optional[str]
    subject_key: Optional[str]
    subject_label: str
    source_document: str
    topic_key: str
    topic_title: str
    bundle_summary: str
    sections: tuple[NarrativeSectionItem, ...]
    absorbed_state_ids: tuple[int, ...]
    omitted_state_ids: tuple[OmittedNarrativeState, ...]
    diagnostics: Dict[str, Any]


OUTPUT_PROFILES = {
    DEFAULT_PROFILE_NAME: OutputProfile(
        name=DEFAULT_PROFILE_NAME,
        config=OUTPUT_CONFIG,
        output_path=OUTPUT_FILE,
    ),
}


def get_output_profile(profile_name: str = DEFAULT_PROFILE_NAME) -> OutputProfile:
    try:
        return OUTPUT_PROFILES[profile_name]
    except KeyError as exc:
        raise ValueError(f"Unknown output profile: {profile_name}") from exc


def select_context_bundles_for_output(
    profile: Optional[OutputProfile] = None,
) -> ContextBundleSelection:
    """Build read-only context bundles from active states and their evidence.

    This is the v1 projection path only; it does not write bundle tables or
    mutate state identity.
    """
    start_time = perf_counter()
    conn = get_connection()
    cursor = conn.cursor()
    profile = profile or get_output_profile()
    allowed_subtypes = {
        (category, subtype)
        for category, config in profile.config.items()
        for subtype in config["subtypes"]
    }

    cursor.execute("""
        SELECT s.id AS state_id,
               s.category,
               s.subtype,
               s.subject_type,
               s.subject_key,
               COALESCE(s.canonical_summary, s.summary) AS canonical_summary,
               COALESCE(s.display_summary, s.summary) AS summary,
               s.detail,
               s.confidence,
               s.last_updated,
               se.chunk_id,
               se.extraction_id,
               c.document_id,
               c.chunk_index,
               c.section_label,
               c.text AS chunk_text,
               d.path AS document_path,
               d.title AS document_title,
               e.extraction_json
        FROM states s
        LEFT JOIN state_evidence se ON se.state_id = s.id
        LEFT JOIN chunks c ON se.chunk_id = c.id
        LEFT JOIN documents d ON c.document_id = d.id
        LEFT JOIN extractions e ON se.extraction_id = e.id
        WHERE s.status = 'active'
        ORDER BY d.id, c.chunk_index, s.last_updated DESC, s.id
    """)

    states_by_id: Dict[int, Dict[str, Any]] = {}
    for row in cursor.fetchall():
        if (row["category"], row["subtype"]) not in allowed_subtypes:
            continue

        state = states_by_id.setdefault(
            row["state_id"],
            {
                "state_id": row["state_id"],
                "category": row["category"],
                "subtype": row["subtype"],
                "subject_type": row["subject_type"],
                "subject_key": row["subject_key"],
                "canonical_summary": row["canonical_summary"],
                "summary": row["summary"],
                "detail": row["detail"],
                "confidence": row["confidence"],
                "last_updated": row["last_updated"],
                "evidence": [],
            },
        )
        if row["chunk_id"] is not None and row["document_id"] is not None:
            state["evidence"].append(
                {
                    "chunk_id": row["chunk_id"],
                    "extraction_id": row["extraction_id"],
                    "document_id": row["document_id"],
                    "chunk_index": row["chunk_index"],
                    "section_label": row["section_label"],
                    "chunk_text": row["chunk_text"],
                    "document_path": row["document_path"],
                    "document_title": row["document_title"],
                    "extraction_json": row["extraction_json"],
                }
            )

    document_chunks_by_id = _load_document_chunks(
        {
            item["document_id"]
            for state in states_by_id.values()
            for item in state["evidence"]
        }
    )
    needs_context_items: List[ContextBundleState] = []
    reading_decisions: Dict[int, ReadingDecision] = {}
    document_groups: Dict[int, List[Dict[str, Any]]] = {}

    for state in states_by_id.values():
        decision = _review_single_state_readability(state)
        state["reading_decision"] = decision
        reading_decisions[state["state_id"]] = decision
        if decision.role == READING_ROLE_DEFER:
            needs_context_items.append(
                _context_state_from_row(
                    state,
                    _needs_context_reason_for_decision(decision),
                )
            )
            continue

        primary_evidence = sorted(
            state["evidence"],
            key=lambda item: (item["document_id"], item["chunk_index"]),
        )[0]
        document_groups.setdefault(primary_evidence["document_id"], []).append(state)

    candidate_groups: List[Dict[str, Any]] = []
    for document_id, group_states in document_groups.items():
        reading_clusters, deferred_states = _build_reading_clusters_for_document(
            document_id,
            group_states,
        )
        for state, reason in deferred_states:
            needs_context_items.append(_context_state_from_row(state, reason))
        for cluster in reading_clusters:
            cluster_state_ids = set(cluster.state_ids)
            candidate_groups.append(
                {
                    "states": [
                        state
                        for state in group_states
                        if state["state_id"] in cluster_state_ids
                    ],
                    "merge_basis": list(cluster.merge_reasons),
                    "reading_cluster": cluster,
                }
            )

    bundles = _finalize_context_bundles(
        candidate_groups,
        document_chunks_by_id,
        needs_context_items,
    )
    bundles.sort(key=lambda bundle: (bundle.source_document, bundle.state_ids))
    diagnostics = _build_context_bundle_diagnostics(bundles, needs_context_items)
    diagnostics["reading_roles"] = {
        state_id: _reading_decision_payload(decision)
        for state_id, decision in reading_decisions.items()
    }
    log_event(
        logger,
        logging.INFO,
        "context_bundles_selected_for_output",
        "Selected context bundles for output projection",
        stage="output",
        bundles=len(bundles),
        needs_context_items=len(needs_context_items),
        large_bundle_count=len(diagnostics["large_bundles"]),
        duration_ms=(perf_counter() - start_time) * 1000,
    )
    return ContextBundleSelection(
        bundles=bundles,
        needs_context_items=needs_context_items,
        diagnostics=diagnostics,
    )


def _review_single_state_readability(state: Dict[str, Any]) -> ReadingDecision:
    """审查单条 state 在没有同伴状态时是否可被读者独立理解。"""
    evidence = state.get("evidence") or []
    evidence_signals: List[str] = []
    missing_signals: List[str] = []

    if not evidence:
        return ReadingDecision(
            state_id=state["state_id"],
            role=READING_ROLE_DEFER,
            reason="状态没有可追溯证据",
            evidence_signals=(),
            missing_signals=("缺少证据链",),
        )

    if not any(item.get("chunk_id") and item.get("document_id") for item in evidence):
        return ReadingDecision(
            state_id=state["state_id"],
            role=READING_ROLE_DEFER,
            reason="状态不能回到原始上下文",
            evidence_signals=(),
            missing_signals=("缺少原始 chunk 或 document",),
        )

    evidence_signals.append("有证据 chunk")
    evidence_signals.append("能回到 document")

    has_subject = _has_explicit_subject(state)
    has_object = bool(_state_object_anchors(state))
    has_relation = _has_readable_relation(state)

    if has_subject:
        evidence_signals.append("有明确主体")
    else:
        missing_signals.append("缺少明确主体")

    if has_object:
        evidence_signals.append("有明确对象")
    else:
        missing_signals.append("缺少明确对象")

    if has_relation:
        evidence_signals.append("有可读关系")
    else:
        missing_signals.append("缺少可读关系")

    if has_subject and has_object and has_relation:
        role = _initial_reading_role_for_state(state)
        reason = (
            "主体、对象和关系足以独立阅读"
            if role == READING_ROLE_STANDALONE
            else "状态更适合作为阅读簇支撑材料"
        )
        return ReadingDecision(
            state_id=state["state_id"],
            role=role,
            reason=reason,
            evidence_signals=tuple(evidence_signals),
            missing_signals=tuple(missing_signals),
        )

    if has_object and has_relation:
        return ReadingDecision(
            state_id=state["state_id"],
            role=READING_ROLE_SUPPORTING,
            reason="缺少明确主体，但对象和关系可支撑附近阅读簇",
            evidence_signals=tuple(evidence_signals),
            missing_signals=tuple(missing_signals),
        )

    return ReadingDecision(
        state_id=state["state_id"],
        role=READING_ROLE_DEFER,
        reason="读者无法从当前状态恢复基本语义结构",
        evidence_signals=tuple(evidence_signals),
        missing_signals=tuple(missing_signals),
    )


def _initial_reading_role_for_state(state: Dict[str, Any]) -> str:
    if state.get("subtype") in SUPPORTING_CONTEXT_SUBTYPES:
        return READING_ROLE_SUPPORTING
    return READING_ROLE_STANDALONE


def _needs_context_reason_for_decision(decision: ReadingDecision) -> str:
    if "缺少证据链" in decision.missing_signals:
        return "missing_evidence"
    if "缺少原始 chunk 或 document" in decision.missing_signals:
        return "missing_source_context"
    if "缺少明确对象" in decision.missing_signals:
        return "missing_subject_or_object"
    if "缺少明确主体" in decision.missing_signals:
        return "missing_subject_or_object"
    return "unreadable_single_state"


def _reading_decision_payload(decision: ReadingDecision) -> Dict[str, Any]:
    return {
        "role": decision.role,
        "reason": decision.reason,
        "evidence_signals": list(decision.evidence_signals),
        "missing_signals": list(decision.missing_signals),
    }


def _has_explicit_subject(state: Dict[str, Any]) -> bool:
    subject_type = str(state.get("subject_type") or "").strip().lower()
    subject_key = str(state.get("subject_key") or "").strip().lower()
    if not subject_type or not subject_key:
        return False
    return subject_type not in {"unknown", "generic"} and subject_key not in {
        "unknown",
        "generic",
        "unknown_or_generic",
    }


def _has_readable_relation(state: Dict[str, Any]) -> bool:
    if state.get("subtype") in READABLE_RELATION_SUBTYPES:
        text = " ".join(
            part
            for part in [
                str(state.get("summary") or ""),
                str(state.get("detail") or ""),
                *_state_evidence_texts(state),
            ]
            if part
        ).strip()
        return bool(text)
    return False


def _state_object_anchors(state: Dict[str, Any]) -> set[str]:
    anchors: set[str] = set()
    for label in _state_section_labels(state):
        cleaned = _clean_context_label(label)
        if cleaned:
            anchors.add(cleaned.lower())

    text_parts = [
        str(state.get("canonical_summary") or ""),
        str(state.get("summary") or ""),
        str(state.get("detail") or ""),
        *_state_evidence_texts(state),
    ]
    for text in text_parts:
        anchors.update(_named_anchors_from_text(text))

    subject_key = str(state.get("subject_key") or "").strip().lower()
    if subject_key:
        anchors.discard(subject_key)
    return anchors


def _state_section_labels(state: Dict[str, Any]) -> set[str]:
    return {
        str(item.get("section_label") or "").strip()
        for item in state.get("evidence", [])
        if str(item.get("section_label") or "").strip()
    }


def _state_evidence_texts(state: Dict[str, Any]) -> List[str]:
    texts = [
        str(item.get("chunk_text") or "")
        for item in state.get("evidence", [])
        if item.get("chunk_text")
    ]
    for item in state.get("evidence", []):
        texts.extend(_extraction_signal_texts(item.get("extraction_json")))
    return texts


def _extraction_signal_texts(extraction_json: Optional[str]) -> List[str]:
    if not extraction_json:
        return []
    try:
        payload = json.loads(extraction_json)
    except (TypeError, ValueError):
        return []

    texts: List[str] = []
    for key in ("entities", "events", "relation_candidates"):
        values = payload.get(key) if isinstance(payload, dict) else None
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, dict):
                texts.extend(
                    str(item)
                    for item in value.values()
                    if isinstance(item, (str, int, float))
                )
    return texts


def _clean_context_label(value: str) -> str:
    text = _clean_topic_title(value)
    if not text:
        return ""
    if text.lower() in GENERIC_CONTEXT_LABELS:
        return ""
    return text


def _named_anchors_from_text(text: str) -> set[str]:
    anchors: set[str] = set()
    if not text:
        return anchors

    anchors.update(match.group(0).lower() for match in ISSUE_ANCHOR_PATTERN.finditer(text))
    anchors.update(match.group(0).lower() for match in MODEL_ANCHOR_PATTERN.finditer(text))
    anchors.update(
        match.group(1).strip().lower()
        for match in BACKTICK_ANCHOR_PATTERN.finditer(text)
        if match.group(1).strip()
    )
    for match in ENGLISH_ANCHOR_PATTERN.finditer(text):
        candidate = re.sub(r"\s+", " ", match.group(0)).strip(" .。；;：:,，")
        if not _is_useful_named_anchor(candidate):
            continue
        anchors.add(candidate.lower())
    return anchors


def _is_useful_named_anchor(candidate: str) -> bool:
    if len(candidate) < 2:
        return False
    lowered = candidate.lower()
    first_word = lowered.split()[0]
    if first_word in CONNECTION_STOP_WORDS:
        return False
    if lowered in GENERIC_CONTEXT_LABELS:
        return False
    if "generic" in lowered:
        return False
    if len(candidate.split()) >= 2:
        return True
    return (
        candidate.isupper()
        or any(char.isdigit() for char in candidate)
        or any(char.islower() for char in candidate[1:])
    )


def _context_state_from_row(
    row: Dict[str, Any],
    needs_context_reason: Optional[str] = None,
) -> ContextBundleState:
    evidence = row.get("evidence") or []
    sections = tuple(
        sorted({item["section_label"] for item in evidence if item.get("section_label")})
    )
    source_chunk_ids = tuple(
        sorted({item["chunk_id"] for item in evidence if item.get("chunk_id") is not None})
    )
    evidence_excerpt = None
    if evidence:
        evidence_excerpt = _shorten_text(str(evidence[0].get("chunk_text") or ""), 220)
    decision = row.get("reading_decision")
    if isinstance(decision, ReadingDecision):
        reading_role = decision.role
        reading_reason = decision.reason
        evidence_signals = decision.evidence_signals
        missing_signals = decision.missing_signals
    elif needs_context_reason:
        reading_role = READING_ROLE_DEFER
        reading_reason = needs_context_reason
        evidence_signals = ()
        missing_signals = (needs_context_reason,)
    else:
        reading_role = READING_ROLE_STANDALONE
        reading_reason = ""
        evidence_signals = ()
        missing_signals = ()

    return ContextBundleState(
        state_id=row["state_id"],
        category=row["category"],
        subtype=row["subtype"],
        summary=row["summary"],
        detail=row["detail"],
        confidence=row["confidence"],
        last_updated=row["last_updated"],
        needs_context_reason=needs_context_reason,
        sections=sections,
        evidence_excerpt=evidence_excerpt,
        source_chunk_ids=source_chunk_ids,
        strong_anchors=tuple(sorted(_strong_anchors_for_state(row))),
        reading_role=reading_role,
        reading_reason=reading_reason,
        reading_evidence_signals=evidence_signals,
        reading_missing_signals=missing_signals,
    )


def _load_document_chunks(
    document_ids: set[int],
) -> Dict[int, List[Dict[str, Any]]]:
    if not document_ids:
        return {}

    conn = get_connection()
    cursor = conn.cursor()
    ordered_ids = sorted(document_ids)
    placeholders = ",".join("?" for _ in ordered_ids)
    cursor.execute(
        f"""
        SELECT id,
               document_id,
               chunk_index,
               section_label,
               text
        FROM chunks
        WHERE document_id IN ({placeholders})
        ORDER BY document_id, chunk_index
        """,
        tuple(ordered_ids),
    )

    chunks_by_document: Dict[int, List[Dict[str, Any]]] = {}
    for row in cursor.fetchall():
        chunks_by_document.setdefault(row["document_id"], []).append(dict(row))
    return chunks_by_document


def _build_reading_clusters_for_document(
    document_id: int,
    states: List[Dict[str, Any]],
) -> tuple[List[ReadingCluster], List[tuple[Dict[str, Any], str]]]:
    """在单个文档内形成 output-only 阅读簇，不改写 state 主体字段。"""
    if not states:
        return [], []

    state_by_id = {state["state_id"]: state for state in states}
    adjacency: Dict[int, set[int]] = {state["state_id"]: set() for state in states}
    edge_reasons: Dict[tuple[int, int], set[str]] = {}

    for left_index, left in enumerate(states):
        for right in states[left_index + 1:]:
            can_connect, reasons = _states_can_share_reading_cluster(left, right)
            if not can_connect:
                continue
            left_id = left["state_id"]
            right_id = right["state_id"]
            adjacency[left_id].add(right_id)
            adjacency[right_id].add(left_id)
            edge_reasons[tuple(sorted((left_id, right_id)))] = set(reasons)

    clusters: List[ReadingCluster] = []
    deferred_states: List[tuple[Dict[str, Any], str]] = []
    visited: set[int] = set()
    for state in sorted(states, key=lambda item: item["state_id"]):
        state_id = state["state_id"]
        if state_id in visited:
            continue

        component_ids = _connected_component_ids(state_id, adjacency)
        visited.update(component_ids)
        component_states = [state_by_id[item_id] for item_id in sorted(component_ids)]
        if len(component_states) == 1:
            decision = component_states[0]["reading_decision"]
            if decision.role in {READING_ROLE_STANDALONE, READING_ROLE_SUPPORTING}:
                clusters.append(
                    _reading_cluster_from_states(
                        document_id,
                        component_states,
                        merge_reasons=(f"single_{decision.role}_state",),
                    )
                )
            else:
                deferred_states.append(
                    (component_states[0], "supporting_state_without_cluster")
                )
            continue

        merge_reasons: set[str] = {"reading_cluster"}
        for left_id in component_ids:
            for right_id in adjacency[left_id] & component_ids:
                merge_reasons.update(edge_reasons.get(tuple(sorted((left_id, right_id))), set()))
        clusters.append(
            _reading_cluster_from_states(
                document_id,
                component_states,
                merge_reasons=tuple(sorted(merge_reasons)),
            )
        )

    return clusters, deferred_states


def _connected_component_ids(start_id: int, adjacency: Dict[int, set[int]]) -> set[int]:
    seen: set[int] = set()
    pending = [start_id]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        pending.extend(sorted(adjacency.get(current, set()) - seen))
    return seen


def _reading_cluster_from_states(
    document_id: int,
    states: List[Dict[str, Any]],
    merge_reasons: tuple[str, ...],
) -> ReadingCluster:
    """把已连通的一组 state 转成阅读簇诊断结构。"""
    ordered_states = sorted(
        states,
        key=lambda state: (
            min(item["chunk_index"] for item in state["evidence"]),
            state["state_id"],
        ),
    )
    primary_state_ids = tuple(
        state["state_id"]
        for state in ordered_states
        if state["reading_decision"].role == READING_ROLE_STANDALONE
    )
    if not primary_state_ids:
        primary_state_ids = (ordered_states[0]["state_id"],)
    supporting_state_ids = tuple(
        state["state_id"]
        for state in ordered_states
        if state["state_id"] not in primary_state_ids
    )
    subject_identities = tuple(
        sorted(
            {
                (state.get("subject_type"), state.get("subject_key"))
                for state in ordered_states
                if state.get("subject_type") or state.get("subject_key")
            }
        )
    )
    risk_flags: List[str] = []
    if len(subject_identities) > 1:
        risk_flags.append("multiple_subjects_same_reading_cluster")

    return ReadingCluster(
        cluster_id=f"doc-{document_id}-cluster-{min(state['state_id'] for state in ordered_states)}",
        title=_reading_cluster_title(ordered_states),
        state_ids=tuple(state["state_id"] for state in ordered_states),
        primary_state_ids=primary_state_ids,
        supporting_state_ids=supporting_state_ids,
        subject_identities=subject_identities,
        merge_reasons=merge_reasons,
        risk_flags=tuple(risk_flags),
    )


def _reading_cluster_title(states: List[Dict[str, Any]]) -> str:
    shared_sections = _shared_context_labels(states)
    for section in shared_sections:
        return section

    shared_anchors = _shared_reading_anchors(states)
    for anchor in sorted(shared_anchors, key=lambda item: (-len(item), item)):
        return _title_from_anchor(anchor)

    first_evidence = sorted(
        states[0]["evidence"],
        key=lambda item: (item["document_id"], item["chunk_index"]),
    )[0]
    return (
        first_evidence["document_title"]
        or first_evidence["section_label"]
        or Path(first_evidence["document_path"]).stem
    )


def _states_can_share_reading_cluster(
    left: Dict[str, Any],
    right: Dict[str, Any],
) -> tuple[bool, tuple[str, ...]]:
    """判断两条 state 是否可放进同一阅读簇，并返回中文可解释的依据键。"""
    reasons: set[str] = set()
    if _primary_document_id(left) != _primary_document_id(right):
        return False, ()

    shared_sections = _shared_context_labels([left, right])
    shared_anchors = _reading_anchors_for_state(left) & _reading_anchors_for_state(right)
    same_subject = _subject_identity(left) == _subject_identity(right) and _subject_identity(left) != (None, None)
    adjacent = _states_are_adjacent(left, right)
    distant_shared_anchor = bool(shared_anchors - _subject_anchor_values(left) - _subject_anchor_values(right))
    subject_object_connection = _has_subject_object_connection(left, right)

    if adjacent and (shared_sections or shared_anchors or same_subject):
        reasons.add("local_adjacent_chunks")
        if shared_sections:
            reasons.add("shared_section")
        if shared_anchors:
            reasons.add("shared_reading_anchor")
        if same_subject:
            reasons.add("shared_subject_identity")

    if not adjacent and distant_shared_anchor:
        for anchor in sorted(
            shared_anchors - _subject_anchor_values(left) - _subject_anchor_values(right)
        ):
            reasons.add(f"distant_strong_anchor:{anchor}")

    if subject_object_connection:
        reasons.add("subject_object_connection")

    return bool(reasons), tuple(sorted(reasons))


def _primary_document_id(state: Dict[str, Any]) -> Optional[int]:
    evidence = state.get("evidence") or []
    if not evidence:
        return None
    return sorted(evidence, key=lambda item: (item["document_id"], item["chunk_index"]))[0]["document_id"]


def _states_are_adjacent(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    left_indexes = {item["chunk_index"] for item in left.get("evidence", [])}
    right_indexes = {item["chunk_index"] for item in right.get("evidence", [])}
    return any(
        abs(left_index - right_index) <= NEIGHBOR_CHUNK_DISTANCE
        for left_index in left_indexes
        for right_index in right_indexes
    )


def _shared_context_labels(states: List[Dict[str, Any]]) -> List[str]:
    label_sets = [
        {
            _clean_context_label(label)
            for label in _state_section_labels(state)
            if _clean_context_label(label)
        }
        for state in states
    ]
    if not label_sets:
        return []
    shared = set.intersection(*label_sets)
    return sorted(shared)


def _shared_reading_anchors(states: List[Dict[str, Any]]) -> set[str]:
    anchor_sets = [_reading_anchors_for_state(state) for state in states]
    if not anchor_sets:
        return set()
    return set.intersection(*anchor_sets)


def _reading_anchors_for_state(state: Dict[str, Any]) -> set[str]:
    anchors = set(_strong_anchors_for_state(state))
    anchors.update(_state_object_anchors(state))
    subject_type, subject_key = _subject_identity(state)
    if subject_type and subject_key:
        anchors.add(f"subject:{subject_type}:{subject_key}".lower())
    return anchors


def _subject_identity(state: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    subject_type = state.get("subject_type")
    subject_key = state.get("subject_key")
    if not subject_type and not subject_key:
        return (None, None)
    return (subject_type, subject_key)


def _subject_anchor_values(state: Dict[str, Any]) -> set[str]:
    subject_type, subject_key = _subject_identity(state)
    if not subject_type or not subject_key:
        return set()
    return {f"subject:{subject_type}:{subject_key}".lower()}


def _has_subject_object_connection(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    left_subject = (left.get("subject_key") or "").strip().lower()
    right_subject = (right.get("subject_key") or "").strip().lower()
    left_anchors = _state_object_anchors(left)
    right_anchors = _state_object_anchors(right)
    return bool(
        (left_subject and left_subject in right_anchors)
        or (right_subject and right_subject in left_anchors)
    )


def _build_local_context_groups(states: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sorted_states = sorted(
        states,
        key=lambda state: (
            min(item["chunk_index"] for item in state["evidence"]),
            state["state_id"],
        ),
    )
    groups: List[Dict[str, Any]] = []
    current_group: List[Dict[str, Any]] = []
    current_max_chunk_index: Optional[int] = None
    current_sections: set[str] = set()
    current_basis: set[str] = set()

    for state in sorted_states:
        chunk_indexes = [item["chunk_index"] for item in state["evidence"]]
        section_labels = {
            item["section_label"]
            for item in state["evidence"]
            if item["section_label"]
        }
        min_chunk_index = min(chunk_indexes)
        is_adjacent = (
            current_max_chunk_index is not None
            and min_chunk_index - current_max_chunk_index <= 1
        )
        shares_section = bool(current_sections & section_labels)

        if current_group and not (is_adjacent or shares_section):
            groups.append({"states": current_group, "merge_basis": sorted(current_basis)})
            current_group = []
            current_max_chunk_index = None
            current_sections = set()
            current_basis = set()

        current_group.append(state)
        if is_adjacent:
            current_basis.add("local_adjacent_chunks")
        if shares_section:
            current_basis.add("shared_section")
        current_max_chunk_index = max(
            current_max_chunk_index or min_chunk_index,
            max(chunk_indexes),
        )
        current_sections.update(section_labels)

    if current_group:
        groups.append({"states": current_group, "merge_basis": sorted(current_basis)})

    return groups


def _merge_distant_strong_anchor_groups(
    groups: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged_groups: List[Dict[str, Any]] = []
    for group in groups:
        group_anchors = _strong_anchors_for_group(group["states"])
        merged_into_existing = False
        for existing in merged_groups:
            existing_anchors = _strong_anchors_for_group(existing["states"])
            shared_anchors = sorted(group_anchors & existing_anchors)
            if not shared_anchors:
                continue

            existing["states"].extend(group["states"])
            merge_basis = set(existing["merge_basis"])
            merge_basis.update(group["merge_basis"])
            merge_basis.update(
                f"distant_strong_anchor:{anchor}" for anchor in shared_anchors
            )
            existing["merge_basis"] = sorted(merge_basis)
            merged_into_existing = True
            break

        if not merged_into_existing:
            merged_groups.append(
                {
                    "states": list(group["states"]),
                    "merge_basis": list(group["merge_basis"]),
                }
            )

    return merged_groups


def _finalize_context_bundles(
    groups: List[Dict[str, Any]],
    document_chunks_by_id: Dict[int, List[Dict[str, Any]]],
    needs_context_items: List[ContextBundleState],
) -> List[ContextBundle]:
    bundles: List[ContextBundle] = []
    for group in groups:
        group_states = group["states"]
        reading_cluster = group.get("reading_cluster")
        context_chunk_ids, context_basis = _complete_context_chunk_ids(
            group_states,
            document_chunks_by_id,
        )
        if not _is_reliable_context_group(group_states, context_chunk_ids):
            needs_context_items.append(
                _context_state_from_row(group_states[0], "local_context_not_found")
            )
            continue

        first_evidence = sorted(
            group_states[0]["evidence"],
            key=lambda item: (item["document_id"], item["chunk_index"]),
        )[0]
        sections = sorted({
            item["section_label"]
            for state in group_states
            for item in state["evidence"]
            if item["section_label"]
        })
        state_ids = [state["state_id"] for state in group_states]
        merge_basis = sorted(set(group["merge_basis"]) | set(context_basis))
        subject_identities = (
            reading_cluster.subject_identities
            if isinstance(reading_cluster, ReadingCluster)
            else tuple(
                sorted(
                    {
                        (state.get("subject_type"), state.get("subject_key"))
                        for state in group_states
                        if state.get("subject_type") or state.get("subject_key")
                    }
                )
            )
        )
        primary_state_ids = (
            reading_cluster.primary_state_ids
            if isinstance(reading_cluster, ReadingCluster)
            else tuple(state_ids)
        )
        supporting_state_ids = (
            reading_cluster.supporting_state_ids
            if isinstance(reading_cluster, ReadingCluster)
            else ()
        )
        bundles.append(
            ContextBundle(
                title=(
                    reading_cluster.title
                    if isinstance(reading_cluster, ReadingCluster)
                    else first_evidence["document_title"]
                    or first_evidence["section_label"]
                    or Path(first_evidence["document_path"]).stem
                ),
                source_document=first_evidence["document_path"],
                subject_type=(
                    group_states[0]["subject_type"]
                    if len(subject_identities) <= 1
                    else None
                ),
                subject_key=(
                    group_states[0]["subject_key"]
                    if len(subject_identities) <= 1
                    else None
                ),
                state_ids=state_ids,
                evidence_chunk_ids=context_chunk_ids,
                sections=sections,
                merge_basis=merge_basis,
                items=[_context_state_from_row(state) for state in group_states],
                primary_state_ids=primary_state_ids,
                supporting_state_ids=supporting_state_ids,
                subject_identities=subject_identities,
                risk_flags=(
                    reading_cluster.risk_flags
                    if isinstance(reading_cluster, ReadingCluster)
                    else ()
                ),
                reading_cluster_id=(
                    reading_cluster.cluster_id
                    if isinstance(reading_cluster, ReadingCluster)
                    else None
                ),
            )
        )

    return bundles


def _complete_context_chunk_ids(
    states: List[Dict[str, Any]],
    document_chunks_by_id: Dict[int, List[Dict[str, Any]]],
) -> tuple[List[int], List[str]]:
    evidence = [
        item
        for state in states
        for item in state["evidence"]
    ]
    evidence_chunk_ids = {item["chunk_id"] for item in evidence}
    context_chunk_ids = set(evidence_chunk_ids)
    basis: set[str] = set()
    anchors = _strong_anchors_for_group(states)

    for item in evidence:
        for chunk in document_chunks_by_id.get(item["document_id"], []):
            if abs(chunk["chunk_index"] - item["chunk_index"]) <= NEIGHBOR_CHUNK_DISTANCE:
                if chunk["id"] not in context_chunk_ids:
                    basis.add("neighbor_chunk_context")
                context_chunk_ids.add(chunk["id"])

            if anchors and _chunk_matches_strong_anchor(chunk, anchors):
                if chunk["id"] not in context_chunk_ids:
                    basis.add("same_document_strong_anchor_context")
                context_chunk_ids.add(chunk["id"])

    return sorted(context_chunk_ids), sorted(basis)


def _is_reliable_context_group(
    states: List[Dict[str, Any]],
    context_chunk_ids: List[int],
) -> bool:
    if len(states) == 1:
        decision = states[0].get("reading_decision")
        if isinstance(decision, ReadingDecision) and decision.role == READING_ROLE_STANDALONE:
            return bool(context_chunk_ids)
    return len(states) >= 2 or len(context_chunk_ids) >= 2


def _strong_anchors_for_group(states: List[Dict[str, Any]]) -> set[str]:
    anchors: set[str] = set()
    for state in states:
        anchors.update(_strong_anchors_for_state(state))
    return anchors


def _strong_anchors_for_state(state: Dict[str, Any]) -> set[str]:
    anchors: set[str] = set()
    subject_type = state.get("subject_type")
    subject_key = state.get("subject_key")
    if subject_type and subject_key:
        anchors.add(f"subject:{subject_type}:{subject_key}".lower())

    text_parts = [
        state.get("canonical_summary") or "",
        state.get("summary") or "",
        state.get("detail") or "",
    ]
    text_parts.extend(
        item.get("chunk_text") or "" for item in state.get("evidence", [])
    )
    text = "\n".join(text_parts)

    anchors.update(match.group(0).lower() for match in ISSUE_ANCHOR_PATTERN.finditer(text))
    anchors.update(match.group(0).lower() for match in MODEL_ANCHOR_PATTERN.finditer(text))
    anchors.update(
        f"term:{match.group(1).strip().lower()}"
        for match in BACKTICK_ANCHOR_PATTERN.finditer(text)
        if match.group(1).strip()
    )
    return anchors


def _chunk_matches_strong_anchor(
    chunk: Dict[str, Any],
    anchors: set[str],
) -> bool:
    text = str(chunk.get("text") or "").lower()
    for anchor in anchors:
        if anchor.startswith("subject:"):
            continue
        if anchor.startswith("term:"):
            if anchor.removeprefix("term:") in text:
                return True
            continue
        if anchor in text:
            return True
    return False


def _build_context_bundle_diagnostics(
    bundles: List[ContextBundle],
    needs_context_items: List[ContextBundleState],
) -> Dict[str, Any]:
    needs_context_reasons: Dict[str, int] = {}
    for item in needs_context_items:
        reason = item.needs_context_reason or "unknown"
        needs_context_reasons[reason] = needs_context_reasons.get(reason, 0) + 1

    return {
        "bundle_count": len(bundles),
        "reading_cluster_count": len(bundles),
        "bundle_state_counts": [len(bundle.state_ids) for bundle in bundles],
        "bundle_merge_basis": [bundle.merge_basis for bundle in bundles],
        "reading_clusters": [
            {
                "cluster_id": bundle.reading_cluster_id,
                "title": bundle.title,
                "state_ids": list(bundle.state_ids),
                "primary_state_ids": list(bundle.primary_state_ids),
                "supporting_state_ids": list(bundle.supporting_state_ids),
                "subject_identities": [
                    list(identity) for identity in bundle.subject_identities
                ],
                "merge_reasons": list(bundle.merge_basis),
                "risk_flags": list(bundle.risk_flags),
            }
            for bundle in bundles
        ],
        "needs_context_count": len(needs_context_items),
        "needs_context_reasons": needs_context_reasons,
        "large_bundles": [
            {
                "title": bundle.title,
                "state_count": len(bundle.state_ids),
            }
            for bundle in bundles
            if len(bundle.state_ids) > LARGE_BUNDLE_STATE_COUNT
        ],
    }


def build_bundle_narratives(
    selection: ContextBundleSelection,
    profile: Optional[OutputProfile] = None,
    narrative_mode: Optional[str] = None,
    narrative_client: Optional[Any] = None,
) -> tuple[List[BundleNarrative], Dict[str, Any]]:
    """Build subject/topic narratives from context bundles.

    The narrative layer is read-only output projection. It never mutates state
    identity and falls back to deterministic rule output whenever LLM
    classification is unavailable or invalid.
    """
    start_time = perf_counter()
    profile = profile or get_output_profile()
    mode = _resolve_narrative_mode(narrative_mode)
    candidates = _candidate_topic_bundles_from_selection(selection)
    narratives: List[BundleNarrative] = []
    fallback_count = 0
    llm_success_count = 0
    llm_failure_count = 0
    weak_title_candidate_count = 0
    omitted_reason_counts: Dict[str, int] = {}
    candidate_diagnostics: List[Dict[str, Any]] = []

    for candidate in candidates:
        if not _clean_topic_title(candidate.topic_title_hint):
            weak_title_candidate_count += 1
        narrative: BundleNarrative
        used_fallback = False
        error_message: Optional[str] = None
        if mode == "rule":
            narrative = _build_rule_bundle_narrative(candidate)
            used_fallback = True
        else:
            try:
                narrative = _build_llm_bundle_narrative(candidate, narrative_client)
                llm_success_count += 1
            except Exception as exc:
                llm_failure_count += 1
                fallback_count += 1
                used_fallback = True
                error_message = f"{type(exc).__name__}: {exc}"
                log_event(
                    logger,
                    logging.WARNING,
                    "bundle_narrative_llm_fallback",
                    "Falling back to rule narrative after LLM narrative failure",
                    stage="output",
                    topic_key=candidate.topic_key,
                    subject_label=candidate.subject_label,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                narrative = _build_rule_bundle_narrative(candidate)

        for omitted in narrative.omitted_state_ids:
            omitted_reason_counts[omitted.reason] = (
                omitted_reason_counts.get(omitted.reason, 0) + 1
            )

        if narrative.sections:
            narratives.append(narrative)
        candidate_diagnostics.append(
            {
                "topic_key": candidate.topic_key,
                "state_count": len(candidate.state_ids),
                "section_count": len(narrative.sections),
                "used_fallback": used_fallback,
                "error": error_message,
            }
        )

    diagnostics = {
        "mode": mode,
        "profile": profile.name,
        "candidate_topic_bundle_count": len(candidates),
        "narrative_count": len(narratives),
        "narrative_section_count": sum(len(item.sections) for item in narratives),
        "weak_title_candidate_count": weak_title_candidate_count,
        "omitted_reason_counts": omitted_reason_counts,
        "llm_success_count": llm_success_count,
        "llm_failure_count": llm_failure_count,
        "fallback_count": fallback_count,
        "candidate_diagnostics": candidate_diagnostics,
        "duration_ms": (perf_counter() - start_time) * 1000,
    }
    log_event(
        logger,
        logging.INFO,
        "bundle_narratives_built",
        "Built bundle narratives for output",
        stage="output",
        narrative_mode=mode,
        candidate_topic_bundle_count=len(candidates),
        narrative_count=len(narratives),
        fallback_count=fallback_count,
        duration_ms=diagnostics["duration_ms"],
    )
    return narratives, diagnostics


def _resolve_narrative_mode(narrative_mode: Optional[str]) -> str:
    mode = (narrative_mode or os.getenv(NARRATIVE_MODE_ENV, DEFAULT_NARRATIVE_MODE)).strip().lower()
    if mode not in VALID_NARRATIVE_MODES:
        raise ValueError(f"Unknown output narrative mode: {mode}")
    return mode


def _candidate_topic_bundles_from_selection(
    selection: ContextBundleSelection,
) -> List[CandidateTopicBundle]:
    groups: Dict[tuple[str, str, str], Dict[str, Any]] = {}

    for bundle in selection.bundles:
        subject_label = _subject_label_for_bundle(bundle)
        for item in bundle.items:
            if bundle.supporting_state_ids or len(bundle.subject_identities) > 1:
                topic_key = f"cluster:{bundle.reading_cluster_id or bundle.title.lower()}"
                topic_title_hint = bundle.title
                basis = "topic_reading_cluster"
            else:
                topic_key, topic_title_hint, basis = _topic_key_for_item(item, bundle)
            group_key = (subject_label, bundle.source_document, topic_key)
            group = groups.setdefault(
                group_key,
                {
                    "subject_type": bundle.subject_type,
                    "subject_key": bundle.subject_key,
                    "subject_label": subject_label,
                    "source_document": bundle.source_document,
                    "topic_key": topic_key,
                    "topic_title_hint": topic_title_hint,
                    "evidence_items": [],
                    "sections": set(),
                    "merge_basis": set(bundle.merge_basis),
                },
            )
            group["merge_basis"].add(basis)
            group["sections"].update(item.sections)
            group["evidence_items"].append(
                NarrativeEvidenceItem(
                    state_id=item.state_id,
                    subtype=item.subtype,
                    summary=item.summary,
                    detail=item.detail,
                    sections=item.sections,
                    evidence_excerpt=item.evidence_excerpt,
                    source_chunk_ids=item.source_chunk_ids,
                    strong_anchors=item.strong_anchors,
                    reading_role=item.reading_role,
                    reading_reason=item.reading_reason,
                )
            )

    candidates: List[CandidateTopicBundle] = []
    for group in groups.values():
        evidence_items = tuple(
            sorted(group["evidence_items"], key=lambda item: item.state_id)
        )
        candidates.append(
            CandidateTopicBundle(
                subject_type=group["subject_type"],
                subject_key=group["subject_key"],
                subject_label=group["subject_label"],
                source_document=group["source_document"],
                topic_key=group["topic_key"],
                topic_title_hint=group["topic_title_hint"],
                state_ids=tuple(item.state_id for item in evidence_items),
                evidence_items=evidence_items,
                sections=tuple(sorted(group["sections"])),
                merge_basis=tuple(sorted(group["merge_basis"])),
            )
        )

    candidates.sort(
        key=lambda item: (
            item.subject_label,
            item.source_document,
            item.topic_title_hint,
            item.state_ids,
        )
    )
    return candidates


def _subject_label_for_bundle(bundle: ContextBundle) -> str:
    if len(bundle.subject_identities) > 1:
        return bundle.title or Path(bundle.source_document).stem
    if bundle.subject_key:
        return bundle.subject_key
    if bundle.subject_type:
        return bundle.subject_type
    return bundle.title or Path(bundle.source_document).stem


def _topic_key_for_item(
    item: ContextBundleState,
    bundle: ContextBundle,
) -> tuple[str, str, str]:
    anchors = [
        anchor
        for anchor in item.strong_anchors
        if not anchor.startswith("subject:")
    ]
    if anchors:
        anchor = sorted(anchors)[0]
        return f"anchor:{anchor}", _title_from_anchor(anchor), f"topic_anchor:{anchor}"

    if item.sections:
        section = item.sections[0].strip()
        if section:
            return f"section:{section.lower()}", section, "topic_section"

    phrase = _topic_phrase_from_text(
        " ".join(part for part in [item.summary, item.detail or ""] if part)
    )
    if phrase:
        return f"text:{phrase.lower()}", phrase, "topic_text"

    return (
        f"bundle:{bundle.title.lower()}",
        bundle.title or Path(bundle.source_document).stem,
        "topic_bundle_fallback",
    )


def _title_from_anchor(anchor: str) -> str:
    if anchor.startswith("term:"):
        return anchor.removeprefix("term:").strip()
    return anchor.strip()


def _topic_phrase_from_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip(" .。；;：:")
    if not cleaned:
        return ""
    if len(cleaned) <= 24:
        return cleaned
    return cleaned[:24].rstrip(" ，,。；;：:")


def _build_rule_bundle_narrative(candidate: CandidateTopicBundle) -> BundleNarrative:
    sections: List[NarrativeSectionItem] = []
    omitted: List[OmittedNarrativeState] = []
    absorbed_state_ids: List[int] = []
    topic_title = _rule_topic_title(candidate)

    for item in candidate.evidence_items:
        text = _fact_sentence_for_item(item)
        if not text:
            omitted.append(OmittedNarrativeState(item.state_id, "too_vague"))
            continue

        sections.append(
            NarrativeSectionItem(
                kind=_narrative_kind_for_item(item),
                text=text,
                source_state_ids=(item.state_id,),
            )
        )
        absorbed_state_ids.append(item.state_id)

    return BundleNarrative(
        subject_type=candidate.subject_type,
        subject_key=candidate.subject_key,
        subject_label=candidate.subject_label,
        source_document=candidate.source_document,
        topic_key=candidate.topic_key,
        topic_title=topic_title,
        bundle_summary=_rule_bundle_summary(candidate, sections, topic_title),
        sections=tuple(sections),
        absorbed_state_ids=tuple(absorbed_state_ids),
        omitted_state_ids=tuple(omitted),
        diagnostics={
            "mode": "rule",
            "merge_basis": list(candidate.merge_basis),
            "source_state_count": len(candidate.state_ids),
        },
    )


def _rule_topic_title(candidate: CandidateTopicBundle) -> str:
    candidates = [
        candidate.topic_title_hint,
        *candidate.sections,
        *_title_hints_from_evidence(candidate.evidence_items),
        Path(candidate.source_document).stem,
        candidate.subject_label,
    ]
    for title in candidates:
        cleaned = _clean_topic_title(title)
        if cleaned:
            return cleaned
    return "未命名主题"


def _title_hints_from_evidence(
    evidence_items: tuple[NarrativeEvidenceItem, ...],
) -> List[str]:
    hints: List[str] = []
    for item in evidence_items:
        for anchor in item.strong_anchors:
            if anchor.startswith("subject:"):
                continue
            hints.append(_title_from_anchor(anchor))
        if item.detail:
            hints.append(_topic_phrase_from_text(item.detail))
        if item.evidence_excerpt:
            hints.append(_topic_phrase_from_text(item.evidence_excerpt))
    return hints


def _clean_topic_title(value: Optional[str]) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" #*`-_")
    text = text.strip()
    text = re.sub(r"^[：:]+|[：:]+$", "", text).strip()
    if not text:
        return ""
    if text in WEAK_TOPIC_TITLES:
        return ""
    if len(text) <= 1:
        return ""
    return _shorten_text(text, 48)


def _rule_bundle_summary(
    candidate: CandidateTopicBundle,
    sections: List[NarrativeSectionItem],
    topic_title: str,
) -> str:
    if not sections:
        return ""

    kinds = {item.kind for item in sections}
    signals = []
    if "problem" in kinds:
        signals.append("问题")
    if "next_step" in kinds:
        signals.append("下一步")
    if "progress" in kinds:
        signals.append("进展")
    if not signals:
        signals.append("背景线索")

    state_count = len(set(candidate.state_ids))
    signal_text = "、".join(signals)
    return (
        f"这是围绕{topic_title}的上下文，汇集了 {state_count} 条可追溯线索，"
        f"用于呈现当前的{signal_text}。"
    )


def _narrative_kind_for_item(item: NarrativeEvidenceItem) -> str:
    searchable_text = " ".join(
        part for part in [item.summary, item.detail or ""] if part
    ).lower()
    if any(hint in searchable_text for hint in PROBLEM_HINTS):
        return "problem"
    if item.subtype == "pending_task":
        return "next_step"
    if item.subtype in {"ongoing_project", "recent_event"}:
        return "progress"
    return "related_context"


def _fact_sentence_for_item(item: NarrativeEvidenceItem) -> str:
    summary = (item.summary or "").strip()
    detail = (item.detail or "").strip()
    evidence = (item.evidence_excerpt or "").strip()

    if detail and not _is_weak_child_text(detail):
        text = detail
    elif evidence and not _is_weak_child_text(evidence):
        text = evidence
    elif summary and not _is_weak_child_text(summary):
        text = summary
    else:
        text = ""

    return _ensure_sentence(_shorten_text(text, 220))


def _is_weak_child_text(text: str) -> bool:
    stripped = re.sub(r"\s+", "", text)
    if not stripped:
        return True
    if stripped in WEAK_TOPIC_TITLES:
        return True
    return False


def _texts_are_redundant(left: str, right: str) -> bool:
    left_normalized = re.sub(r"\s+", "", left).lower()
    right_normalized = re.sub(r"\s+", "", right).lower()
    return (
        bool(left_normalized)
        and bool(right_normalized)
        and (left_normalized in right_normalized or right_normalized in left_normalized)
    )


def _ensure_sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    if text[-1] in "。.!！？?":
        return text
    return f"{text}。"


def _shorten_text(text: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "…"


def _build_llm_bundle_narrative(
    candidate: CandidateTopicBundle,
    narrative_client: Optional[Any] = None,
) -> BundleNarrative:
    payload = _candidate_topic_bundle_payload(candidate)
    raw_result: Any
    if narrative_client is not None and hasattr(narrative_client, "create_narrative"):
        raw_result = narrative_client.create_narrative(payload)
    else:
        raw_result = _call_narrative_llm(payload, narrative_client)

    if isinstance(raw_result, str):
        parsed_result = json.loads(raw_result)
    else:
        parsed_result = raw_result
    return _bundle_narrative_from_llm_result(candidate, parsed_result)


def _candidate_topic_bundle_payload(candidate: CandidateTopicBundle) -> Dict[str, Any]:
    return {
        "subject": {
            "type": candidate.subject_type,
            "key": candidate.subject_key,
            "label": candidate.subject_label,
        },
        "source_document": candidate.source_document,
        "topic_key": candidate.topic_key,
        "topic_title_hint": candidate.topic_title_hint,
        "merge_basis": list(candidate.merge_basis),
        "evidence_items": [
            {
                "state_id": item.state_id,
                "subtype": item.subtype,
                "summary": item.summary,
                "detail": item.detail,
                "sections": list(item.sections),
                "chunk_excerpt": item.evidence_excerpt,
                "source_chunk_ids": list(item.source_chunk_ids),
            }
            for item in candidate.evidence_items
        ],
    }


def _call_narrative_llm(
    payload: Dict[str, Any],
    narrative_client: Optional[Any] = None,
) -> Dict[str, Any]:
    if narrative_client is not None and hasattr(narrative_client, "chat"):
        client = narrative_client
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
        timeout = 30
        extra_body = None
    else:
        from layers.extractors.config import ExtractorConfig
        from openai import OpenAI

        config = ExtractorConfig()
        config.validate()
        client = OpenAI(api_key=config.api_key, base_url=config.base_url) if config.base_url else OpenAI(api_key=config.api_key)
        model = config.model
        temperature = config.temperature
        timeout = config.timeout
        extra_body = config.extra_body

    request_params: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": _narrative_system_prompt()},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, indent=2),
            },
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "timeout": timeout,
    }
    if extra_body:
        request_params["extra_body"] = extra_body

    response = client.chat.completions.create(**request_params)
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def _narrative_system_prompt() -> str:
    return (
        "You organize verified state evidence into a concise Chinese status report. "
        "Use only the provided evidence. Return strict JSON with keys: "
        "topic_title, bundle_summary, sections, absorbed_state_ids, omitted_state_ids. "
        "Each section item must have kind, text, and source_state_ids. Valid kinds are "
        "current_goal, progress, problem, next_step, related_context. Do not invent "
        "facts or cite state ids that are not present in the input."
    )


def _bundle_narrative_from_llm_result(
    candidate: CandidateTopicBundle,
    result: Dict[str, Any],
) -> BundleNarrative:
    if not isinstance(result, dict):
        raise ValueError("LLM narrative result must be a JSON object")

    topic_title = _clean_topic_title(str(result.get("topic_title") or "").strip())
    bundle_summary = str(result.get("bundle_summary") or "").strip()
    if not topic_title or not bundle_summary:
        raise ValueError("LLM narrative requires topic_title and bundle_summary")
    if any(phrase in bundle_summary for phrase in FORBIDDEN_SUMMARY_PHRASES):
        raise ValueError("LLM narrative summary used item-list phrasing")

    allowed_state_ids = set(candidate.state_ids)
    sections_raw = result.get("sections")
    if not isinstance(sections_raw, list):
        raise ValueError("LLM narrative sections must be a list")

    sections: List[NarrativeSectionItem] = []
    for item in sections_raw:
        if not isinstance(item, dict):
            raise ValueError("LLM narrative section item must be an object")
        kind = str(item.get("kind") or "").strip()
        text = str(item.get("text") or "").strip()
        source_state_ids_raw = item.get("source_state_ids")
        if kind not in NARRATIVE_SECTION_TITLES:
            raise ValueError(f"Invalid narrative section kind: {kind}")
        if not text:
            raise ValueError("Narrative section text cannot be blank")
        if not isinstance(source_state_ids_raw, list) or not source_state_ids_raw:
            raise ValueError("Narrative section requires source_state_ids")
        source_state_ids = tuple(int(state_id) for state_id in source_state_ids_raw)
        if not set(source_state_ids).issubset(allowed_state_ids):
            raise ValueError("Narrative section referenced unknown state ids")
        sections.append(
            NarrativeSectionItem(
                kind=kind,
                text=_ensure_sentence(text),
                source_state_ids=source_state_ids,
            )
        )

    if not sections:
        raise ValueError("LLM narrative must contain at least one section item")

    absorbed_raw = result.get("absorbed_state_ids")
    if not isinstance(absorbed_raw, list):
        raise ValueError("LLM narrative requires absorbed_state_ids")
    absorbed_state_ids = tuple(int(state_id) for state_id in absorbed_raw)
    if not set(absorbed_state_ids).issubset(allowed_state_ids):
        raise ValueError("LLM narrative absorbed unknown state ids")

    omitted_states: List[OmittedNarrativeState] = []
    omitted_raw = result.get("omitted_state_ids", [])
    if not isinstance(omitted_raw, list):
        raise ValueError("LLM narrative omitted_state_ids must be a list")
    for item in omitted_raw:
        if not isinstance(item, dict):
            raise ValueError("LLM narrative omitted item must be an object")
        state_id = int(item.get("state_id"))
        if state_id not in allowed_state_ids:
            raise ValueError("LLM narrative omitted unknown state ids")
        reason = str(item.get("reason") or "unspecified").strip()
        omitted_states.append(OmittedNarrativeState(state_id, reason))

    return BundleNarrative(
        subject_type=candidate.subject_type,
        subject_key=candidate.subject_key,
        subject_label=candidate.subject_label,
        source_document=candidate.source_document,
        topic_key=candidate.topic_key,
        topic_title=topic_title,
        bundle_summary=_ensure_sentence(bundle_summary),
        sections=tuple(sections),
        absorbed_state_ids=absorbed_state_ids,
        omitted_state_ids=tuple(omitted_states),
        diagnostics={
            "mode": "llm",
            "merge_basis": list(candidate.merge_basis),
            "source_state_count": len(candidate.state_ids),
        },
    )


def select_states_for_output(profile: Optional[OutputProfile] = None) -> Dict[str, Any]:
    """从中间层选择要输出的状态项
    
    这里实现"按需选取"逻辑，不是把整个中间层塞给输出
    """
    start_time = perf_counter()
    conn = get_connection()
    cursor = conn.cursor()
    
    result = {}
    profile = profile or get_output_profile()
    
    for category, config in profile.config.items():
        result[category] = {}
        
        for subtype, subtype_label in config['subtypes'].items():
            max_items = config['max_items_per_subtype']
            
            # 按 last_updated 倒序取，保证最新的在前
            cursor.execute("""
                SELECT id,
                       COALESCE(display_summary, summary) AS summary,
                       detail,
                       confidence,
                       first_seen,
                       last_updated
                FROM states
                WHERE category = ? AND subtype = ? AND status = 'active'
                ORDER BY last_updated DESC
                LIMIT ?
            """, (category, subtype, max_items))
            
            items = [dict(row) for row in cursor.fetchall()]
            if items:
                result[category][subtype] = {
                    'label': subtype_label,
                    'items': items
                }
    
    total_items = sum(
        len(subtype_data['items'])
        for category_data in result.values()
        for subtype_data in category_data.values()
    )
    log_event(
        logger,
        logging.INFO,
        "states_selected_for_output",
        "Selected states for output generation",
        stage="output",
        total_items=total_items,
        duration_ms=(perf_counter() - start_time) * 1000,
    )
    return result


def format_julian_date(julian_day: Optional[float]) -> str:
    """将 SQLite 的 Julian Day 转换为可读日期"""
    if julian_day is None:
        return "未知"
    # Julian Day 2440587.5 = Unix epoch (1970-01-01)
    import datetime as dt
    try:
        unix_ts = (julian_day - 2440587.5) * 86400
        return dt.datetime.fromtimestamp(unix_ts).strftime('%Y-%m-%d')
    except:
        return "未知"


def generate_status_document(
    selected_states: Dict[str, Any],
    profile: Optional[OutputProfile] = None,
) -> str:
    """生成状态文档 Markdown"""
    lines = []
    profile = profile or get_output_profile()
    
    # 头部
    lines.append("# 状态文档")
    lines.append("")
    lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # 按大类输出
    for category, config in profile.config.items():
        category_data = selected_states.get(category, {})
        
        lines.append(f"## {config['title']}")
        lines.append("")
        lines.append(f"*{config['description']}*")
        lines.append("")
        
        if not category_data:
            lines.append("*暂无数据*")
            lines.append("")
            continue
        
        for subtype, subtype_data in category_data.items():
            label = subtype_data['label']
            items = subtype_data['items']
            
            lines.append(f"### {label}")
            lines.append("")
            
            for item in items:
                summary = item['summary']
                detail = item.get('detail', '')
                confidence = item.get('confidence', 1.0)
                last_updated = format_julian_date(item.get('last_updated'))
                
                # 主要信息
                lines.append(f"- **{summary}**")
                
                # 详情（如果有）
                if detail:
                    lines.append(f"  - {detail}")
                
                # 元信息
                meta_parts = []
                if confidence < 1.0:
                    meta_parts.append(f"置信度: {confidence:.0%}")
                meta_parts.append(f"更新: {last_updated}")
                
                if meta_parts:
                    lines.append(f"  - *{' | '.join(meta_parts)}*")
                
                lines.append("")
        
        lines.append("---")
        lines.append("")
    
    # 归档区提示
    lines.append("## 归档区")
    lines.append("")
    lines.append("*已归档的历史状态可通过数据库查询获取*")
    lines.append("")
    
    return '\n'.join(lines)


def generate_contextual_status_document(
    selection: ContextBundleSelection,
    profile: Optional[OutputProfile] = None,
    narrative_mode: Optional[str] = None,
    narrative_client: Optional[Any] = None,
    narratives: Optional[List[BundleNarrative]] = None,
) -> str:
    """生成以主体 / 主题 narrative 为主阅读单位的状态文档。"""
    lines = []
    profile = profile or get_output_profile()
    if narratives is None:
        narratives, _diagnostics = build_bundle_narratives(
            selection,
            profile=profile,
            narrative_mode=narrative_mode,
            narrative_client=narrative_client,
        )

    lines.append("# 状态文档")
    lines.append("")
    lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 输出 profile: {profile.name}")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 上下文报告")
    lines.append("")
    if not narratives:
        lines.append("*暂无可靠上下文*")
        lines.append("")
    else:
        for subject_label, subject_narratives in _narratives_by_subject(narratives):
            lines.extend(_render_subject_narratives(subject_label, subject_narratives))

    lines.append("## 归档区")
    lines.append("")
    lines.append("*已归档的历史状态可通过数据库查询获取*")
    lines.append("")

    return "\n".join(lines)


def _narratives_by_subject(
    narratives: List[BundleNarrative],
) -> List[tuple[str, List[BundleNarrative]]]:
    grouped: Dict[str, List[BundleNarrative]] = {}
    for narrative in sorted(
        narratives,
        key=lambda item: (item.subject_label, item.source_document, item.topic_title),
    ):
        grouped.setdefault(narrative.subject_label, []).append(narrative)
    return list(grouped.items())


def _render_subject_narratives(
    subject_label: str,
    narratives: List[BundleNarrative],
) -> List[str]:
    lines = [f"### {subject_label}", ""]
    subject_meta = _subject_meta_for_narratives(narratives)
    if subject_meta:
        lines.append(f"*{subject_meta}*")
        lines.append("")

    for narrative in narratives:
        lines.extend(_render_bundle_narrative(narrative))
    return lines


def _subject_meta_for_narratives(narratives: List[BundleNarrative]) -> str:
    if not narratives:
        return ""
    first = narratives[0]
    meta_parts = []
    if first.subject_type and first.subject_key:
        meta_parts.append(f"主体: {first.subject_type}/{first.subject_key}")
    sources = sorted({item.source_document for item in narratives if item.source_document})
    if sources:
        meta_parts.append(f"来源: {', '.join(sources)}")
    return " | ".join(meta_parts)


def _render_bundle_narrative(narrative: BundleNarrative) -> List[str]:
    lines = [f"#### {narrative.topic_title}", ""]
    lines.append(narrative.bundle_summary)
    lines.append("")

    items_by_kind: Dict[str, List[NarrativeSectionItem]] = {
        kind: [] for kind in NARRATIVE_SECTION_ORDER
    }
    for item in narrative.sections:
        items_by_kind.setdefault(item.kind, []).append(item)

    for kind in NARRATIVE_SECTION_ORDER:
        for item in items_by_kind.get(kind) or []:
            lines.append(f"- {item.text}")

    if narrative.sections:
        lines.append("")

    return lines


def save_output(content: str, output_path: Path = OUTPUT_FILE) -> int:
    """保存输出文档并记录快照"""
    start_time = perf_counter()
    # 写入文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding='utf-8')
    
    # 记录快照
    conn = get_connection()
    cursor = conn.cursor()
    
    # 获取当前状态版本（简单用 states 表的最大 id）
    cursor.execute("SELECT MAX(id) FROM states")
    state_version = cursor.fetchone()[0] or 0
    
    cursor.execute("""
        INSERT INTO output_snapshots (content_md, source_state_version)
        VALUES (?, ?)
    """, (content, state_version))
    
    snapshot_id = cursor.lastrowid
    conn.commit()
    log_event(
        logger,
        logging.INFO,
        "output_saved",
        "Saved output document and snapshot",
        stage="output",
        output_path=output_path,
        snapshot_id=snapshot_id,
        total_items=content.count("\n- "),
        duration_ms=(perf_counter() - start_time) * 1000,
    )
    
    return snapshot_id


def generate_output(
    profile_name: str = DEFAULT_PROFILE_NAME,
    output_path: Optional[Path] = None,
    narrative_mode: Optional[str] = None,
    narrative_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """输出层主流程：选择 → 生成 → 保存
    
    Returns:
        处理结果信息
    """
    stage_start = perf_counter()
    profile = get_output_profile(profile_name)
    # 1. 从中间层选择上下文 bundle
    selected = select_context_bundles_for_output(profile)
    narratives, narrative_diagnostics = build_bundle_narratives(
        selected,
        profile=profile,
        narrative_mode=narrative_mode,
        narrative_client=narrative_client,
    )
    
    # 2. 生成文档
    content = generate_contextual_status_document(
        selected,
        profile,
        narrative_mode=narrative_mode,
        narrative_client=narrative_client,
        narratives=narratives,
    )
    
    # 3. 保存
    selected_output_path = output_path or profile.output_path
    snapshot_id = save_output(content, selected_output_path)
    
    # 统计
    total_items = sum(len(narrative.sections) for narrative in narratives)
    
    result = {
        'profile': profile.name,
        'snapshot_id': snapshot_id,
        'output_path': str(selected_output_path),
        'bundle_count': len(selected.bundles),
        'topic_bundle_count': len(narratives),
        'narrative_mode': narrative_diagnostics["mode"],
        'needs_context_items': len(selected.needs_context_items),
        'diagnostics': {
            **selected.diagnostics,
            "narrative": narrative_diagnostics,
        },
        'total_items': total_items,
        'content_length': len(content)
    }
    log_event(
        logger,
        logging.INFO,
        "output_generation_done",
        "Completed output generation",
        stage="output",
        snapshot_id=snapshot_id,
        output_path=selected_output_path,
        bundle_count=len(selected.bundles),
        topic_bundle_count=len(narratives),
        narrative_mode=narrative_diagnostics["mode"],
        needs_context_items=len(selected.needs_context_items),
        total_items=total_items,
        duration_ms=(perf_counter() - stage_start) * 1000,
    )
    return result
