"""
Tests for middle-layer document completion and pending chunk recovery.
"""
import os
import tempfile
import unittest
from pathlib import Path

import db.connection as db_connection
from db import close_connection, init_db
from layers.middle_layer import (
    ExtractionResult,
    get_pending_chunks,
    mark_document_processed,
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


if __name__ == "__main__":
    unittest.main()
