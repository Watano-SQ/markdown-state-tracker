"""
聚合层：将 extraction 的 state_candidates 聚合到 states/state_evidence。
"""
import json
import logging
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app_logging import get_logger, log_event
from layers.middle_layer import (
    ExtractionResult,
    archive_orphan_states,
    ensure_state_evidence,
    get_extractions_for_aggregation,
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
SUBTYPE_ALIASES = {
    "ongoing_learning": "active_interest",
    "interest": "active_interest",
    "other": "",
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


def _normalize_state_candidate(candidate: Any) -> Optional[Dict[str, Any]]:
    """将 StateCandidate 规范化为 states 表可用字段。"""
    summary = _clean_text(getattr(candidate, "summary", None), limit=200)
    if not summary:
        return None

    category, subtype = _normalize_category_and_subtype(
        getattr(candidate, "category", None),
        getattr(candidate, "subtype", None),
    )
    detail = _clean_text(getattr(candidate, "detail", None), limit=500)
    if detail == summary:
        detail = None

    return {
        "category": category,
        "subtype": subtype,
        "summary": summary,
        "detail": detail,
        "confidence": _normalize_confidence(getattr(candidate, "confidence", 1.0)),
    }


def aggregate_extractions() -> Dict[str, int]:
    """读取 extractions 并聚合 state_candidates。"""
    stage_start = perf_counter()
    rows = get_extractions_for_aggregation()

    result = {
        "source_extractions": len(rows),
        "state_candidates": 0,
        "aggregated_candidates": 0,
        "touched_states": 0,
        "evidence_added": 0,
        "invalid_extractions": 0,
        "skipped_candidates": 0,
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

        if not extraction.state_candidates:
            continue

        result["state_candidates"] += len(extraction.state_candidates)

        for candidate_index, candidate in enumerate(extraction.state_candidates):
            normalized = _normalize_state_candidate(candidate)
            if normalized is None:
                result["skipped_candidates"] += 1
                continue

            state_id = upsert_state(
                category=normalized["category"],
                subtype=normalized["subtype"],
                summary=normalized["summary"],
                detail=normalized["detail"],
                confidence=normalized["confidence"],
            )
            touched_state_ids.add(state_id)
            result["aggregated_candidates"] += 1

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
        orphan_states_archived=result["orphan_states_archived"],
    )
    return result
