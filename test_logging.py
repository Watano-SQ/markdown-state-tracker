"""
Tests for the block-style logging system.
"""
import logging
import os
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import List
from unittest.mock import MagicMock, patch

import main
from app_logging import (
    BACKUP_COUNT,
    BASE_LOGGER_NAME,
    MAX_LOG_BYTES,
    get_logger,
    log_event,
    setup_logging,
    shutdown_logging,
    summarize_text,
)
from layers.extractors.llm_extractor import LLMExtractor
from layers.middle_layer import Entity, ExtractionResult, StateCandidate


class LoggingSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        shutdown_logging()
        self.log_dir = Path(__file__).parent / "data" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"{self._testMethodName}.log"
        for candidate in self.log_dir.glob(f"{self._testMethodName}.log*"):
            candidate.unlink()

    def tearDown(self) -> None:
        shutdown_logging()
        for candidate in self.log_dir.glob(f"{self._testMethodName}.log*"):
            candidate.unlink()

    def read_log(self) -> str:
        shutdown_logging()
        return self.log_file.read_text(encoding="utf-8")

    def read_records(self) -> List[str]:
        content = self.read_log()
        return [record.strip() for record in content.split("\n\n") if record.strip()]

    def find_record(self, event: str) -> str:
        for record in reversed(self.read_records()):
            if f"event={event}" in record:
                return record
        self.fail(f"event={event} not found in log")

    def test_setup_logging_creates_rotating_file_and_block_header(self) -> None:
        run_id = setup_logging(self.log_file, level="INFO")
        logger = get_logger("test")
        log_event(logger, logging.INFO, "test_event", "hello log", stage="test", path="doc.md")

        base_logger = logging.getLogger(BASE_LOGGER_NAME)
        handlers = base_logger.handlers

        self.assertTrue(self.log_file.exists())
        self.assertTrue(any(handler.__class__.__name__ == "RotatingFileHandler" for handler in handlers))
        self.assertTrue(any(getattr(handler, "maxBytes", None) == MAX_LOG_BYTES for handler in handlers))
        self.assertTrue(any(getattr(handler, "backupCount", None) == BACKUP_COUNT for handler in handlers))

        record = self.find_record("test_event")
        lines = record.splitlines()

        self.assertRegex(lines[0], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \[INFO\] test event=test_event$")
        self.assertIn("context: run_id:", record)
        self.assertIn(run_id, record)
        self.assertIn("stage: test", record)
        self.assertIn("source: path: doc.md", record)
        self.assertIn("note: hello log", record)
        self.assertNotIn("|", record)
        self.assertNotIn("path=doc.md", record)

    def test_summarize_text_normalizes_and_truncates(self) -> None:
        text = "first line\n\nsecond line   third line " + ("X" * 160)
        summary = summarize_text(text, limit=40)

        self.assertNotIn("\n", summary)
        self.assertLessEqual(len(summary), 40)
        self.assertTrue(summary.endswith("..."))

    def test_preview_block_is_rendered_separately(self) -> None:
        setup_logging(self.log_file, level="INFO")
        logger = get_logger("test")
        long_preview = "preview " * 40

        log_event(
            logger,
            logging.INFO,
            "chunk_extract_start",
            "Starting chunk extraction",
            stage="extraction",
            chunk_id=31,
            chunk_index=2,
            path="article.md",
            text_preview=long_preview,
        )

        record = self.find_record("chunk_extract_start")
        lines = record.splitlines()

        self.assertIn("preview[text]:", record)
        self.assertNotIn("text_preview=", record)

        preview_index = lines.index("  preview[text]:")
        preview_lines = lines[preview_index + 1 :]
        self.assertGreaterEqual(len(preview_lines), 2)
        self.assertTrue(all(line.startswith("    ") for line in preview_lines))

    def test_run_pipeline_skip_extraction_logs_stage_events(self) -> None:
        setup_logging(self.log_file, level="INFO")

        pending_chunk = {
            "id": 11,
            "document_id": 7,
            "chunk_index": 0,
            "text": "hello world",
            "token_estimate": 8,
            "path": "demo.md",
            "title": "Demo",
        }

        with patch.object(main, "init_db"), \
             patch.object(main, "process_input", return_value={"total": 1, "new": 1, "modified": 0, "processed": [{"path": "demo.md", "is_new": True, "chunk_count": 1}]}), \
             patch.object(main, "get_pending_chunks", side_effect=[[pending_chunk], [pending_chunk]]), \
             patch.object(main, "aggregate_extractions", return_value={"source_extractions": 0, "state_candidates": 0, "aggregated_candidates": 0, "touched_states": 0, "evidence_added": 0, "invalid_extractions": 0, "skipped_candidates": 0, "orphan_states_archived": 0}), \
             patch.object(main, "get_stats", return_value={"documents": 1, "chunks": 1, "extractions": 0, "active_states": 0, "archived_states": 0, "pending_candidates": 0}), \
             patch.object(main, "generate_output", return_value={"snapshot_id": 3, "output_path": "output/status.md", "total_items": 0, "content_length": 42}):
            result = main.run_pipeline(verbose=False, skip_extraction=True)

        self.assertEqual(result["extraction"]["skipped"], 1)
        content = self.read_log()
        self.assertIn("event=run_start", content)
        self.assertIn("event=input_scan_done", content)
        self.assertIn("event=extraction_queue_loaded", content)
        self.assertIn("event=extraction_skipped", content)
        self.assertIn("event=aggregation_stage_done", content)
        self.assertIn("event=output_generate_done", content)
        self.assertIn("event=run_end", content)
        self.assertIn("\n\n", content)

    def test_missing_api_key_logs_skip_reason(self) -> None:
        setup_logging(self.log_file, level="INFO")
        pending = [{
            "id": 21,
            "document_id": 5,
            "chunk_index": 0,
            "text": "sample chunk",
            "token_estimate": 6,
            "path": "note.md",
            "title": "Note",
        }]

        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            result = main.run_extraction(pending, verbose=False)

        self.assertEqual(result["skipped"], 1)
        record = self.find_record("extraction_skipped")
        self.assertIn("note: Skipping extraction because API key is not configured", record)
        self.assertIn("stats: pending: 1", record)

    def test_llm_retry_logs_error_summary(self) -> None:
        setup_logging(self.log_file, level="INFO")

        extractor = object.__new__(LLMExtractor)
        extractor.config = SimpleNamespace(max_retries=2, timeout=1)
        extractor.model = "gpt-4o-mini"
        extractor.temperature = 0.1
        extractor.extra_body = None
        extractor.provider = "openai"
        extractor.client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=MagicMock(side_effect=RuntimeError("boom")))
            )
        )

        with patch("layers.extractors.llm_extractor.time.sleep"):
            with self.assertRaises(RuntimeError):
                extractor._call_llm_with_retry("prompt", log_context={"chunk_id": 99, "path": "retry.md"})

        retry_record = self.find_record("llm_request_retry")
        failed_record = self.find_record("llm_request_failed")

        self.assertIn("error: RuntimeError: boom", retry_record)
        self.assertIn("retry: attempt: 2/2, sleep: 2s", retry_record)
        self.assertIn("source: chunk: 99, path: retry.md", retry_record)
        self.assertIn("error: RuntimeError: boom", failed_record)
        self.assertIn("note: LLM request failed after all retries", failed_record)

    def test_chunk_extract_failed_includes_traceback_block(self) -> None:
        setup_logging(self.log_file, level="INFO")
        logger = get_logger("test")

        try:
            raise ValueError("broken chunk")
        except ValueError as exc:
            logger.exception(
                "Chunk extraction failed",
                extra={
                    "event": "chunk_extract_failed",
                    "stage": "extraction",
                    "error_type": type(exc).__name__,
                    "chunk_id": 41,
                    "chunk_index": 3,
                    "path": "broken.md",
                    "text_preview": "short preview",
                },
            )

        record = self.find_record("chunk_extract_failed")
        self.assertIn("error: ValueError: broken chunk", record)
        self.assertIn("traceback:", record)
        self.assertIn("ValueError: broken chunk", record)
        self.assertIn("preview[text]:", record)

    def test_run_start_stays_compact(self) -> None:
        setup_logging(self.log_file, level="INFO")
        logger = get_logger("pipeline")
        log_event(
            logger,
            logging.INFO,
            "run_start",
            "Pipeline run started",
            stage="pipeline",
            input_dir="input_docs",
            output_file="output/status.md",
        )

        record = self.find_record("run_start")
        lines = record.splitlines()

        self.assertTrue(re.match(r"^\d{4}-\d{2}-\d{2} ", lines[0]))
        self.assertIn("context: run_id:", record)
        self.assertIn("paths: input: input_docs, output_file: output/status.md", record)
        self.assertIn("note: Pipeline run started", record)
        self.assertNotIn("extra:", record)
        self.assertNotIn("preview[", record)
        self.assertNotIn("error:", record)

    def test_successful_chunk_extraction_logs_preview_and_counts(self) -> None:
        setup_logging(self.log_file, level="INFO")

        long_text = "chunk content " * 80
        pending = [{
            "id": 31,
            "document_id": 8,
            "chunk_index": 2,
            "text": long_text,
            "token_estimate": 180,
            "path": "article.md",
            "title": "Article",
        }]

        class DummyExtractor:
            def __init__(self) -> None:
                self.model = "gpt-4o-mini"
                self.provider = "openai"

            def extract(self, text, context, log_context=None):
                return ExtractionResult(
                    entities=[Entity(text="Python", type="tool")],
                    state_candidates=[StateCandidate(summary="testing logs", category="dynamic", subtype="pending_task")],
                )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False), \
             patch("layers.extractors.LLMExtractor", DummyExtractor), \
             patch.object(main, "save_extraction", return_value=123), \
             patch.object(main, "mark_document_processed"):
            result = main.run_extraction(pending, verbose=False)

        self.assertEqual(result["extracted"], 1)
        record = self.find_record("chunk_extract_done")
        self.assertIn("event=chunk_extract_done", record)
        self.assertIn("counts: entities: 1, states: 1", record)
        self.assertIn("preview[text]:", self.find_record("chunk_extract_start"))
        self.assertNotIn(long_text, self.read_log())


if __name__ == "__main__":
    unittest.main()
