"""
Tests for output profile compatibility.
"""
import os
import tempfile
import unittest
from pathlib import Path

import db.connection as db_connection
from db import close_connection, init_db
from layers.output_layer import DEFAULT_PROFILE_NAME, generate_output, get_output_profile


class OutputLayerProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        base_dir = Path(__file__).parent / "data"
        base_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix="output_layer_test_", suffix=".db", dir=base_dir)
        os.close(fd)
        self.temp_db_path = Path(temp_path)
        self.base_dir = base_dir
        self.temp_output_paths: list[Path] = []
        self.original_db_path = db_connection.DB_PATH

        close_connection()
        db_connection.DB_PATH = self.temp_db_path
        init_db()
        self.seed_state()

    def tearDown(self) -> None:
        close_connection()
        db_connection.DB_PATH = self.original_db_path
        self.temp_db_path.unlink(missing_ok=True)
        for output_path in self.temp_output_paths:
            output_path.unlink(missing_ok=True)

    def make_output_path(self, suffix: str) -> Path:
        fd, temp_path = tempfile.mkstemp(
            prefix="output_layer_status_",
            suffix=suffix,
            dir=self.base_dir,
        )
        os.close(fd)
        output_path = Path(temp_path)
        self.temp_output_paths.append(output_path)
        return output_path

    def seed_state(self) -> None:
        conn = db_connection.get_connection()
        conn.execute(
            """
            INSERT INTO states (
                category,
                subtype,
                subject_type,
                subject_key,
                canonical_summary,
                display_summary,
                summary,
                detail,
                confidence,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "dynamic",
                "active_interest",
                "person",
                "alice",
                "learn output profiles",
                "Alice is validating the default output profile",
                "Alice validates output profile plumbing",
                "Profile output should still use the existing status document shape.",
                0.9,
                "active",
            ),
        )
        conn.commit()

    def test_generate_output_uses_default_profile_when_omitted(self) -> None:
        output_path = self.make_output_path("-default.md")

        result = generate_output(output_path=output_path)

        self.assertEqual(result["profile"], DEFAULT_PROFILE_NAME)
        self.assertEqual(result["output_path"], str(output_path))
        self.assertEqual(result["total_items"], 1)
        self.assertTrue(output_path.exists())
        self.assertIn(
            "Alice is validating the default output profile",
            output_path.read_text(encoding="utf-8"),
        )

    def test_generate_output_accepts_explicit_default_profile(self) -> None:
        output_path = self.make_output_path("-explicit.md")

        result = generate_output(
            profile_name=DEFAULT_PROFILE_NAME,
            output_path=output_path,
        )

        self.assertEqual(result["profile"], DEFAULT_PROFILE_NAME)
        self.assertEqual(result["total_items"], 1)
        self.assertTrue(output_path.exists())

    def test_unknown_output_profile_fails_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown output profile"):
            get_output_profile("missing")


if __name__ == "__main__":
    unittest.main()
