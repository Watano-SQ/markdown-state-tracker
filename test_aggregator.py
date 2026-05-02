"""
Tests for state aggregation.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

import db.connection as db_connection
from db import close_connection, init_db
from layers.aggregator import aggregate_extractions
from layers.middle_layer import ExtractionResult, StateCandidate


class AggregatorTests(unittest.TestCase):
    def setUp(self) -> None:
        base_dir = Path(__file__).parent / "data"
        base_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix="aggregator_test_", suffix=".db", dir=base_dir)
        os.close(fd)
        self.temp_db_path = Path(temp_path)
        self.original_db_path = db_connection.DB_PATH

        close_connection()
        db_connection.DB_PATH = self.temp_db_path
        init_db()

    def tearDown(self) -> None:
        close_connection()
        db_connection.DB_PATH = self.original_db_path
        self.temp_db_path.unlink(missing_ok=True)

    def seed_extraction(
        self,
        *,
        summary: str,
        category: str = "dynamic",
        subtype: str = "ongoing_project",
        detail: str | None = None,
        confidence: float = 0.8,
        subject_type: str | None = None,
        subject_key: str | None = None,
    ) -> tuple[int, int]:
        conn = db_connection.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO documents (path, title, modified_time, content_hash, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("demo.md", "Demo", 1.0, "hash-demo", "processed"),
        )
        document_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO chunks (document_id, chunk_index, text, token_estimate)
            VALUES (?, ?, ?, ?)
            """,
            (document_id, 0, "demo chunk", 10),
        )
        chunk_id = cursor.lastrowid

        extraction = ExtractionResult(
            state_candidates=[
                StateCandidate(
                    summary=summary,
                    category=category,
                    subtype=subtype,
                    detail=detail,
                    confidence=confidence,
                    subject_type=subject_type,
                    subject_key=subject_key,
                )
            ]
        )
        cursor.execute(
            """
            INSERT INTO extractions (chunk_id, extraction_json, extractor_type, model_name, prompt_version)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                json.dumps(extraction.to_dict(), ensure_ascii=False),
                "llm",
                "test-model",
                "v-test",
            ),
        )
        extraction_id = cursor.lastrowid
        conn.commit()
        return chunk_id, extraction_id

    def test_aggregate_extractions_creates_state_and_evidence(self) -> None:
        chunk_id, extraction_id = self.seed_extraction(
            summary="  正在推进聚合实现  ",
            subtype="ongoing_project",
            detail="实现 state_candidates 到 states 的主链路",
            confidence=0.7,
        )

        result = aggregate_extractions()

        conn = db_connection.get_connection()
        state_row = conn.execute(
            "SELECT category, subtype, summary, detail, confidence FROM states"
        ).fetchone()
        evidence_row = conn.execute(
            "SELECT chunk_id, extraction_id FROM state_evidence"
        ).fetchone()

        self.assertEqual(result["source_extractions"], 1)
        self.assertEqual(result["aggregated_candidates"], 1)
        self.assertEqual(result["evidence_added"], 1)
        self.assertEqual(state_row["category"], "dynamic")
        self.assertEqual(state_row["subtype"], "ongoing_project")
        self.assertEqual(state_row["summary"], "正在推进聚合实现")
        self.assertEqual(state_row["detail"], "实现 state_candidates 到 states 的主链路")
        self.assertAlmostEqual(state_row["confidence"], 0.7)
        self.assertEqual(evidence_row["chunk_id"], chunk_id)
        self.assertEqual(evidence_row["extraction_id"], extraction_id)

    def test_aggregate_extractions_is_idempotent_for_existing_evidence(self) -> None:
        self.seed_extraction(summary="正在维护聚合结果", subtype="pending_task")

        first = aggregate_extractions()
        second = aggregate_extractions()

        conn = db_connection.get_connection()
        state_count = conn.execute("SELECT COUNT(*) FROM states").fetchone()[0]
        evidence_count = conn.execute("SELECT COUNT(*) FROM state_evidence").fetchone()[0]

        self.assertEqual(first["evidence_added"], 1)
        self.assertEqual(second["evidence_added"], 0)
        self.assertEqual(state_count, 1)
        self.assertEqual(evidence_count, 1)

    def test_aggregate_extractions_maps_legacy_subtype_to_supported_output_subtype(self) -> None:
        self.seed_extraction(
            summary="正在学习 Rust",
            category="dynamic",
            subtype="ongoing_learning",
        )

        aggregate_extractions()

        conn = db_connection.get_connection()
        state_row = conn.execute(
            "SELECT category, subtype FROM states"
        ).fetchone()

        self.assertEqual(state_row["category"], "dynamic")
        self.assertEqual(state_row["subtype"], "active_interest")

    def test_aggregate_extractions_rejects_explicit_unknown_subject(self) -> None:
        self.seed_extraction(
            summary="这是一条主体不明的教程建议",
            subject_type="unknown",
        )

        result = aggregate_extractions()

        conn = db_connection.get_connection()
        state_count = conn.execute("SELECT COUNT(*) FROM states").fetchone()[0]
        evidence_count = conn.execute("SELECT COUNT(*) FROM state_evidence").fetchone()[0]

        self.assertEqual(result["state_candidates"], 1)
        self.assertEqual(result["aggregated_candidates"], 0)
        self.assertEqual(result["skipped_candidates"], 1)
        self.assertEqual(state_count, 0)
        self.assertEqual(evidence_count, 0)

    def test_aggregate_extractions_requires_subject_key_when_subject_type_present(self) -> None:
        self.seed_extraction(
            summary="团队正在推进上线准备",
            subject_type="team",
        )

        result = aggregate_extractions()

        conn = db_connection.get_connection()
        state_count = conn.execute("SELECT COUNT(*) FROM states").fetchone()[0]

        self.assertEqual(result["aggregated_candidates"], 0)
        self.assertEqual(result["skipped_candidates"], 1)
        self.assertEqual(state_count, 0)


if __name__ == "__main__":
    unittest.main()
