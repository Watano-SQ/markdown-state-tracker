"""
Tests for middle-layer document completion and pending chunk recovery.
"""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import db.connection as db_connection
from db import close_connection, init_db
from layers.middle_layer import (
    ExtractionResult,
    get_state_candidate_supports,
    get_pending_chunks,
    mark_document_processed,
    record_state_candidate_support,
    save_extraction,
)


class MiddleLayerDocumentStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        base_dir = Path(__file__).parent / "data"
        base_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix="middle_layer_test_", suffix=".db", dir=base_dir)
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

    def seed_document_with_chunks(self, *, status: str = "pending") -> tuple[int, list[int]]:
        conn = db_connection.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO documents (path, title, modified_time, content_hash, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("partial.md", "Partial", 1.0, "hash-partial", status),
        )
        document_id = cursor.lastrowid

        chunk_ids: list[int] = []
        for index, text in enumerate(("first chunk", "second chunk")):
            cursor.execute(
                """
                INSERT INTO chunks (document_id, chunk_index, text, token_estimate)
                VALUES (?, ?, ?, ?)
                """,
                (document_id, index, text, 10),
            )
            chunk_ids.append(cursor.lastrowid)

        conn.commit()
        return document_id, chunk_ids

    def test_processed_document_with_missing_extraction_returns_to_pending_queue(self) -> None:
        _, chunk_ids = self.seed_document_with_chunks(status="processed")
        save_extraction(chunk_ids[0], ExtractionResult(), extractor_type="llm")

        pending = get_pending_chunks()

        self.assertEqual([row["id"] for row in pending], [chunk_ids[1]])

    def test_document_is_processed_only_after_all_chunks_have_extractions(self) -> None:
        document_id, chunk_ids = self.seed_document_with_chunks(status="pending")
        save_extraction(chunk_ids[0], ExtractionResult(), extractor_type="llm")

        completed = mark_document_processed(document_id)

        conn = db_connection.get_connection()
        status_after_partial = conn.execute(
            "SELECT status FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()["status"]

        self.assertFalse(completed)
        self.assertEqual(status_after_partial, "pending")
        self.assertEqual([row["id"] for row in get_pending_chunks()], [chunk_ids[1]])

        save_extraction(chunk_ids[1], ExtractionResult(), extractor_type="llm")
        completed = mark_document_processed(document_id)
        status_after_complete = conn.execute(
            "SELECT status FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()["status"]

        self.assertTrue(completed)
        self.assertEqual(status_after_complete, "processed")
        self.assertEqual(get_pending_chunks(), [])


class MiddleLayerSchemaMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        base_dir = Path(__file__).parent / "data"
        base_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix="middle_layer_migration_test_", suffix=".db", dir=base_dir)
        os.close(fd)
        self.temp_db_path = Path(temp_path)
        self.original_db_path = db_connection.DB_PATH

        close_connection()
        db_connection.DB_PATH = self.temp_db_path

    def tearDown(self) -> None:
        close_connection()
        db_connection.DB_PATH = self.original_db_path
        self.temp_db_path.unlink(missing_ok=True)

    def test_init_db_adds_state_identity_columns_to_existing_states_table(self) -> None:
        legacy_conn = sqlite3.connect(self.temp_db_path)
        try:
            legacy_conn.execute(
                """
                CREATE TABLE states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    subtype TEXT,
                    summary TEXT NOT NULL,
                    detail TEXT,
                    status TEXT DEFAULT 'active',
                    confidence REAL DEFAULT 1.0,
                    first_seen REAL DEFAULT (julianday('now')),
                    last_updated REAL DEFAULT (julianday('now'))
                )
                """
            )
            legacy_conn.commit()
        finally:
            legacy_conn.close()

        init_db()

        conn = db_connection.get_connection()
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(states)").fetchall()
        }
        indexes = {
            row["name"]
            for row in conn.execute("PRAGMA index_list(states)").fetchall()
        }
        support_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(state_candidate_supports)"
            ).fetchall()
        }
        support_indexes = {
            row["name"]
            for row in conn.execute(
                "PRAGMA index_list(state_candidate_supports)"
            ).fetchall()
        }
        view_row = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'view' AND name = 'v_state_candidate_support_trace'
            """
        ).fetchone()

        self.assertIn("subject_type", columns)
        self.assertIn("subject_key", columns)
        self.assertIn("canonical_summary", columns)
        self.assertIn("display_summary", columns)
        self.assertIn("idx_states_identity", indexes)
        self.assertIn("extraction_id", support_columns)
        self.assertIn("candidate_index", support_columns)
        self.assertIn("decision", support_columns)
        self.assertIn("reason", support_columns)
        self.assertIn("state_id", support_columns)
        self.assertIn("idx_state_candidate_supports_extraction", support_indexes)
        self.assertIn("idx_state_candidate_supports_state", support_indexes)
        self.assertIn("idx_state_candidate_supports_decision", support_indexes)
        self.assertIsNotNone(view_row)

    def test_state_candidate_support_recording_is_idempotent(self) -> None:
        init_db()
        conn = db_connection.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO documents (path, title, modified_time, content_hash, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("support-api.md", "Support API", 1.0, "hash-support-api", "processed"),
        )
        document_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO chunks (document_id, chunk_index, text, token_estimate)
            VALUES (?, ?, ?, ?)
            """,
            (document_id, 0, "Alice finished support trace implementation.", 10),
        )
        chunk_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO extractions (chunk_id, extraction_json, extractor_type)
            VALUES (?, ?, ?)
            """,
            (chunk_id, "{}", "llm"),
        )
        extraction_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO states (category, subtype, summary)
            VALUES (?, ?, ?)
            """,
            ("dynamic", "ongoing_project", "Alice finished support trace implementation"),
        )
        state_id = cursor.lastrowid
        conn.commit()

        first_id = record_state_candidate_support(
            extraction_id=extraction_id,
            candidate_index=0,
            decision="accept",
            reason="accepted",
            state_id=state_id,
        )
        second_id = record_state_candidate_support(
            extraction_id=extraction_id,
            candidate_index=0,
            decision="accept",
            reason="accepted",
            state_id=state_id,
        )
        supports = get_state_candidate_supports(extraction_id=extraction_id)

        self.assertEqual(first_id, second_id)
        self.assertEqual(len(supports), 1)
        self.assertEqual(supports[0]["decision"], "accept")
        self.assertEqual(supports[0]["reason"], "accepted")
        self.assertEqual(supports[0]["state_id"], state_id)


if __name__ == "__main__":
    unittest.main()
