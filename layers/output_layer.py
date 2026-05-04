"""
输出层：状态文档生成
"""
import json
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


@dataclass(frozen=True)
class OutputProfile:
    name: str
    config: Dict[str, Dict[str, Any]]
    output_path: Path


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


@dataclass(frozen=True)
class ContextBundleSelection:
    bundles: List[ContextBundle]
    needs_context_items: List[ContextBundleState]
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
               c.document_id,
               c.chunk_index,
               c.section_label,
               c.text AS chunk_text,
               d.path AS document_path,
               d.title AS document_title
        FROM states s
        LEFT JOIN state_evidence se ON se.state_id = s.id
        LEFT JOIN chunks c ON se.chunk_id = c.id
        LEFT JOIN documents d ON c.document_id = d.id
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
                    "document_id": row["document_id"],
                    "chunk_index": row["chunk_index"],
                    "section_label": row["section_label"],
                    "chunk_text": row["chunk_text"],
                    "document_path": row["document_path"],
                    "document_title": row["document_title"],
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
    bundle_groups: Dict[tuple[Any, ...], List[Dict[str, Any]]] = {}

    for state in states_by_id.values():
        evidence = state["evidence"]
        if not evidence:
            needs_context_items.append(
                _context_state_from_row(state, "missing_evidence")
            )
            continue

        primary_evidence = sorted(
            evidence,
            key=lambda item: (item["document_id"], item["chunk_index"]),
        )[0]
        group_key = (
            primary_evidence["document_id"],
            state["subject_type"] or "",
            state["subject_key"] or "",
        )
        bundle_groups.setdefault(group_key, []).append(state)

    candidate_groups: List[Dict[str, Any]] = []
    for group_states in bundle_groups.values():
        local_groups = _build_local_context_groups(group_states)
        candidate_groups.extend(_merge_distant_strong_anchor_groups(local_groups))

    bundles = _finalize_context_bundles(
        candidate_groups,
        document_chunks_by_id,
        needs_context_items,
    )
    bundles.sort(key=lambda bundle: (bundle.source_document, bundle.state_ids))
    diagnostics = _build_context_bundle_diagnostics(bundles, needs_context_items)
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


def _context_state_from_row(
    row: Dict[str, Any],
    needs_context_reason: Optional[str] = None,
) -> ContextBundleState:
    return ContextBundleState(
        state_id=row["state_id"],
        category=row["category"],
        subtype=row["subtype"],
        summary=row["summary"],
        detail=row["detail"],
        confidence=row["confidence"],
        last_updated=row["last_updated"],
        needs_context_reason=needs_context_reason,
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
        bundles.append(
            ContextBundle(
                title=first_evidence["document_title"]
                or first_evidence["section_label"]
                or Path(first_evidence["document_path"]).stem,
                source_document=first_evidence["document_path"],
                subject_type=group_states[0]["subject_type"],
                subject_key=group_states[0]["subject_key"],
                state_ids=state_ids,
                evidence_chunk_ids=context_chunk_ids,
                sections=sections,
                merge_basis=merge_basis,
                items=[_context_state_from_row(state) for state in group_states],
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
        "bundle_state_counts": [len(bundle.state_ids) for bundle in bundles],
        "bundle_merge_basis": [bundle.merge_basis for bundle in bundles],
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
) -> str:
    """生成以 ContextBundle 为主阅读单位的状态文档。"""
    lines = []
    profile = profile or get_output_profile()

    lines.append("# 状态文档")
    lines.append("")
    lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 输出 profile: {profile.name}")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 上下文报告")
    lines.append("")
    if not selection.bundles:
        lines.append("*暂无可靠上下文*")
        lines.append("")
    else:
        for bundle in selection.bundles:
            lines.extend(_render_context_bundle(bundle))

    lines.append("## 归档区")
    lines.append("")
    lines.append("*已归档的历史状态可通过数据库查询获取*")
    lines.append("")

    return "\n".join(lines)


def _render_context_bundle(bundle: ContextBundle) -> List[str]:
    lines = [f"### {bundle.title}", ""]
    meta_parts = [f"来源: {bundle.source_document}"]
    if bundle.subject_type and bundle.subject_key:
        meta_parts.append(f"主体: {bundle.subject_type}/{bundle.subject_key}")
    if bundle.sections:
        meta_parts.append(f"章节: {', '.join(bundle.sections)}")
    lines.append(f"*{' | '.join(meta_parts)}*")
    lines.append("")

    items_by_section: Dict[str, List[ContextBundleState]] = {
        title: [] for title in CONTEXT_SECTION_TITLES
    }
    for item in bundle.items:
        items_by_section[_section_for_context_item(item)].append(item)

    for title in CONTEXT_SECTION_TITLES:
        items = items_by_section[title]
        if not items:
            continue
        lines.append(f"#### {title}")
        lines.append("")
        for item in items:
            lines.extend(_render_context_item(item))

    return lines


def _section_for_context_item(item: ContextBundleState) -> str:
    searchable_text = " ".join(
        part for part in [item.summary, item.detail or ""] if part
    ).lower()
    if any(hint in searchable_text for hint in PROBLEM_HINTS):
        return "问题"
    return CONTEXT_SECTION_BY_SUBTYPE.get(item.subtype, "相关线索")


def _render_context_item(item: ContextBundleState) -> List[str]:
    lines = [f"- **{item.summary}**"]
    if item.detail:
        lines.append(f"  - {item.detail}")

    meta_parts = []
    if item.confidence < 1.0:
        meta_parts.append(f"置信度: {item.confidence:.0%}")
    meta_parts.append(f"更新: {format_julian_date(item.last_updated)}")
    lines.append(f"  - *{' | '.join(meta_parts)}*")
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
        total_items=content.count("\n- **"),
        duration_ms=(perf_counter() - start_time) * 1000,
    )
    
    return snapshot_id


def generate_output(
    profile_name: str = DEFAULT_PROFILE_NAME,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """输出层主流程：选择 → 生成 → 保存
    
    Returns:
        处理结果信息
    """
    stage_start = perf_counter()
    profile = get_output_profile(profile_name)
    # 1. 从中间层选择上下文 bundle
    selected = select_context_bundles_for_output(profile)
    
    # 2. 生成文档
    content = generate_contextual_status_document(selected, profile)
    
    # 3. 保存
    selected_output_path = output_path or profile.output_path
    snapshot_id = save_output(content, selected_output_path)
    
    # 统计
    total_items = sum(len(bundle.items) for bundle in selected.bundles)
    
    result = {
        'profile': profile.name,
        'snapshot_id': snapshot_id,
        'output_path': str(selected_output_path),
        'bundle_count': len(selected.bundles),
        'needs_context_items': len(selected.needs_context_items),
        'diagnostics': selected.diagnostics,
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
        needs_context_items=len(selected.needs_context_items),
        total_items=total_items,
        duration_ms=(perf_counter() - stage_start) * 1000,
    )
    return result
