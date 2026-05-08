"""Read-only grounding audit: how each state_candidate is supported by Observation IR.

This script inspects persisted extraction JSON, chunk text, source_context_blocks,
and state_candidate_supports rows. It does not modify the database, call an LLM,
or import project pipeline modules.

Audit dimensions (per candidate):
  subject grounding  – where does subject_type / subject_key come from?
  text grounding     – can summary / detail be traced to chunk text?
  event grounding    – do events support the action, participants, and time?
  relation grounding – do relation_candidates explain the subject-object link?
  retrieval grounding – does the candidate depend on unresolved surface forms?
  context grounding  – does the candidate lean on context / context_only blocks?
  overall grounding  – strong / medium / weak / risky / inconsistent

Also cross-checks against current state_candidate_supports admission decisions.

This is an audit hint, not validation. It does not change pipeline semantics.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_DB = Path("data/state.db")

# ── lightweight text helpers ────────────────────────────────────────────────

_ASIAN_PUNCT = re.compile(r"[　-〿＀-￯]")
_RE_CJK = re.compile(r"[一-鿿㐀-䶿]")
_RE_ASCII_WORD = re.compile(r"[A-Za-z0-9]{2,}")
_RE_ALPHANUM = re.compile(r"[A-Za-z0-9一-鿿㐀-䶿]")

_STOPWORDS_EN = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "and", "but", "or", "if", "while", "it", "its",
    "this", "that", "these", "those", "just", "about", "also",
}
_STOPWORDS_ZH = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些",
    "所", "被", "把", "让", "给", "对", "从", "向", "但", "而", "且",
    "或", "与", "及", "更", "已经", "还", "可以", "这个", "那个", "什么",
    "怎么", "如果", "因为", "所以", "然后", "不过", "虽然", "只是",
}


def _normalize(value: Any) -> str:
    """Flatten any value to a lowercased, whitespace-collapsed string."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_normalize(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_normalize(item) for item in value)
    s = str(value).strip().lower()
    s = _ASIAN_PUNCT.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def _display(value: Any) -> str:
    """Render for human reading (preserve original casing)."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _contains(haystack: Any, needle: Any) -> bool:
    """Case-folded substring containment."""
    hn = _normalize(haystack)
    nd = _normalize(needle)
    return bool(hn and nd and nd in hn)


def _keywords(text: str) -> List[str]:
    """Extract lightweight keywords: ASCII words (≥2 chars) + CJK bigrams."""
    result: List[str] = []
    t = _normalize(text)
    for m in _RE_ASCII_WORD.finditer(t):
        w = m.group()
        if w not in _STOPWORDS_EN:
            result.append(w)
    cjk_chars = _RE_CJK.findall(t)
    if len(cjk_chars) >= 2:
        result.extend("".join(cjk_chars[i:i + 2]) for i in range(len(cjk_chars) - 1))
    return result


def _keyword_overlap(needle: str, haystack: str, min_overlap: int = 1) -> bool:
    """True when at least min_overlap keywords from needle appear in haystack."""
    n_kw = _keywords(needle)
    if not n_kw:
        return False
    h_norm = _normalize(haystack)
    matched = sum(1 for kw in n_kw if kw in h_norm)
    return matched >= min_overlap


def _phrase_contains(text: str, phrase: str) -> bool:
    """Check if phrase or at least 2 of its keywords appear in text."""
    if not phrase or not text:
        return False
    tn = _normalize(text)
    pn = _normalize(phrase)
    if pn and pn in tn:
        return True
    return _keyword_overlap(phrase, text, min_overlap=2)


def _strong_overlap(text: str, candidate_text: str) -> bool:
    """Candidate's core subject + action/object terms are found in text."""
    if not candidate_text or not text:
        return False
    tn = _normalize(text)
    # full substring match is strong
    cn = _normalize(candidate_text)
    if cn and cn in tn:
        return True
    # or most keywords overlap
    c_kw = _keywords(candidate_text)
    if not c_kw:
        return False
    matched = sum(1 for kw in c_kw if kw in tn)
    return matched >= max(2, len(c_kw) * 0.5)


def _weak_overlap(text: str, candidate_text: str) -> bool:
    """At least some shared keywords between candidate and text."""
    if not candidate_text or not text:
        return False
    return _keyword_overlap(candidate_text, text, min_overlap=1)


# ── data access ──────────────────────────────────────────────────────────────


def connect_read_only(db_path: Path) -> sqlite3.Connection:
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _iter_list(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def fetch_extractions(conn: sqlite3.Connection, limit: int) -> List[sqlite3.Row]:
    sql = """
        SELECT
            e.id AS extraction_id,
            e.chunk_id AS chunk_id,
            e.extraction_json AS extraction_json,
            c.text AS chunk_text,
            c.document_id AS document_id,
            d.path AS document_path,
            d.title AS document_title
        FROM extractions e
        LEFT JOIN chunks c ON e.chunk_id = c.id
        LEFT JOIN documents d ON c.document_id = d.id
        ORDER BY e.id
    """
    params: Tuple[Any, ...] = ()
    if limit > 0:
        sql += " LIMIT ?"
        params = (limit,)
    return conn.execute(sql, params).fetchall()


def fetch_supports(conn: sqlite3.Connection) -> Dict[Tuple[int, int], Dict[str, Any]]:
    """Return {(extraction_id, candidate_index): {decision, reason, state_id}}."""
    rows = conn.execute(
        "SELECT extraction_id, candidate_index, decision, reason, state_id "
        "FROM state_candidate_supports ORDER BY id"
    ).fetchall()
    result: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for row in rows:
        key = (int(row["extraction_id"]), int(row["candidate_index"]))
        result[key] = {
            "decision": row["decision"],
            "reason": row["reason"],
            "state_id": row["state_id"],
        }
    return result


# ── grounding check helpers ──────────────────────────────────────────────────


def _text_support_level(text: str, candidate_field: Any) -> str:
    """strong | weak | none | not_provided"""
    val = _display(candidate_field)
    if not val:
        return "not_provided"
    if _strong_overlap(text, val):
        return "strong"
    if _weak_overlap(text, val):
        return "weak"
    return "none"


def _collect_matched_terms(text: str, candidate_text: str) -> List[str]:
    """Return keywords from candidate_text that appear in text."""
    if not candidate_text or not text:
        return []
    tn = _normalize(text)
    return [kw for kw in _keywords(candidate_text) if kw in tn]


def _collect_missing_terms(text: str, candidate_text: str) -> List[str]:
    """Return keywords from candidate_text NOT found in text."""
    if not candidate_text or not text:
        return []
    tn = _normalize(text)
    return [kw for kw in _keywords(candidate_text) if kw not in tn]


# ── per-dimension audit functions ────────────────────────────────────────────


def audit_subject_grounding(
    candidate: Dict[str, Any],
    chunk_text: str,
    entities: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    context: Dict[str, Any],
    source_context_blocks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    subject_type = _display(candidate.get("subject_type"))
    subject_key = _display(candidate.get("subject_key"))
    if not subject_key:
        return {
            "subject_type": subject_type,
            "subject_key": "",
            "found_in_chunk_text": False,
            "found_in_entities": False,
            "found_in_event_participants": False,
            "found_in_relation_candidates": False,
            "found_in_context_only": False,
            "found_only_in_context": False,
            "entity_type_matches_subject_type": False,
            "risk_flags": ["missing_subject_key"],
        }

    found_in_chunk_text = _contains(chunk_text, subject_key)
    found_in_entities = any(
        _contains(e.get("text"), subject_key) or _contains(subject_key, e.get("text"))
        for e in entities
    )
    found_in_event_participants = any(
        any(_contains(p, subject_key) or _contains(subject_key, p)
            for p in (ev.get("participants") or []))
        for ev in events
    )
    found_in_relations = any(
        _contains(r.get("source"), subject_key) or _contains(r.get("target"), subject_key)
        or _contains(subject_key, r.get("source")) or _contains(subject_key, r.get("target"))
        for r in relations
    )

    # context / context_only checks
    doc_author = _display(context.get("document_author"))
    found_in_doc_author = bool(doc_author and _normalize(doc_author) == _normalize(subject_key))

    ctx_blocks_text = " ".join(
        _display(b.get("text_preview")) for b in source_context_blocks
    )
    found_in_context_blocks = _contains(ctx_blocks_text, subject_key)

    # found in any context source but NOT in chunk/entities/events/relations
    in_context = found_in_doc_author or found_in_context_blocks
    in_observation = found_in_chunk_text or found_in_entities or found_in_event_participants or found_in_relations
    found_only_in_context = in_context and not in_observation

    # entity type vs subject_type
    subject_entity_types = [
        _display(e.get("type"))
        for e in entities
        if _contains(e.get("text"), subject_key) or _contains(subject_key, e.get("text"))
    ]
    entity_type_matches = (
        not subject_type
        or not subject_entity_types
        or any(_normalize(t) == _normalize(subject_type) for t in subject_entity_types)
    )

    risk_flags: List[str] = []
    if not found_in_chunk_text:
        risk_flags.append("subject_not_in_chunk_text")
    if not found_in_entities:
        risk_flags.append("subject_not_in_entities")
    if found_only_in_context:
        risk_flags.append("subject_only_in_context")
    if found_in_doc_author and not found_in_chunk_text and not found_in_entities:
        risk_flags.append("document_author_used_as_subject_without_text_support")
    if subject_type and subject_entity_types and not entity_type_matches:
        risk_flags.append("subject_type_entity_type_conflict")

    return {
        "subject_type": subject_type,
        "subject_key": subject_key,
        "found_in_chunk_text": found_in_chunk_text,
        "found_in_entities": found_in_entities,
        "found_in_event_participants": found_in_event_participants,
        "found_in_relation_candidates": found_in_relations,
        "found_in_context_only": found_in_context_blocks,
        "found_only_in_context": found_only_in_context,
        "entity_type_matches_subject_type": entity_type_matches,
        "risk_flags": risk_flags,
    }


def audit_text_grounding(
    candidate: Dict[str, Any],
    chunk_text: str,
) -> Dict[str, Any]:
    summary = _display(candidate.get("summary"))
    canonical = _display(candidate.get("canonical_summary"))
    display_s = _display(candidate.get("display_summary"))
    detail = _display(candidate.get("detail"))

    # build combined candidate text for matched/missing terms
    combined = " ".join(p for p in [summary, canonical, display_s, detail] if p)
    matched_terms = _collect_matched_terms(chunk_text, combined)
    missing_terms = _collect_missing_terms(chunk_text, combined)

    risk_flags: List[str] = []
    summary_support = _text_support_level(chunk_text, candidate.get("summary"))
    if summary_support == "none":
        risk_flags.append("summary_not_supported_by_chunk_text")

    canonical_support = _text_support_level(chunk_text, candidate.get("canonical_summary"))
    if canonical_support == "weak":
        risk_flags.append("canonical_summary_expands_beyond_text")

    display_support = _text_support_level(chunk_text, candidate.get("display_summary"))
    if display_support == "none" and display_s:
        risk_flags.append("display_summary_too_generic")

    detail_support = _text_support_level(chunk_text, candidate.get("detail"))
    if detail_support == "weak" and detail:
        risk_flags.append("detail_expands_beyond_text")

    return {
        "summary_support": summary_support,
        "canonical_summary_support": canonical_support,
        "display_summary_support": display_support,
        "detail_support": detail_support,
        "matched_terms": matched_terms,
        "missing_terms": missing_terms,
        "risk_flags": risk_flags,
    }


def audit_event_grounding(
    candidate: Dict[str, Any],
    events: List[Dict[str, Any]],
    chunk_text: str,
) -> Dict[str, Any]:
    subject_key = _normalize(candidate.get("subject_key"))
    candidate_text = " ".join([
        _display(candidate.get(f)) for f in ("summary", "canonical_summary", "detail")
    ])

    matched_indexes: List[int] = []
    action_supported = False
    subject_in_participants = False
    time_consistency = "not_applicable"

    candidate_time = candidate.get("time")
    if isinstance(candidate_time, dict):
        cand_time_norm = _normalize(candidate_time.get("normalized"))
    else:
        cand_time_norm = ""

    risk_flags: List[str] = []

    for i, ev in enumerate(events):
        description = _display(ev.get("description"))
        participants = [str(p).strip() for p in (ev.get("participants") or [])]

        # check subject in participants
        if subject_key:
            for p in participants:
                if _contains(p, subject_key) or _contains(subject_key, p):
                    subject_in_participants = True
                    break

        # check action overlap
        if _keyword_overlap(candidate_text, description, min_overlap=2) or _contains(
            description, candidate.get("summary")
        ):
            matched_indexes.append(i)
            action_supported = True
        elif subject_in_participants and _weak_overlap(description, candidate_text):
            matched_indexes.append(i)

        # time consistency
        if cand_time_norm:
            ev_time = ev.get("time")
            if isinstance(ev_time, dict):
                ev_time_norm = _normalize(ev_time.get("normalized"))
                if ev_time_norm:
                    if ev_time_norm == cand_time_norm:
                        time_consistency = "consistent"
                    elif time_consistency != "consistent":
                        time_consistency = "conflict"

    if not matched_indexes:
        risk_flags.append("no_matching_event")
    if matched_indexes and not action_supported:
        risk_flags.append("event_action_mismatch")
    if not subject_in_participants and subject_key:
        risk_flags.append("event_participants_do_not_support_subject")
    if time_consistency == "conflict":
        risk_flags.append("candidate_time_conflicts_with_event_time")
    if action_supported and not _contains(candidate.get("summary"), _display(
        events[matched_indexes[0]].get("description")
    )):
        if candidate.get("detail") and len(_display(candidate.get("detail"))) > len(
            _display(events[matched_indexes[0]].get("description"))
        ):
            risk_flags.append("state_candidate_more_specific_than_event")

    event_support = "strong"
    if not matched_indexes:
        event_support = "none"
    elif not action_supported:
        event_support = "weak"
    elif time_consistency == "conflict":
        event_support = "weak"

    return {
        "matched_event_indexes": matched_indexes,
        "event_support": event_support,
        "action_supported_by_event": action_supported,
        "subject_supported_by_event_participants": subject_in_participants,
        "time_consistency": time_consistency,
        "risk_flags": risk_flags,
    }


def audit_relation_grounding(
    candidate: Dict[str, Any],
    relations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    subject_key = _display(candidate.get("subject_key"))
    summary = _display(candidate.get("summary"))
    subtype = _display(candidate.get("subtype"))
    detail = _display(candidate.get("detail"))

    matched_indexes: List[int] = []
    supports_link = False
    supports_subtype = False

    # subtype → relation_type loose mapping
    subtype_relation_hints = {
        "ongoing_project": ["works_with", "depends_on", "uses"],
        "recent_event": ["related_to"],
        "pending_task": ["depends_on", "related_to"],
        "active_interest": ["uses", "related_to"],
    }
    expected_relations = subtype_relation_hints.get(subtype, [])

    risk_flags: List[str] = []

    for i, rel in enumerate(relations):
        source = _display(rel.get("source"))
        target = _display(rel.get("target"))
        rtype = _display(rel.get("relation_type"))

        if subject_key:
            source_match = _contains(source, subject_key) or _contains(subject_key, source)
            target_match = _contains(target, subject_key) or _contains(subject_key, target)
            if source_match or target_match:
                matched_indexes.append(i)
                # does the other end appear in summary?
                other = target if source_match else source
                if other and (_contains(summary, other) or _contains(other, summary)):
                    supports_link = True

        # does relation_type weakly support the candidate subtype?
        if expected_relations and rtype in expected_relations:
            supports_subtype = True

    if not matched_indexes and relations:
        risk_flags.append("no_matching_relation")
    if matched_indexes and not supports_link:
        risk_flags.append("relation_subject_object_mismatch")
    if relations and not matched_indexes:
        risk_flags.append("relation_candidate_unused_but_relevant")
    if subtype and relations and not supports_subtype:
        risk_flags.append("relation_type_does_not_support_subtype")

    relation_support = "strong" if supports_link else ("weak" if matched_indexes else "none")

    return {
        "matched_relation_indexes": matched_indexes,
        "relation_support": relation_support,
        "supports_subject_object_link": supports_link,
        "supports_subtype_or_detail": supports_subtype,
        "risk_flags": risk_flags,
    }


def audit_retrieval_grounding(
    candidate: Dict[str, Any],
    retrievals: List[Dict[str, Any]],
    chunk_text: str,
) -> Dict[str, Any]:
    subject_key = _normalize(candidate.get("subject_key"))
    summary = _normalize(_display(candidate.get("summary")))
    detail = _normalize(_display(candidate.get("detail")))
    combined = f"{subject_key} {summary} {detail}"

    matched_indexes: List[int] = []
    has_ambiguity = False
    ambiguity_affects_subject = False
    ambiguity_affects_object = False

    risk_flags: List[str] = []

    for i, rc in enumerate(retrievals):
        sf = _normalize(rc.get("surface_form"))
        if not sf:
            continue
        # check if surface_form appears in candidate or chunk
        if sf and (sf in combined or sf in _normalize(chunk_text)):
            matched_indexes.append(i)
            has_ambiguity = True
            if subject_key and (sf in subject_key or subject_key in sf):
                ambiguity_affects_subject = True
                risk_flags.append("subject_depends_on_unresolved_retrieval_candidate")
            else:
                ambiguity_affects_object = True
                risk_flags.append("object_depends_on_unresolved_retrieval_candidate")

    if matched_indexes and not ambiguity_affects_subject and not ambiguity_affects_object:
        risk_flags.append("ambiguous_surface_form_in_summary")
    if retrievals and not matched_indexes:
        risk_flags.append("retrieval_candidate_present_but_not_reflected_in_candidate")

    return {
        "matched_retrieval_indexes": matched_indexes,
        "has_ambiguity": has_ambiguity,
        "ambiguity_affects_subject": ambiguity_affects_subject,
        "ambiguity_affects_object": ambiguity_affects_object,
        "risk_flags": risk_flags,
    }


def audit_context_grounding(
    candidate: Dict[str, Any],
    context: Dict[str, Any],
    source_context_blocks: List[Dict[str, Any]],
    chunk_text: str,
) -> Dict[str, Any]:
    subject_key = _display(candidate.get("subject_key"))
    summary = _display(candidate.get("summary"))
    detail = _display(candidate.get("detail"))
    candidate_text = " ".join(p for p in [subject_key, summary, detail] if p)

    doc_title = _display(context.get("document_title"))
    doc_author = _display(context.get("document_author"))
    doc_time = _display(context.get("document_time"))
    section = _display(context.get("section"))

    uses_document_title = bool(doc_title and doc_title in candidate_text)
    uses_document_author = bool(
        doc_author and _normalize(doc_author) == _normalize(subject_key)
    )
    uses_document_time = bool(doc_time and doc_time in candidate_text)
    uses_section = bool(section and section in candidate_text)
    uses_source_context_blocks = False

    risk_flags: List[str] = []

    # source_context_blocks analysis
    ctx_blocks_text = " ".join(
        _display(b.get("text_preview")) for b in source_context_blocks
    )

    context_only_support = "none"
    if source_context_blocks:
        # check if candidate core info depends on context blocks
        has_chunk_support = _weak_overlap(chunk_text, summary) if summary else False
        has_ctx_support = _weak_overlap(ctx_blocks_text, summary) if summary else False

        if has_ctx_support:
            uses_source_context_blocks = True
            if has_chunk_support:
                context_only_support = "auxiliary"
            else:
                context_only_support = "only"
                risk_flags.append("context_only_only")

    if uses_document_title:
        risk_flags.append("document_title_driven_candidate")
    if uses_document_author and not _contains(chunk_text, subject_key):
        risk_flags.append("document_author_driven_subject")
    if uses_document_time and not _contains(chunk_text, doc_time):
        risk_flags.append("document_time_overused")
    if uses_section and not _weak_overlap(chunk_text, summary):
        risk_flags.append("section_overused_as_fact")

    return {
        "uses_document_title": uses_document_title,
        "uses_document_author": uses_document_author,
        "uses_document_time": uses_document_time,
        "uses_section": uses_section,
        "uses_source_context_blocks": uses_source_context_blocks,
        "context_only_support": context_only_support,
        "risk_flags": risk_flags,
    }


def compute_overall_grounding(
    subject: Dict[str, Any],
    text: Dict[str, Any],
    event: Dict[str, Any],
    relation: Dict[str, Any],
    retrieval: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    all_risks: List[str] = []
    for dim in [subject, text, event, relation, retrieval, context]:
        all_risks.extend(dim.get("risk_flags", []))

    # ── decide level ──
    context_only_only = "context_only_only" in all_risks
    text_none = text.get("summary_support") == "none"
    text_weak = text.get("summary_support") == "weak"
    text_strong = text.get("summary_support") == "strong"
    subject_in_text = subject.get("found_in_chunk_text", False)
    subject_in_entities = subject.get("found_in_entities", False)
    subject_only_ctx = subject.get("found_only_in_context", False)
    event_none = event.get("event_support") == "none"
    event_action = event.get("action_supported_by_event", False)
    time_conflict = "candidate_time_conflicts_with_event_time" in all_risks
    has_ambiguity = retrieval.get("has_ambiguity", False)
    subject_type_conflict = "subject_type_entity_type_conflict" in all_risks

    level = "medium"
    reasons: List[str] = []

    if subject_in_text and text_strong and (event_action or relation.get("supports_subject_object_link")):
        level = "strong"
        reasons.append("主体、动作和对象均能回到正文与 observation;")
    elif context_only_only:
        level = "risky"
        reasons.append("关键信息只存在于 context_only 材料中")
    elif subject_only_ctx:
        level = "risky"
        reasons.append("主体只来自 context，chunk text 无支撑")
    elif time_conflict or subject_type_conflict:
        level = "inconsistent"
        reasons.append("candidate 与 observation 存在明显冲突")
    elif text_none and event_none:
        level = "weak"
        reasons.append("chunk text 和 event 均无法支撑 candidate 核心语义")
    elif text_weak or (not subject_in_text and not subject_in_entities):
        level = "weak"
        reasons.append("只有部分词面支撑，event/relation 均不明显")
    elif has_ambiguity and not subject_in_text:
        level = "risky"
        reasons.append("对象未消歧且正文支撑弱")
    else:
        # medium — partial support
        reasons.append("subject 和 summary 能回到 chunk text，event/relation 支撑不完整")

    main_reason = " ".join(reasons) if reasons else "无法确定"

    return {
        "level": level,
        "main_reason": main_reason,
        "risk_flags": all_risks,
    }


def compute_admission_cross_check(
    current_decision: str,
    current_reason: str,
    overall_level: str,
) -> Dict[str, Any]:
    if current_decision == "missing":
        return {
            "current_decision": "missing",
            "current_reason": "",
            "audit_judgment": "missing_admission_record",
            "note": "当前 extraction 在 state_candidate_supports 中没有记录。",
        }

    strong_or_medium = overall_level in ("strong", "medium")
    weak_risky_inconsistent = overall_level in ("weak", "risky", "inconsistent")

    if current_decision == "accept" and strong_or_medium:
        judgment = "aligned_accept"
        note = "当前准入结果与 grounding 结果一致。"
    elif current_decision == "reject" and weak_risky_inconsistent:
        judgment = "aligned_reject"
        note = "当前准入结果与 grounding 结果一致。"
    elif current_decision == "accept" and weak_risky_inconsistent:
        judgment = "possible_false_accept"
        note = f"candidate 被 accept（理由: {current_reason}），但 grounding 为 {overall_level}。建议人工复核。"
    elif current_decision == "reject" and strong_or_medium:
        judgment = "possible_false_reject"
        note = f"candidate 被 reject（理由: {current_reason}），但 grounding 为 {overall_level}。建议检查准入规则是否过严。"
    else:
        judgment = "aligned_accept"
        note = "无法判断。"
    return {
        "current_decision": current_decision,
        "current_reason": current_reason,
        "audit_judgment": judgment,
        "note": note,
    }


# ── main audit entry ─────────────────────────────────────────────────────────


def audit_candidate(
    *,
    extraction_id: int,
    chunk_id: int | None,
    document_path: str,
    chunk_text: str,
    extraction_json: Dict[str, Any],
    candidate_index: int,
    candidate: Dict[str, Any],
    support_row: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    context = (
        extraction_json.get("context")
        if isinstance(extraction_json.get("context"), dict)
        else {}
    )
    entities = _iter_list(extraction_json.get("entities"))
    events = _iter_list(extraction_json.get("events"))
    relations = _iter_list(extraction_json.get("relation_candidates"))
    retrievals = _iter_list(extraction_json.get("retrieval_candidates"))
    source_ctx_blocks = _iter_list(context.get("source_context_blocks"))

    # 1. candidate info
    decision = "missing"
    reason = ""
    if support_row is not None:
        decision = support_row.get("decision", "missing")
        reason = support_row.get("reason", "")

    candidate_info = {
        "extraction_id": extraction_id,
        "chunk_id": chunk_id,
        "candidate_index": candidate_index,
        "candidate_summary": _display(candidate.get("summary")),
        "candidate_canonical_summary": _display(candidate.get("canonical_summary")),
        "candidate_display_summary": _display(candidate.get("display_summary")),
        "category": _display(candidate.get("category")),
        "subtype": _display(candidate.get("subtype")),
        "subject_type": _display(candidate.get("subject_type")),
        "subject_key": _display(candidate.get("subject_key")),
        "current_support_decision": decision,
        "current_support_reason": reason,
    }

    # 2-7. grounding dimensions
    subject_g = audit_subject_grounding(
        candidate, chunk_text, entities, events, relations, context, source_ctx_blocks
    )
    text_g = audit_text_grounding(candidate, chunk_text)
    event_g = audit_event_grounding(candidate, events, chunk_text)
    relation_g = audit_relation_grounding(candidate, relations)
    retrieval_g = audit_retrieval_grounding(candidate, retrievals, chunk_text)
    context_g = audit_context_grounding(candidate, context, source_ctx_blocks, chunk_text)

    # 8. overall
    overall_g = compute_overall_grounding(
        subject_g, text_g, event_g, relation_g, retrieval_g, context_g
    )

    # 9. cross-check
    cross_check = compute_admission_cross_check(decision, reason, overall_g["level"])

    return {
        "candidate_info": candidate_info,
        "subject_grounding": subject_g,
        "text_grounding": text_g,
        "event_grounding": event_g,
        "relation_grounding": relation_g,
        "retrieval_grounding": retrieval_g,
        "context_grounding": context_g,
        "overall_grounding": overall_g,
        "admission_cross_check": cross_check,
    }


# ── output formatters ────────────────────────────────────────────────────────


def _fmt_list(items: List[Any]) -> str:
    if not items:
        return "none"
    return ", ".join(str(i) for i in items[:20])


def print_text_report(items: List[Dict[str, Any]]) -> None:
    if not items:
        print("No state_candidates found in inspected extraction rows.")
        return

    for item in items:
        info = item["candidate_info"]
        subject = item["subject_grounding"]
        text = item["text_grounding"]
        event = item["event_grounding"]
        relation = item["relation_grounding"]
        retrieval = item["retrieval_grounding"]
        context = item["context_grounding"]
        overall = item["overall_grounding"]
        cross = item["admission_cross_check"]

        print(f"Extraction #{info['extraction_id']} / Chunk #{info['chunk_id']} / "
              f"Candidate[{info['candidate_index']}]")
        print(f"  summary: {info['candidate_summary'][:120]}")
        print(f"  subject: {info['subject_type']} / {info['subject_key']}")
        print(f"  admission: {info['current_support_decision']} ({info['current_support_reason']})")
        print(f"  overall grounding: {overall['level']} — {overall['main_reason'][:160]}")
        print(f"  risk flags: {_fmt_list(overall['risk_flags'])}")
        print(f"  cross-check: {cross['audit_judgment']} — {cross['note'][:160]}")
        print()

        # detailed dimensions (abbreviated)
        print(f"  Subject grounding:")
        print(f"    in chunk_text: {_yes(subject['found_in_chunk_text'])}  "
              f"in entities: {_yes(subject['found_in_entities'])}  "
              f"in events: {_yes(subject['found_in_event_participants'])}  "
              f"in relations: {_yes(subject['found_in_relation_candidates'])}")
        if subject["risk_flags"]:
            print(f"    risks: {_fmt_list(subject['risk_flags'])}")

        print(f"  Text grounding:")
        print(f"    summary: {text['summary_support']}  "
              f"canonical: {text['canonical_summary_support']}  "
              f"display: {text['display_summary_support']}  "
              f"detail: {text['detail_support']}")
        if text["matched_terms"]:
            print(f"    matched: {_fmt_list(text['matched_terms'])}")
        if text["risk_flags"]:
            print(f"    risks: {_fmt_list(text['risk_flags'])}")

        print(f"  Event grounding:")
        print(f"    support: {event['event_support']}  "
              f"action: {_yes(event['action_supported_by_event'])}  "
              f"subject_in_participants: {_yes(event['subject_supported_by_event_participants'])}  "
              f"time: {event['time_consistency']}")
        if event["risk_flags"]:
            print(f"    risks: {_fmt_list(event['risk_flags'])}")

        print(f"  Relation grounding:")
        print(f"    support: {relation['relation_support']}  "
              f"link: {_yes(relation['supports_subject_object_link'])}  "
              f"subtype: {_yes(relation['supports_subtype_or_detail'])}")
        if relation["risk_flags"]:
            print(f"    risks: {_fmt_list(relation['risk_flags'])}")

        print(f"  Retrieval grounding:")
        print(f"    ambiguity: {_yes(retrieval['has_ambiguity'])}  "
              f"affects_subject: {_yes(retrieval['ambiguity_affects_subject'])}  "
              f"affects_object: {_yes(retrieval['ambiguity_affects_object'])}")
        if retrieval["risk_flags"]:
            print(f"    risks: {_fmt_list(retrieval['risk_flags'])}")

        print(f"  Context grounding:")
        print(f"    title: {_yes(context['uses_document_title'])}  "
              f"author: {_yes(context['uses_document_author'])}  "
              f"time: {_yes(context['uses_document_time'])}  "
              f"section: {_yes(context['uses_section'])}  "
              f"ctx_blocks: {_yes(context['uses_source_context_blocks'])}")
        print(f"    context_only_support: {context['context_only_support']}")
        if context["risk_flags"]:
            print(f"    risks: {_fmt_list(context['risk_flags'])}")

        print()


def _yes(v: bool) -> str:
    return "yes" if v else "no"


def print_markdown_report(items: List[Dict[str, Any]]) -> None:
    if not items:
        print("*No state_candidates found in inspected extraction rows.*")
        return

    # summary
    levels = {"strong": 0, "medium": 0, "weak": 0, "risky": 0, "inconsistent": 0}
    cross_counts = {
        "aligned_accept": 0, "aligned_reject": 0,
        "possible_false_accept": 0, "possible_false_reject": 0,
        "missing_admission_record": 0,
    }
    extraction_ids: set[int] = set()
    for item in items:
        extraction_ids.add(item["candidate_info"]["extraction_id"])
        lv = item["overall_grounding"]["level"]
        if lv in levels:
            levels[lv] += 1
        cc = item["admission_cross_check"]["audit_judgment"]
        if cc in cross_counts:
            cross_counts[cc] += 1

    print("# State Candidate Grounding Audit\n")
    print("## Summary\n")
    print(f"- Extractions inspected: {len(extraction_ids)}")
    print(f"- State candidates: {len(items)}")
    print(f"- Strong: {levels['strong']}")
    print(f"- Medium: {levels['medium']}")
    print(f"- Weak: {levels['weak']}")
    print(f"- Risky: {levels['risky']}")
    print(f"- Inconsistent: {levels['inconsistent']}")
    print(f"- Aligned accept: {cross_counts['aligned_accept']}")
    print(f"- Aligned reject: {cross_counts['aligned_reject']}")
    print(f"- Possible false accept: {cross_counts['possible_false_accept']}")
    print(f"- Possible false reject: {cross_counts['possible_false_reject']}")
    print(f"- Missing admission record: {cross_counts['missing_admission_record']}")
    print()

    for idx, item in enumerate(items, 1):
        info = item["candidate_info"]
        subject = item["subject_grounding"]
        text = item["text_grounding"]
        event = item["event_grounding"]
        relation = item["relation_grounding"]
        retrieval = item["retrieval_grounding"]
        context = item["context_grounding"]
        overall = item["overall_grounding"]
        cross = item["admission_cross_check"]

        print(f"## Candidate {idx}\n")
        print(f"- **extraction_id**: {info['extraction_id']}")
        print(f"- **chunk_id**: {info['chunk_id']}")
        print(f"- **candidate_index**: {info['candidate_index']}")
        print(f"- **summary**: {info['candidate_summary']}")
        print(f"- **canonical_summary**: {info['candidate_canonical_summary'] or '—'}")
        print(f"- **display_summary**: {info['candidate_display_summary'] or '—'}")
        print(f"- **category / subtype**: {info['category']} / {info['subtype']}")
        print(f"- **subject**: {info['subject_type']} / {info['subject_key']}")
        print(f"- **current admission**: {info['current_support_decision']}"
              f" ({info['current_support_reason']})")
        print(f"- **overall grounding**: **{overall['level']}** — {overall['main_reason']}")
        print()

        _md_section("Subject grounding", subject, [
            ("subject_key in chunk_text", subject["found_in_chunk_text"]),
            ("subject_key in entities", subject["found_in_entities"]),
            ("subject_key in event participants", subject["found_in_event_participants"]),
            ("subject_key in relation_candidates", subject["found_in_relation_candidates"]),
            ("subject_key in context_only", subject["found_in_context_only"]),
            ("found only in context", subject["found_only_in_context"]),
            ("entity_type matches subject_type", subject["entity_type_matches_subject_type"]),
        ])

        _md_section("Text grounding", text, [
            ("summary support", text["summary_support"]),
            ("canonical_summary support", text["canonical_summary_support"]),
            ("display_summary support", text["display_summary_support"]),
            ("detail support", text["detail_support"]),
        ])
        if text["matched_terms"]:
            print(f"  - matched terms: {_fmt_list(text['matched_terms'])}")
        if text["missing_terms"]:
            print(f"  - missing terms: {_fmt_list(text['missing_terms'])}")
        _md_risks(text["risk_flags"])

        _md_section("Event grounding", event, [
            ("event support", event["event_support"]),
            ("action supported by event", event["action_supported_by_event"]),
            ("subject in event participants", event["subject_supported_by_event_participants"]),
            ("time consistency", event["time_consistency"]),
        ])
        if event["matched_event_indexes"]:
            print(f"  - matched events: {event['matched_event_indexes']}")
        _md_risks(event["risk_flags"])

        _md_section("Relation grounding", relation, [
            ("relation support", relation["relation_support"]),
            ("supports subject-object link", relation["supports_subject_object_link"]),
            ("supports subtype or detail", relation["supports_subtype_or_detail"]),
        ])
        if relation["matched_relation_indexes"]:
            print(f"  - matched relations: {relation['matched_relation_indexes']}")
        _md_risks(relation["risk_flags"])

        _md_section("Retrieval / ambiguity", retrieval, [
            ("has ambiguity", retrieval["has_ambiguity"]),
            ("ambiguity affects subject", retrieval["ambiguity_affects_subject"]),
            ("ambiguity affects object", retrieval["ambiguity_affects_object"]),
        ])
        if retrieval["matched_retrieval_indexes"]:
            print(f"  - matched retrieval candidates: {retrieval['matched_retrieval_indexes']}")
        _md_risks(retrieval["risk_flags"])

        _md_section("Context-only risk", context, [
            ("uses document_title", context["uses_document_title"]),
            ("uses document_author", context["uses_document_author"]),
            ("uses document_time", context["uses_document_time"]),
            ("uses section", context["uses_section"]),
            ("uses source_context_blocks", context["uses_source_context_blocks"]),
            ("context_only_support", context["context_only_support"]),
        ])
        _md_risks(context["risk_flags"])

        _md_section("Cross-check", cross, [
            ("current decision", cross["current_decision"]),
            ("current reason", cross["current_reason"]),
            ("audit judgment", cross["audit_judgment"]),
        ])
        print(f"  - **note**: {cross['note']}")
        print()
        print("---")
        print()


def _md_section(title: str, dim: Dict[str, Any], fields: List[Tuple[str, Any]]) -> None:
    print(f"### {title}\n")
    for label, value in fields:
        if isinstance(value, bool):
            value = "yes" if value else "no"
        print(f"  - **{label}**: {value}")
    print()


def _md_risks(risk_flags: List[str]) -> None:
    if risk_flags:
        print(f"  - **risk_flags**: {_fmt_list(risk_flags)}")
    print()


# ── main ─────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit possible grounding relationships between Observation IR "
            "objects and state_candidates. This is a read-only hint, not validation."
        )
    )
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path.")
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of extraction rows to inspect. Use 0 for no limit.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of text.",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Emit Markdown report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}", file=sys.stderr)
        return 1

    try:
        conn = connect_read_only(db_path)
    except sqlite3.Error as exc:
        print(f"Could not open database read-only: {exc}", file=sys.stderr)
        return 1

    items: List[Dict[str, Any]] = []
    invalid_extractions: List[str] = []

    try:
        rows = fetch_extractions(conn, args.limit)
        supports = fetch_supports(conn)
    except sqlite3.Error as exc:
        print(f"Could not read extraction rows: {exc}", file=sys.stderr)
        conn.close()
        return 1
    finally:
        conn.close()

    if not rows:
        print("No extractions found in the database.")
        return 0

    for row in rows:
        extraction_id = int(row["extraction_id"])
        raw_json = row["extraction_json"]
        if not raw_json:
            invalid_extractions.append(
                f"Extraction #{extraction_id}: empty extraction_json, skipped."
            )
            continue

        try:
            extraction_json = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            invalid_extractions.append(
                f"Extraction #{extraction_id}: invalid extraction_json ({exc}), skipped."
            )
            continue

        if not isinstance(extraction_json, dict):
            invalid_extractions.append(
                f"Extraction #{extraction_id}: extraction_json is not an object, skipped."
            )
            continue

        candidates = _iter_list(extraction_json.get("state_candidates"))
        for index, candidate in enumerate(candidates):
            support_row = supports.get((extraction_id, index))
            items.append(
                audit_candidate(
                    extraction_id=extraction_id,
                    chunk_id=row["chunk_id"],
                    document_path=_display(
                        row["document_path"] or row["document_title"] or "<unknown>"
                    ),
                    chunk_text=_display(row["chunk_text"]),
                    extraction_json=extraction_json,
                    candidate_index=index,
                    candidate=candidate,
                    support_row=support_row,
                )
            )

    # compute summary
    levels = {"strong": 0, "medium": 0, "weak": 0, "risky": 0, "inconsistent": 0}
    cross_judgments: Dict[str, int] = {
        "aligned_accept": 0, "aligned_reject": 0,
        "possible_false_accept": 0, "possible_false_reject": 0,
        "missing_admission_record": 0,
    }
    extraction_ids: set[int] = set()
    for item in items:
        extraction_ids.add(item["candidate_info"]["extraction_id"])
        lv = item["overall_grounding"]["level"]
        if lv in levels:
            levels[lv] += 1
        cc = item["admission_cross_check"]["audit_judgment"]
        if cc in cross_judgments:
            cross_judgments[cc] += 1

    summary = {
        "extractions": len(extraction_ids),
        "state_candidates": len(items),
        "strong": levels["strong"],
        "medium": levels["medium"],
        "weak": levels["weak"],
        "risky": levels["risky"],
        "inconsistent": levels["inconsistent"],
        "aligned_accept": cross_judgments["aligned_accept"],
        "aligned_reject": cross_judgments["aligned_reject"],
        "possible_false_accept": cross_judgments["possible_false_accept"],
        "possible_false_reject": cross_judgments["possible_false_reject"],
        "missing_admission_record": cross_judgments["missing_admission_record"],
    }

    if args.json:
        print(
            json.dumps(
                {
                    "summary": summary,
                    "items": items,
                    "invalid_extractions": invalid_extractions,
                    "note": "This is an audit hint, not validation.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.markdown:
        print_markdown_report(items)
        return 0

    # default text output
    for message in invalid_extractions:
        print(message, file=sys.stderr)
    print(f"# State Candidate Grounding Audit Summary\n")
    print(f"Extractions: {summary['extractions']}  Candidates: {summary['state_candidates']}")
    print(f"Strong: {summary['strong']}  Medium: {summary['medium']}  "
          f"Weak: {summary['weak']}  Risky: {summary['risky']}  "
          f"Inconsistent: {summary['inconsistent']}")
    print(f"Aligned accept: {summary['aligned_accept']}  "
          f"Aligned reject: {summary['aligned_reject']}")
    print(f"Possible false accept: {summary['possible_false_accept']}  "
          f"Possible false reject: {summary['possible_false_reject']}")
    print(f"Missing admission: {summary['missing_admission_record']}")
    print()
    print_text_report(items)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
