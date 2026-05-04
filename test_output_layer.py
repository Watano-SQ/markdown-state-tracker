"""
Tests for output profile compatibility.
"""
import os
import tempfile
import unittest
from pathlib import Path

import db.connection as db_connection
from db import close_connection, init_db
from layers.output_layer import (
    DEFAULT_PROFILE_NAME,
    generate_output,
    get_output_profile,
    select_context_bundles_for_output,
)


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
        cursor = conn.execute(
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
        self.orphan_state_id = cursor.lastrowid
        conn.commit()

    def insert_document(self, path: str, title: str) -> int:
        conn = db_connection.get_connection()
        cursor = conn.execute(
            """
            INSERT INTO documents (path, title, modified_time, content_hash, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (path, title, 1.0, f"hash:{path}", "processed"),
        )
        conn.commit()
        return cursor.lastrowid

    def insert_chunk(
        self,
        document_id: int,
        chunk_index: int,
        text: str,
        section_label: str = "Project Alpha",
    ) -> int:
        conn = db_connection.get_connection()
        cursor = conn.execute(
            """
            INSERT INTO chunks (
                document_id,
                chunk_index,
                text,
                token_estimate,
                section_label
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (document_id, chunk_index, text, 20, section_label),
        )
        conn.commit()
        return cursor.lastrowid

    def insert_state(
        self,
        summary: str,
        subtype: str = "ongoing_project",
        subject_type: str = "project",
        subject_key: str = "project-alpha",
        detail: str = "Seeded contextual output state.",
    ) -> int:
        conn = db_connection.get_connection()
        cursor = conn.execute(
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
                subtype,
                subject_type,
                subject_key,
                summary.lower(),
                summary,
                summary,
                detail,
                0.8,
                "active",
            ),
        )
        conn.commit()
        return cursor.lastrowid

    def insert_evidence(self, state_id: int, chunk_id: int) -> int:
        conn = db_connection.get_connection()
        cursor = conn.execute(
            """
            INSERT INTO state_evidence (state_id, chunk_id, evidence_role, weight)
            VALUES (?, ?, ?, ?)
            """,
            (state_id, chunk_id, "source", 1.0),
        )
        conn.commit()
        return cursor.lastrowid

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
        self.assertIn("## 上下文报告", output_path.read_text(encoding="utf-8"))

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

    def test_context_bundles_group_adjacent_states_from_same_document(self) -> None:
        document_id = self.insert_document("input_docs/project-alpha.md", "Project Alpha")
        first_chunk_id = self.insert_chunk(
            document_id,
            0,
            "Project Alpha is moving through output bundle validation.",
        )
        second_chunk_id = self.insert_chunk(
            document_id,
            1,
            "Next step is switching the Markdown renderer.",
        )
        progress_state_id = self.insert_state(
            "Project Alpha validates contextual output",
            subtype="recent_event",
        )
        next_step_state_id = self.insert_state(
            "Switch Markdown renderer to bundles",
            subtype="pending_task",
        )
        self.insert_evidence(progress_state_id, first_chunk_id)
        self.insert_evidence(next_step_state_id, second_chunk_id)

        selection = select_context_bundles_for_output()

        matching_bundles = [
            bundle
            for bundle in selection.bundles
            if set(bundle.state_ids) == {progress_state_id, next_step_state_id}
        ]
        self.assertEqual(len(matching_bundles), 1)
        bundle = matching_bundles[0]
        self.assertEqual(bundle.title, "Project Alpha")
        self.assertEqual(bundle.source_document, "input_docs/project-alpha.md")
        self.assertEqual(bundle.evidence_chunk_ids, [first_chunk_id, second_chunk_id])
        self.assertEqual(bundle.sections, ["Project Alpha"])

    def test_context_bundles_do_not_merge_unrelated_documents(self) -> None:
        first_document_id = self.insert_document("input_docs/alpha.md", "Alpha")
        second_document_id = self.insert_document("input_docs/beta.md", "Beta")
        first_chunk_id = self.insert_chunk(
            first_document_id,
            0,
            "Alpha has a local implementation note.",
        )
        second_chunk_id = self.insert_chunk(
            second_document_id,
            0,
            "Beta has a separate planning note.",
            section_label="Beta",
        )
        first_state_id = self.insert_state(
            "Alpha implementation note",
            subject_key="project-alpha",
        )
        second_state_id = self.insert_state(
            "Beta planning note",
            subject_key="project-beta",
        )
        self.insert_evidence(first_state_id, first_chunk_id)
        self.insert_evidence(second_state_id, second_chunk_id)

        selection = select_context_bundles_for_output()

        merged_state_sets = [set(bundle.state_ids) for bundle in selection.bundles]
        self.assertNotIn({first_state_id, second_state_id}, merged_state_sets)

    def test_context_bundles_downgrade_states_without_evidence(self) -> None:
        selection = select_context_bundles_for_output()

        bundled_state_ids = {
            state_id
            for bundle in selection.bundles
            for state_id in bundle.state_ids
        }
        needs_context = {
            item.state_id: item.needs_context_reason
            for item in selection.needs_context_items
        }
        self.assertNotIn(self.orphan_state_id, bundled_state_ids)
        self.assertEqual(needs_context[self.orphan_state_id], "missing_evidence")

    def test_generate_output_renders_contextual_bundle_sections(self) -> None:
        document_id = self.insert_document("input_docs/render-alpha.md", "Render Alpha")
        first_chunk_id = self.insert_chunk(
            document_id,
            0,
            "Rendering has progress evidence.",
        )
        second_chunk_id = self.insert_chunk(
            document_id,
            1,
            "The next task is covered by adjacent evidence.",
        )
        progress_state_id = self.insert_state(
            "Rendering uses evidence backed bundles",
            subtype="recent_event",
        )
        task_state_id = self.insert_state(
            "Review contextual report output",
            subtype="pending_task",
        )
        self.insert_evidence(progress_state_id, first_chunk_id)
        self.insert_evidence(task_state_id, second_chunk_id)
        output_path = self.make_output_path("-contextual.md")

        result = generate_output(output_path=output_path)
        content = output_path.read_text(encoding="utf-8")

        self.assertEqual(result["total_items"], 3)
        self.assertIn("## 上下文报告", content)
        self.assertIn("### Render Alpha", content)
        self.assertIn("#### 进展", content)
        self.assertIn("#### 下一步", content)
        self.assertIn("## 待澄清", content)


if __name__ == "__main__":
    unittest.main()
