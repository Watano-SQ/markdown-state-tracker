"""
项目日志模块
"""
from __future__ import annotations

import json
import logging
import textwrap
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
from uuid import uuid4

from config import DEFAULT_LOG_FILE


BASE_LOGGER_NAME = "markdown_state_tracker"
MAX_LOG_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5
WRAP_WIDTH = 100
RUN_ID_CONTEXT: ContextVar[str] = ContextVar("markdown_state_tracker_run_id", default="-")

_STANDARD_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__.keys())
_CURRENT_LOG_FILE: Optional[Path] = None

FIELD_LABELS = {
    "run_id": "run_id",
    "stage": "stage",
    "document_id": "doc",
    "chunk_id": "chunk",
    "chunk_index": "index",
    "path": "path",
    "title": "title",
    "attempt": "attempt",
    "max_retries": "retries",
    "duration_ms": "duration",
    "sleep_seconds": "sleep",
    "model": "model",
    "provider": "provider",
    "temperature": "temp",
    "timeout": "timeout",
    "token_estimate": "tokens",
    "entity_count": "entities",
    "state_candidate_count": "states",
    "relation_candidate_count": "relations",
    "retrieval_candidate_count": "retrieval",
    "pending_chunks": "pending",
    "total_documents": "total_docs",
    "new_documents": "new",
    "modified_documents": "modified",
    "processed_documents": "processed",
    "total_items": "items",
    "snapshot_id": "snapshot",
    "extraction_id": "extraction",
    "prompt_chars": "prompt_chars",
    "response_chars": "response_chars",
    "db_path": "db",
    "output_path": "output",
    "input_dir": "input",
    "output_file": "output_file",
    "log_file": "log_file",
    "log_level": "log_level",
    "action": "action",
    "error_type": "type",
    "chunk_count": "chunks",
    "replaced_chunk_count": "replaced_chunks",
    "content_hash": "hash",
    "documents": "documents",
    "chunks": "chunks",
    "extractions": "extractions",
    "active_states": "active_states",
    "archived_states": "archived_states",
    "pending_candidates": "pending_candidates",
    "backup_count": "backup_count",
    "max_bytes": "max_bytes",
    "force": "force",
    "removed_existing": "removed_existing",
    "init": "init",
    "stats": "stats",
    "skip_extraction": "skip_extraction",
    "extracted": "extracted",
    "failed": "failed",
    "skipped": "skipped",
    "content_length": "content_length",
}

GROUP_LABELS = {
    "context": "context",
    "source": "source",
    "retry": "retry",
    "timing": "timing",
    "model": "model",
    "counts": "counts",
    "stats": "stats",
    "paths": "paths",
    "extra": "extra",
}

GROUP_FIELDS = {
    "context": ("run_id", "stage"),
    "source": ("document_id", "chunk_id", "chunk_index", "path", "title"),
    "retry": ("attempt", "max_retries", "sleep_seconds"),
    "timing": ("duration_ms", "timeout"),
    "model": ("model", "provider", "temperature", "token_estimate", "prompt_chars", "response_chars"),
    "counts": ("entity_count", "state_candidate_count", "relation_candidate_count", "retrieval_candidate_count"),
    "stats": (
        "pending_chunks",
        "total_documents",
        "new_documents",
        "modified_documents",
        "processed_documents",
        "total_items",
        "snapshot_id",
        "extraction_id",
        "action",
        "chunk_count",
        "replaced_chunk_count",
        "documents",
        "chunks",
        "extractions",
        "active_states",
        "archived_states",
        "pending_candidates",
        "content_hash",
        "log_level",
        "max_bytes",
        "backup_count",
        "force",
        "removed_existing",
        "init",
        "stats",
        "skip_extraction",
        "extracted",
        "failed",
        "skipped",
        "content_length",
    ),
    "paths": ("input_dir", "output_file", "db_path", "output_path", "log_file"),
}

PREVIEW_FIELDS = ("text_preview", "response_preview")
GENERIC_GROUP_SEQUENCE = ("context", "source", "retry", "timing", "model", "counts", "stats", "paths")

EVENT_TEMPLATES = {
    "chunk_extract_start": ("context", "source", "retry", "model", "stats"),
    "chunk_extract_done": ("context", "source", "timing", "model", "counts"),
    "chunk_extract_failed": ("context", "source", "timing", "model"),
    "llm_request_start": ("context", "source", "retry", "model"),
    "llm_request_done": ("context", "source", "retry", "timing", "model"),
    "llm_request_retry": ("context", "source", "retry", "timing", "model"),
    "llm_request_failed": ("context", "source", "retry", "model"),
    "run_start": ("context", "paths"),
    "run_end": ("context", "timing", "stats"),
    "run_failed": ("context", "timing"),
    "save_extraction_done": ("context", "source", "timing", "model", "counts", "stats"),
    "pending_chunks_loaded": ("context", "timing", "stats"),
    "extraction_queue_loaded": ("context", "stats"),
    "extraction_skipped": ("context", "stats"),
    "extraction_batch_done": ("context", "stats"),
    "input_scan_done": ("context", "timing", "stats"),
    "input_processing_done": ("context", "timing", "stats"),
    "middle_stats_collected": ("context", "stats"),
    "output_generate_done": ("context", "timing", "stats", "paths"),
    "output_generation_done": ("context", "timing", "stats", "paths"),
    "db_stats_collected": ("context", "timing", "stats"),
    "document_saved": ("context", "source", "timing", "stats"),
    "document_chunked": ("context", "source", "timing", "stats"),
    "document_scanned": ("context", "source", "stats"),
    "document_scan_done": ("context", "timing", "stats"),
    "document_changes_detected": ("context", "stats"),
    "states_selected_for_output": ("context", "timing", "stats"),
    "output_saved": ("context", "timing", "stats", "paths"),
    "db_connection_opened": ("context", "timing", "paths"),
    "db_connection_closed": ("context", "paths"),
    "db_schema_initialized": ("context", "timing", "stats", "paths"),
    "document_marked_processed": ("context", "source", "timing"),
    "extract_result_ready": ("context", "source", "timing", "counts"),
    "logging_configured": ("context", "stats", "paths"),
    "logging_shutdown": ("context", "paths"),
}


def summarize_text(text: Optional[str], limit: int = 120) -> str:
    """压缩空白并截断文本，用于日志预览。"""
    if not text:
        return ""

    compact = " ".join(str(text).split())
    if len(compact) <= limit:
        return compact
    if limit <= 3:
        return compact[:limit]
    return compact[: limit - 3] + "..."


def _coerce_log_value(value: Any) -> Any:
    """标准化日志字段值。"""
    if value is None:
        return None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        preview = items[:5]
        if len(items) > 5:
            preview.append(f"...(+{len(items) - 5})")
        return ",".join(str(item) for item in preview)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _format_inline_value(value: Any) -> str:
    text = str(_coerce_log_value(value))
    if any(ch.isspace() for ch in text):
        return json.dumps(text, ensure_ascii=False)
    return text


class ContextFilter(logging.Filter):
    """为所有日志记录补齐统一上下文字段。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = getattr(record, "run_id", RUN_ID_CONTEXT.get())
        record.event = getattr(record, "event", "-")
        record.stage = getattr(record, "stage", "-")
        return True


class ContextFormatter(logging.Formatter):
    """将日志渲染为多行块状文本。"""

    def _short_logger_name(self, record: logging.LogRecord) -> str:
        logger_name = record.name
        if logger_name.startswith(BASE_LOGGER_NAME + "."):
            return logger_name[len(BASE_LOGGER_NAME) + 1 :]
        if logger_name == BASE_LOGGER_NAME:
            return "root"
        return logger_name

    def _get_field(self, record: logging.LogRecord, field: str) -> Any:
        if not hasattr(record, field):
            return None
        value = _coerce_log_value(getattr(record, field))
        if value in (None, ""):
            return None
        return value

    def _format_value_for_field(self, field: str, value: Any) -> str:
        if field == "duration_ms":
            return f"{float(value):.2f}ms"
        if field == "sleep_seconds":
            return f"{value}s"
        if field == "timeout":
            return f"{value}s"
        return _format_inline_value(value)

    def _collect_pairs(
        self,
        record: logging.LogRecord,
        fields: Sequence[str],
        used_fields: set[str],
    ) -> List[Tuple[str, str]]:
        pairs: List[Tuple[str, str]] = []

        for field in fields:
            if field == "chunk_id":
                chunk_id = self._get_field(record, "chunk_id")
                if chunk_id is None or "chunk_id" in used_fields:
                    continue
                chunk_index = self._get_field(record, "chunk_index")
                chunk_value = f"{chunk_id}#{chunk_index}" if chunk_index is not None else chunk_id
                used_fields.add("chunk_id")
                if chunk_index is not None:
                    used_fields.add("chunk_index")
                pairs.append((FIELD_LABELS["chunk_id"], _format_inline_value(chunk_value)))
                continue

            if field == "attempt":
                attempt = self._get_field(record, "attempt")
                if attempt is None or "attempt" in used_fields:
                    continue
                max_retries = self._get_field(record, "max_retries")
                attempt_value = f"{attempt}/{max_retries}" if max_retries is not None else attempt
                used_fields.add("attempt")
                if max_retries is not None:
                    used_fields.add("max_retries")
                pairs.append((FIELD_LABELS["attempt"], _format_inline_value(attempt_value)))
                continue

            if field in {"chunk_index", "max_retries"} and field in used_fields:
                continue

            value = self._get_field(record, field)
            if value is None:
                continue

            used_fields.add(field)
            pairs.append((FIELD_LABELS.get(field, field), self._format_value_for_field(field, value)))

        return pairs

    def _render_group(self, group_name: str, pairs: Sequence[Tuple[str, str]]) -> Optional[str]:
        if not pairs:
            return None
        content = ", ".join(f"{label}: {value}" for label, value in pairs)
        return f"  {GROUP_LABELS[group_name]}: {content}"

    def _wrap_block_text(self, text: str, indent: str = "    ") -> List[str]:
        wrapper = textwrap.TextWrapper(
            width=WRAP_WIDTH,
            initial_indent=indent,
            subsequent_indent=indent,
            break_long_words=False,
            break_on_hyphens=False,
        )
        lines: List[str] = []
        for raw_line in str(text).splitlines() or [""]:
            if not raw_line:
                lines.append(indent.rstrip())
                continue
            lines.extend(wrapper.fill(raw_line).splitlines())
        return lines

    def _render_preview_lines(self, record: logging.LogRecord, used_fields: set[str]) -> List[str]:
        lines: List[str] = []
        for field in PREVIEW_FIELDS:
            value = self._get_field(record, field)
            if value is None:
                continue
            used_fields.add(field)
            preview_name = "text" if field == "text_preview" else "response"
            lines.append(f"  preview[{preview_name}]:")
            lines.extend(self._wrap_block_text(value))
        return lines

    def _render_error_line(self, record: logging.LogRecord, used_fields: set[str]) -> Optional[str]:
        error_type = self._get_field(record, "error_type")
        error_message = self._get_field(record, "error_message")
        exc_value = record.exc_info[1] if record.exc_info else None
        if error_type is None and error_message is None and exc_value is None:
            return None

        if error_type is not None:
            used_fields.add("error_type")
        if error_message is not None:
            used_fields.add("error_message")

        if exc_value is not None:
            error_text = f"{error_type or type(exc_value).__name__}: {exc_value}"
        elif error_type is not None and error_message is not None:
            error_text = f"{error_type}: {error_message}"
        elif error_type is not None:
            error_text = str(error_type)
        elif error_message is not None:
            error_text = str(error_message)
        else:
            error_text = str(exc_value)
        return f"  error: {error_text}"

    def _render_traceback_lines(self, record: logging.LogRecord) -> List[str]:
        if not record.exc_info:
            return []
        traceback_text = self.formatException(record.exc_info)
        lines = ["  traceback:"]
        lines.extend(self._wrap_block_text(traceback_text))
        return lines

    def _render_extra_line(self, record: logging.LogRecord, used_fields: set[str]) -> Optional[str]:
        extra_pairs: List[Tuple[str, str]] = []
        for key, value in sorted(record.__dict__.items()):
            if key in used_fields or key in _STANDARD_RECORD_FIELDS or key.startswith("_"):
                continue
            normalized = _coerce_log_value(value)
            if normalized in (None, ""):
                continue
            extra_pairs.append((FIELD_LABELS.get(key, key), _format_inline_value(normalized)))

        if not extra_pairs:
            return None
        return self._render_group("extra", extra_pairs)

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, self.datefmt)
        logger_name = self._short_logger_name(record)
        event_name = getattr(record, "event", "-")

        used_fields: set[str] = {"event"}
        lines = [f"{timestamp} [{record.levelname}] {logger_name} event={event_name}"]

        template_groups = EVENT_TEMPLATES.get(event_name, GENERIC_GROUP_SEQUENCE)
        for group_name in template_groups:
            pairs = self._collect_pairs(record, GROUP_FIELDS[group_name], used_fields)
            group_line = self._render_group(group_name, pairs)
            if group_line:
                lines.append(group_line)

        error_line = self._render_error_line(record, used_fields)
        if error_line:
            lines.append(error_line)

        lines.append(f"  note: {record.getMessage()}")
        lines.extend(self._render_preview_lines(record, used_fields))

        extra_line = self._render_extra_line(record, used_fields)
        if extra_line:
            lines.append(extra_line)

        lines.extend(self._render_traceback_lines(record))
        return "\n".join(lines) + "\n"


def _reset_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def setup_logging(
    log_file: Optional[Union[str, Path]] = None,
    level: str = "INFO",
    quiet: bool = False,
) -> str:
    """配置项目日志系统。"""
    del quiet  # quiet 只影响控制台摘要，不影响文件日志。

    global _CURRENT_LOG_FILE

    log_path = Path(log_file) if log_file else DEFAULT_LOG_FILE
    log_path.parent.mkdir(parents=True, exist_ok=True)

    run_id = uuid4().hex[:12]
    RUN_ID_CONTEXT.set(run_id)
    _CURRENT_LOG_FILE = log_path

    base_logger = logging.getLogger(BASE_LOGGER_NAME)
    _reset_handlers(base_logger)
    base_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    base_logger.propagate = False

    handler = RotatingFileHandler(
        filename=str(log_path),
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(base_logger.level)
    handler.addFilter(ContextFilter())
    handler.setFormatter(ContextFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
    base_logger.addHandler(handler)

    log_event(
        base_logger,
        logging.INFO,
        "logging_configured",
        "File logging configured",
        stage="logging",
        log_file=log_path,
        log_level=level.upper(),
        max_bytes=MAX_LOG_BYTES,
        backup_count=BACKUP_COUNT,
    )
    return run_id


def shutdown_logging() -> None:
    """关闭日志句柄。"""
    base_logger = logging.getLogger(BASE_LOGGER_NAME)
    if base_logger.handlers:
        log_event(
            base_logger,
            logging.INFO,
            "logging_shutdown",
            "Shutting down logging handlers",
            stage="logging",
            log_file=_CURRENT_LOG_FILE,
        )
    _reset_handlers(base_logger)


def get_logger(name: str) -> logging.Logger:
    """获取命名空间 logger。"""
    if not name:
        return logging.getLogger(BASE_LOGGER_NAME)
    return logging.getLogger(f"{BASE_LOGGER_NAME}.{name}")


def get_current_run_id() -> str:
    """返回当前运行的 run_id。"""
    return RUN_ID_CONTEXT.get()


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    message: str,
    *,
    stage: str,
    **fields: Any,
) -> None:
    """按统一格式写事件日志。"""
    extra: Dict[str, Any] = {"event": event, "stage": stage}
    for key, value in fields.items():
        normalized = _coerce_log_value(value)
        if normalized not in (None, ""):
            extra[key] = normalized
    logger.log(level, message, extra=extra)
