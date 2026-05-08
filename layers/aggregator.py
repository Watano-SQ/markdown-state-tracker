"""
聚合层：将 extraction 的 state_candidates 聚合到 states/state_evidence。
"""
import json
import logging
import re
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app_logging import get_logger, log_event
from layers.middle_layer import (
    ExtractionResult,
    add_retrieval_candidate,
    archive_orphan_states,
    ensure_state_evidence,
    get_context_only_source_block_texts,
    get_extractions_for_aggregation,
    record_state_candidate_support,
    upsert_state,
)


logger = get_logger("aggregator")

VALID_CATEGORIES = {"dynamic", "static"}
DEFAULT_SUBTYPE_BY_CATEGORY = {
    "dynamic": "active_interest",
    "static": "background",
}
SUPPORTED_SUBTYPES = {
    "ongoing_project": "dynamic",
    "recent_event": "dynamic",
    "pending_task": "dynamic",
    "active_interest": "dynamic",
    "preference": "static",
    "background": "static",
    "skill": "static",
    "relationship": "static",
}
SUPPORTED_SUBJECT_TYPES = {"person", "team", "project", "organization"}
SUBTYPE_ALIASES = {
    "ongoing_learning": "active_interest",
    "interest": "active_interest",
    "other": "",
}
SUPPORT_EXTRACT_SUPPORTED = "extract_supported"
SUPPORT_CONTEXT_ONLY_ONLY = "context_only_only"
SUPPORT_NO_TEXT_SUPPORT = "no_text_support"
REJECT_INVALID_CANDIDATE = "invalid_candidate"
REJECT_MISSING_SUBJECT = "missing_subject"
REJECT_NO_TEXT_SUPPORT = "no_text_support"
REJECT_CONTEXT_ONLY_ONLY = "context_only_only"
ACCEPT_REASON = "accepted"
TEXT_SIGNAL_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]")
ASCII_WORD_RE = re.compile(r"[a-z0-9][a-z0-9_+#.-]{2,}")
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "正在",
    "已经",
    "需要",
    "当前",
    "进行",
    "完成",
}


def _clean_text(value: Optional[str], limit: Optional[int] = None) -> Optional[str]:
    """压缩空白并截断文本。"""
    if value is None:
        return None

    text = " ".join(str(value).split())
    if not text:
        return None

    if limit is not None and len(text) > limit:
        text = text[: limit - 3].rstrip() + "..."

    return text


def _normalize_confidence(value: Any) -> float:
    """保证置信度位于 0-1 之间。"""
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, min(1.0, confidence))


def _normalize_category_and_subtype(
    category: Optional[str],
    subtype: Optional[str],
) -> tuple[str, str]:
    """将候选 category/subtype 规范化到输出层支持的词表。"""
    raw_subtype = _clean_text(subtype)
    normalized_subtype = raw_subtype.lower() if raw_subtype else ""
    mapped_subtype = SUBTYPE_ALIASES.get(normalized_subtype, normalized_subtype)

    if mapped_subtype in SUPPORTED_SUBTYPES:
        return SUPPORTED_SUBTYPES[mapped_subtype], mapped_subtype

    raw_category = _clean_text(category)
    normalized_category = raw_category.lower() if raw_category else ""
    normalized_category = (
        normalized_category if normalized_category in VALID_CATEGORIES else "dynamic"
    )

    return normalized_category, DEFAULT_SUBTYPE_BY_CATEGORY[normalized_category]


def _normalize_subject(
    candidate: Any,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Normalize subject clues, preserving legacy candidates with no subject."""
    subject_type = _clean_text(getattr(candidate, "subject_type", None))
    subject_key = _clean_text(getattr(candidate, "subject_key", None), limit=120)

    if subject_type is None:
        return None, None, None

    normalized_subject_type = subject_type.lower()
    if normalized_subject_type not in SUPPORTED_SUBJECT_TYPES:
        return None, None, REJECT_MISSING_SUBJECT

    if subject_key is None:
        return None, None, REJECT_MISSING_SUBJECT

    return normalized_subject_type, subject_key, None


def _validate_and_normalize_state_candidate(
    candidate: Any,
) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Normalize candidate fields and return a candidate-level rejection reason."""
    subject_type, subject_key, subject_error = _normalize_subject(candidate)
    if subject_error:
        return None, subject_error

    summary = _clean_text(getattr(candidate, "summary", None), limit=200)
    if not summary:
        return None, REJECT_INVALID_CANDIDATE
    canonical_summary = (
        _clean_text(getattr(candidate, "canonical_summary", None), limit=200)
        or summary
    )
    display_summary = (
        _clean_text(getattr(candidate, "display_summary", None), limit=200)
        or summary
    )

    category, subtype = _normalize_category_and_subtype(
        getattr(candidate, "category", None),
        getattr(candidate, "subtype", None),
    )
    detail = _clean_text(getattr(candidate, "detail", None), limit=500)
    if detail in {summary, canonical_summary, display_summary}:
        detail = None

    return {
        "category": category,
        "subtype": subtype,
        "summary": display_summary,
        "canonical_summary": canonical_summary,
        "display_summary": display_summary,
        "subject_type": subject_type,
        "subject_key": subject_key,
        "detail": detail,
        "confidence": _normalize_confidence(getattr(candidate, "confidence", 1.0)),
    }, None


def _normalize_state_candidate(candidate: Any) -> Optional[Dict[str, Any]]:
    """将 StateCandidate 规范化为 states 表可用字段。"""
    normalized, _ = _validate_and_normalize_state_candidate(candidate)
    return normalized


def _normalize_retrieval_candidate(candidate: Any) -> Optional[Dict[str, Any]]:
    """Normalize RetrievalCandidate for the pending candidate pool."""
    surface_form = _clean_text(getattr(candidate, "surface_form", None), limit=200)
    if not surface_form:
        return None

    return {
        "surface_form": surface_form,
        "type_guess": _clean_text(getattr(candidate, "type_guess", None), limit=80),
        "scope_guess": _clean_text(getattr(candidate, "context", None), limit=200),
        "priority": _normalize_retrieval_priority(
            getattr(candidate, "priority", 0)
        ),
    }


def _normalize_retrieval_priority(value: Any) -> int:
    """Clamp retrieval priority to the documented 0-10 range."""
    try:
        priority = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(10, priority))


def _prepare_support_phrase(value: Optional[str], limit: int = 160) -> Optional[str]:
    text = _clean_text(value, limit=limit)
    if not text:
        return None
    if not TEXT_SIGNAL_RE.search(text):
        return None
    if len(text) < 2:
        return None
    if text.isascii() and len(text) < 3:
        return None
    return text


def _dedupe_phrases(phrases: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for phrase in phrases:
        key = phrase.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(phrase)
    return deduped


def _candidate_support_phrases(candidate: Any) -> tuple[list[str], list[str]]:
    subject_phrases = []
    subject_key = _prepare_support_phrase(getattr(candidate, "subject_key", None))
    if subject_key:
        subject_phrases.append(subject_key)

    core_phrases = []
    for field_name in (
        "summary",
        "canonical_summary",
        "display_summary",
        "detail",
    ):
        phrase = _prepare_support_phrase(getattr(candidate, field_name, None))
        if phrase:
            core_phrases.append(phrase)

    return _dedupe_phrases(subject_phrases), _dedupe_phrases(core_phrases)


def _normalize_for_match(text: str) -> str:
    return " ".join(str(text).casefold().split())


def _keywords(text: str) -> set[str]:
    normalized = _normalize_for_match(text)
    keywords = {
        token
        for token in ASCII_WORD_RE.findall(normalized)
        if token not in STOPWORDS
    }
    for sequence in re.findall(r"[\u4e00-\u9fff]{3,}", normalized):
        if len(sequence) <= 8:
            keywords.add(sequence)
        else:
            keywords.update(
                sequence[index : index + 3]
                for index in range(0, len(sequence) - 2)
                if sequence[index : index + 3] not in STOPWORDS
            )
    return keywords


def _text_contains_phrase_or_keywords(text: str, phrase: str) -> bool:
    haystack = _normalize_for_match(text)
    needle = _normalize_for_match(phrase)
    if not haystack or not needle:
        return False
    if needle in haystack:
        return True

    phrase_keywords = _keywords(needle)
    if not phrase_keywords:
        return False

    overlap = phrase_keywords & _keywords(haystack)
    if len(overlap) >= 2:
        return True
    return any(len(token) >= 8 for token in overlap)


def _has_candidate_text_support(candidate: Any, text: str) -> bool:
    """Return true only when non-subject candidate clues are present."""
    if not text:
        return False

    subject_phrases, core_phrases = _candidate_support_phrases(candidate)
    if any(
        _text_contains_phrase_or_keywords(text, phrase)
        for phrase in core_phrases
    ):
        return True

    subject_match = any(
        _text_contains_phrase_or_keywords(text, phrase)
        for phrase in subject_phrases
    )
    if not subject_match:
        return False

    subject_keywords = set()
    for phrase in subject_phrases:
        subject_keywords.update(_keywords(phrase))
    text_keywords = _keywords(text)
    for phrase in core_phrases:
        core_keywords = _keywords(phrase) - subject_keywords
        if core_keywords & text_keywords:
            return True
    return False


def _context_text_for_candidate_support(
    extraction: ExtractionResult,
    row: Dict[str, Any],
) -> str:
    previews = [
        block.text_preview
        for block in extraction.context.source_context_blocks
        if block.text_preview
    ]
    if previews:
        return "\n\n".join(previews)

    fallback_texts = get_context_only_source_block_texts(
        document_id=row["document_id"],
        section_label=row.get("section_label"),
    )
    return "\n\n".join(fallback_texts)


def _evaluate_candidate_text_support(
    candidate: Any,
    *,
    chunk_text: str,
    context_text: str,
) -> str:
    if _has_candidate_text_support(candidate, chunk_text):
        return SUPPORT_EXTRACT_SUPPORTED
    if _has_candidate_text_support(candidate, context_text):
        return SUPPORT_CONTEXT_ONLY_ONLY
    return SUPPORT_NO_TEXT_SUPPORT


def aggregate_extractions() -> Dict[str, int]:
    """读取 extractions 并聚合 state_candidates。"""
    stage_start = perf_counter()
    rows = get_extractions_for_aggregation()

    result = {
        "source_extractions": len(rows),
        "state_candidates": 0,
        "aggregated_candidates": 0,
        "accepted_candidates": 0,
        "supported_candidates": 0,
        "rejected_candidates": 0,
        "support_rejected_invalid": 0,
        "support_rejected_missing_subject": 0,
        "support_rejected_no_text_support": 0,
        "support_rejected_context_only_only": 0,
        "touched_states": 0,
        "evidence_added": 0,
        "invalid_extractions": 0,
        "skipped_candidates": 0,
        "retrieval_candidates": 0,
        "ensured_retrieval_candidates": 0,
        "skipped_retrieval_candidates": 0,
        "orphan_states_archived": 0,
    }

    if not rows:
        log_event(
            logger,
            logging.INFO,
            "aggregation_sources_empty",
            "No extractions available for aggregation",
            stage="aggregation",
            duration_ms=(perf_counter() - stage_start) * 1000,
        )
        return result

    touched_state_ids = set()

    for row in rows:
        try:
            payload = json.loads(row["extraction_json"] or "{}")
            extraction = ExtractionResult.from_dict(payload)
        except Exception as exc:
            result["invalid_extractions"] += 1
            log_event(
                logger,
                logging.WARNING,
                "aggregation_extraction_invalid",
                "Skipping invalid extraction payload during aggregation",
                stage="aggregation",
                extraction_id=row["extraction_id"],
                chunk_id=row["chunk_id"],
                path=row.get("path"),
                error_type=type(exc).__name__,
            )
            continue

        result["state_candidates"] += len(extraction.state_candidates)
        context_text = _context_text_for_candidate_support(extraction, row)

        for candidate_index, candidate in enumerate(extraction.state_candidates):
            normalized, rejection_reason = _validate_and_normalize_state_candidate(
                candidate
            )
            if rejection_reason:
                record_state_candidate_support(
                    extraction_id=row["extraction_id"],
                    candidate_index=candidate_index,
                    decision="reject",
                    reason=rejection_reason,
                    state_id=None,
                )
                result["rejected_candidates"] += 1
                result["skipped_candidates"] += 1
                if rejection_reason == REJECT_INVALID_CANDIDATE:
                    result["support_rejected_invalid"] += 1
                elif rejection_reason == REJECT_MISSING_SUBJECT:
                    result["support_rejected_missing_subject"] += 1
                continue

            support = _evaluate_candidate_text_support(
                candidate,
                chunk_text=row.get("chunk_text") or "",
                context_text=context_text,
            )
            if support == SUPPORT_CONTEXT_ONLY_ONLY:
                record_state_candidate_support(
                    extraction_id=row["extraction_id"],
                    candidate_index=candidate_index,
                    decision="reject",
                    reason=REJECT_CONTEXT_ONLY_ONLY,
                    state_id=None,
                )
                result["rejected_candidates"] += 1
                result["skipped_candidates"] += 1
                result["support_rejected_context_only_only"] += 1
                continue
            if support == SUPPORT_NO_TEXT_SUPPORT:
                record_state_candidate_support(
                    extraction_id=row["extraction_id"],
                    candidate_index=candidate_index,
                    decision="reject",
                    reason=REJECT_NO_TEXT_SUPPORT,
                    state_id=None,
                )
                result["rejected_candidates"] += 1
                result["skipped_candidates"] += 1
                result["support_rejected_no_text_support"] += 1
                continue
            if normalized is None:
                record_state_candidate_support(
                    extraction_id=row["extraction_id"],
                    candidate_index=candidate_index,
                    decision="reject",
                    reason=REJECT_INVALID_CANDIDATE,
                    state_id=None,
                )
                result["rejected_candidates"] += 1
                result["skipped_candidates"] += 1
                result["support_rejected_invalid"] += 1
                continue

            state_id = upsert_state(
                category=normalized["category"],
                subtype=normalized["subtype"],
                summary=normalized["summary"],
                detail=normalized["detail"],
                subject_type=normalized["subject_type"],
                subject_key=normalized["subject_key"],
                canonical_summary=normalized["canonical_summary"],
                display_summary=normalized["display_summary"],
                confidence=normalized["confidence"],
            )
            touched_state_ids.add(state_id)
            result["aggregated_candidates"] += 1
            result["accepted_candidates"] += 1
            result["supported_candidates"] += 1

            record_state_candidate_support(
                extraction_id=row["extraction_id"],
                candidate_index=candidate_index,
                decision="accept",
                reason=ACCEPT_REASON,
                state_id=state_id,
            )

            _, created = ensure_state_evidence(
                state_id=state_id,
                chunk_id=row["chunk_id"],
                extraction_id=row["extraction_id"],
                evidence_role="source",
                weight=normalized["confidence"],
                note=f"aggregated_state_candidate[{candidate_index}]",
            )
            if created:
                result["evidence_added"] += 1

        result["retrieval_candidates"] += len(extraction.retrieval_candidates)
        for candidate in extraction.retrieval_candidates:
            normalized_retrieval = _normalize_retrieval_candidate(candidate)
            if normalized_retrieval is None:
                result["skipped_retrieval_candidates"] += 1
                continue

            add_retrieval_candidate(
                surface_form=normalized_retrieval["surface_form"],
                type_guess=normalized_retrieval["type_guess"],
                scope_guess=normalized_retrieval["scope_guess"],
                source_chunk_ids=[row["chunk_id"]],
                priority=normalized_retrieval["priority"],
            )
            result["ensured_retrieval_candidates"] += 1

    result["touched_states"] = len(touched_state_ids)
    result["orphan_states_archived"] = archive_orphan_states()

    log_event(
        logger,
        logging.INFO,
        "aggregation_done",
        "Completed state aggregation",
        stage="aggregation",
        duration_ms=(perf_counter() - stage_start) * 1000,
        extractions=result["source_extractions"],
        state_candidates=result["state_candidates"],
        aggregated_candidates=result["aggregated_candidates"],
        touched_states=result["touched_states"],
        evidence_added=result["evidence_added"],
        invalid_extractions=result["invalid_extractions"],
        skipped_candidates=result["skipped_candidates"],
        accepted_candidates=result["accepted_candidates"],
        supported_candidates=result["supported_candidates"],
        rejected_candidates=result["rejected_candidates"],
        support_rejected_invalid=result["support_rejected_invalid"],
        support_rejected_missing_subject=result["support_rejected_missing_subject"],
        support_rejected_no_text_support=result["support_rejected_no_text_support"],
        support_rejected_context_only_only=result[
            "support_rejected_context_only_only"
        ],
        retrieval_candidates=result["retrieval_candidates"],
        ensured_retrieval_candidates=result["ensured_retrieval_candidates"],
        skipped_retrieval_candidates=result["skipped_retrieval_candidates"],
        orphan_states_archived=result["orphan_states_archived"],
    )
    return result
