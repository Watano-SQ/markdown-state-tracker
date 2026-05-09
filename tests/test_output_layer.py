"""
Tests for output profile compatibility.
"""
import os
import tempfile
import unittest
from pathlib import Path
from typing import Optional

import db.connection as db_connection
from db import close_connection, init_db
from layers.output_layer import (
    DEFAULT_PROFILE_NAME,
    build_bundle_narratives,
    generate_output,
    generate_contextual_status_document,
    get_output_profile,
    select_context_bundles_for_output,
)


class FakeNarrativeClient:
    def __init__(self, response):
        self.response = response

    def create_narrative(self, payload):
        return self.response


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
        subject_type: Optional[str] = "project",
        subject_key: Optional[str] = "project-alpha",
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
        self.assertEqual(result["total_items"], 0)
        self.assertEqual(result["needs_context_items"], 1)
        self.assertTrue(output_path.exists())
        content = output_path.read_text(encoding="utf-8")
        self.assertIn("## 上下文报告", content)
        self.assertIn("*暂无可靠上下文*", content)
        self.assertNotIn("Alice is validating the default output profile", content)
        self.assertNotIn("## 待澄清", content)

    def test_generate_output_accepts_explicit_default_profile(self) -> None:
        output_path = self.make_output_path("-explicit.md")

        result = generate_output(
            profile_name=DEFAULT_PROFILE_NAME,
            output_path=output_path,
        )

        self.assertEqual(result["profile"], DEFAULT_PROFILE_NAME)
        self.assertEqual(result["total_items"], 0)
        self.assertEqual(result["needs_context_items"], 1)
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

    def test_context_bundles_merge_distant_chunks_with_strong_anchor(self) -> None:
        document_id = self.insert_document("input_docs/issue-alpha.md", "Issue Alpha")
        first_chunk_id = self.insert_chunk(
            document_id,
            0,
            "The team starts investigating issue #1260.",
            section_label="Start",
        )
        anchor_chunk_id = self.insert_chunk(
            document_id,
            5,
            "Later notes also mention issue #1260 as the same thread.",
            section_label="Middle",
        )
        final_chunk_id = self.insert_chunk(
            document_id,
            10,
            "The end of the document returns to issue #1260.",
            section_label="End",
        )
        first_state_id = self.insert_state(
            "Investigate issue #1260",
            subtype="recent_event",
            subject_type=None,
            subject_key=None,
        )
        final_state_id = self.insert_state(
            "Issue #1260 still needs follow-up",
            subtype="pending_task",
            subject_type=None,
            subject_key=None,
        )
        self.insert_evidence(first_state_id, first_chunk_id)
        self.insert_evidence(final_state_id, final_chunk_id)

        selection = select_context_bundles_for_output()

        matching_bundles = [
            bundle
            for bundle in selection.bundles
            if set(bundle.state_ids) == {first_state_id, final_state_id}
        ]
        self.assertEqual(len(matching_bundles), 1)
        bundle = matching_bundles[0]
        self.assertEqual(
            bundle.evidence_chunk_ids,
            [first_chunk_id, anchor_chunk_id, final_chunk_id],
        )
        self.assertIn("same_document_strong_anchor_context", bundle.merge_basis)
        self.assertTrue(
            any(
                basis.startswith("distant_strong_anchor:")
                for basis in bundle.merge_basis
            )
        )

    def test_context_bundles_do_not_merge_distant_chunks_without_anchor(self) -> None:
        document_id = self.insert_document("input_docs/no-anchor.md", "No Anchor")
        first_chunk_id = self.insert_chunk(
            document_id,
            0,
            "The first note is local and generic.",
            section_label="Start",
        )
        second_chunk_id = self.insert_chunk(
            document_id,
            10,
            "The final note is separate and generic.",
            section_label="End",
        )
        first_state_id = self.insert_state(
            "First generic note",
            subject_type=None,
            subject_key=None,
        )
        second_state_id = self.insert_state(
            "Second generic note",
            subject_type=None,
            subject_key=None,
        )
        self.insert_evidence(first_state_id, first_chunk_id)
        self.insert_evidence(second_state_id, second_chunk_id)

        selection = select_context_bundles_for_output()

        merged_state_sets = [set(bundle.state_ids) for bundle in selection.bundles]
        needs_context_ids = {item.state_id for item in selection.needs_context_items}
        self.assertNotIn({first_state_id, second_state_id}, merged_state_sets)
        self.assertTrue({first_state_id, second_state_id}.issubset(needs_context_ids))

    def test_context_bundles_complete_single_state_with_neighbor_chunk(self) -> None:
        document_id = self.insert_document("input_docs/neighbor.md", "Neighbor")
        source_chunk_id = self.insert_chunk(
            document_id,
            0,
            "A source state appears here.",
            section_label="Local",
        )
        neighbor_chunk_id = self.insert_chunk(
            document_id,
            1,
            "The adjacent chunk supplies local context.",
            section_label="Local",
        )
        state_id = self.insert_state(
            "Use local chunk context",
            subject_type=None,
            subject_key=None,
        )
        self.insert_evidence(state_id, source_chunk_id)

        selection = select_context_bundles_for_output()

        matching_bundles = [
            bundle for bundle in selection.bundles if bundle.state_ids == [state_id]
        ]
        self.assertEqual(len(matching_bundles), 1)
        bundle = matching_bundles[0]
        self.assertEqual(bundle.evidence_chunk_ids, [source_chunk_id, neighbor_chunk_id])
        self.assertIn("neighbor_chunk_context", bundle.merge_basis)

    def test_generate_output_renders_flat_reading_view(self) -> None:
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

        self.assertEqual(result["total_items"], 2)
        self.assertEqual(result["needs_context_items"], 1)
        self.assertEqual(result["diagnostics"]["bundle_count"], 1)
        self.assertEqual(result["topic_bundle_count"], 1)
        self.assertEqual(result["narrative_mode"], "rule")
        self.assertIn("## 上下文报告", content)
        self.assertIn("### project-alpha", content)
        self.assertIn("#### Project Alpha", content)
        self.assertIn("这是围绕Project Alpha的上下文", content)
        self.assertNotIn("##### 进展", content)
        self.assertNotIn("##### 下一步", content)
        self.assertNotIn("主要涉及：", content)
        self.assertNotIn("核心信息是：", content)
        self.assertNotIn("Rendering uses evidence backed bundles：", content)
        self.assertNotIn("置信度:", content)
        self.assertNotIn("- **", content)
        self.assertNotIn("## 待澄清", content)

    def test_contextual_output_splits_subject_into_topic_narratives(self) -> None:
        document_id = self.insert_document("input_docs/person-alpha.md", "Person Alpha")
        docker_chunk_id = self.insert_chunk(
            document_id,
            0,
            "Docker mirror configuration failed and needs another source.",
            section_label="Docker",
        )
        mcp_chunk_id = self.insert_chunk(
            document_id,
            1,
            "MCP client setup is being explored separately.",
            section_label="MCP",
        )
        docker_state_id = self.insert_state(
            "Docker mirror setup failed",
            subtype="recent_event",
            subject_type="person",
            subject_key="alice",
        )
        mcp_state_id = self.insert_state(
            "Explore MCP client setup",
            subtype="pending_task",
            subject_type="person",
            subject_key="alice",
        )
        self.insert_evidence(docker_state_id, docker_chunk_id)
        self.insert_evidence(mcp_state_id, mcp_chunk_id)
        output_path = self.make_output_path("-topics.md")

        result = generate_output(output_path=output_path)
        content = output_path.read_text(encoding="utf-8")

        self.assertEqual(result["bundle_count"], 1)
        self.assertEqual(result["topic_bundle_count"], 2)
        self.assertIn("### alice", content)
        self.assertIn("#### Docker", content)
        self.assertIn("#### MCP", content)
        self.assertNotIn("##### 问题", content)
        self.assertNotIn("##### 下一步", content)

    def test_reading_view_cleans_weak_topic_title(self) -> None:
        document_id = self.insert_document("input_docs/weak-title.md", "Weak Title Doc")
        chunk_id = self.insert_chunk(
            document_id,
            0,
            "工具：WhisperDesktop is being compared with another local tool.",
            section_label="工具：",
        )
        self.insert_chunk(
            document_id,
            1,
            "The adjacent context confirms this is a tool comparison.",
            section_label="工具：",
        )
        state_id = self.insert_state(
            "工具：",
            detail="WhisperDesktop 正在和其他本地转写工具比较。",
            subject_type="project",
            subject_key="weak-title",
        )
        self.insert_evidence(state_id, chunk_id)
        output_path = self.make_output_path("-weak-title.md")

        generate_output(output_path=output_path)
        content = output_path.read_text(encoding="utf-8")

        self.assertNotIn("#### 工具：", content)
        self.assertIn("WhisperDesktop 正在和其他本地转写工具比较。", content)

    def test_short_pragmatic_evaluation_is_not_low_information(self) -> None:
        document_id = self.insert_document(
            "input_docs/short-evaluation.md",
            "Short Evaluation",
        )
        chunk_id = self.insert_chunk(
            document_id,
            0,
            "WhisperDesktop，伟大。",
            section_label="WhisperDesktop",
        )
        self.insert_chunk(
            document_id,
            1,
            "Only adjacent context exists, with no tool comparison.",
            section_label="WhisperDesktop",
        )
        state_id = self.insert_state(
            "高度认可WhisperDesktop",
            detail="WhisperDesktop，伟大。",
            subject_type="project",
            subject_key="whisperdesktop-evaluation",
        )
        self.insert_evidence(state_id, chunk_id)
        output_path = self.make_output_path("-short-evaluation.md")

        result = generate_output(output_path=output_path)
        content = output_path.read_text(encoding="utf-8")

        self.assertIn("WhisperDesktop，伟大。", content)
        self.assertNotIn("高度认可WhisperDesktop：", content)
        self.assertNotIn("low_information", str(result["diagnostics"]))
        reading_roles = result["diagnostics"]["reading_roles"]
        self.assertEqual(reading_roles[state_id]["role"], "standalone")

    def test_short_sentence_without_subject_or_object_is_deferred(self) -> None:
        document_id = self.insert_document(
            "input_docs/short-vague.md",
            "Short Vague",
        )
        chunk_id = self.insert_chunk(
            document_id,
            0,
            "伟大。",
            section_label="杂记",
        )
        state_id = self.insert_state(
            "伟大",
            detail="伟大。",
            subject_type=None,
            subject_key=None,
        )
        self.insert_evidence(state_id, chunk_id)
        output_path = self.make_output_path("-short-vague.md")

        result = generate_output(output_path=output_path)
        content = output_path.read_text(encoding="utf-8")

        self.assertNotIn("伟大。", content)
        self.assertIn(state_id, {item.state_id for item in select_context_bundles_for_output().needs_context_items})
        reading_roles = result["diagnostics"]["reading_roles"]
        self.assertEqual(reading_roles[state_id]["role"], "defer")
        self.assertIn("缺少明确对象", reading_roles[state_id]["missing_signals"])

    def test_short_blocker_can_support_project_context(self) -> None:
        document_id = self.insert_document(
            "input_docs/aurora-board-blocker.md",
            "Aurora Board",
        )
        project_chunk_id = self.insert_chunk(
            document_id,
            0,
            "Aurora Board export debugging is the active project context.",
            section_label="Aurora Board",
        )
        blocker_chunk_id = self.insert_chunk(
            document_id,
            1,
            "导出又卡死。",
            section_label="Aurora Board",
        )
        project_state_id = self.insert_state(
            "Aurora Board export debugging",
            detail="Aurora Board 的导出调试正在推进。",
            subject_type="project",
            subject_key="aurora-board",
            subtype="ongoing_project",
        )
        blocker_state_id = self.insert_state(
            "导出又卡死",
            detail="导出又卡死。",
            subject_type=None,
            subject_key=None,
            subtype="recent_event",
        )
        self.insert_evidence(project_state_id, project_chunk_id)
        self.insert_evidence(blocker_state_id, blocker_chunk_id)

        selection = select_context_bundles_for_output()

        matching_bundles = [
            bundle
            for bundle in selection.bundles
            if set(bundle.state_ids) == {project_state_id, blocker_state_id}
        ]
        self.assertEqual(len(matching_bundles), 1)
        bundle = matching_bundles[0]
        self.assertIn(blocker_state_id, bundle.supporting_state_ids)
        self.assertIn("reading_cluster", bundle.merge_basis)
        self.assertEqual(
            selection.diagnostics["reading_roles"][blocker_state_id]["role"],
            "supporting",
        )

    def test_aurora_board_groups_primary_and_supporting_states(self) -> None:
        document_id = self.insert_document(
            "input_docs/aurora-board.md",
            "Aurora Board",
        )
        debug_chunk_id = self.insert_chunk(
            document_id,
            0,
            "Lin Qiao is debugging Aurora Board export failures.",
            section_label="Aurora Board",
        )
        rule_chunk_id = self.insert_chunk(
            document_id,
            1,
            "Nadia provided a renderer grouping rule for Aurora Board.",
            section_label="Aurora Board",
        )
        debug_state_id = self.insert_state(
            "Lin Qiao debugs Aurora Board export",
            detail="Lin Qiao 正在调试 Aurora Board 的导出问题。",
            subject_type="person",
            subject_key="lin-qiao",
            subtype="recent_event",
        )
        rule_state_id = self.insert_state(
            "Nadia renderer grouping rule",
            detail="Nadia 提供的 renderer grouping rule 支撑 Aurora Board 的排查上下文。",
            subject_type="person",
            subject_key="nadia",
            subtype="active_interest",
        )
        self.insert_evidence(debug_state_id, debug_chunk_id)
        self.insert_evidence(rule_state_id, rule_chunk_id)

        selection = select_context_bundles_for_output()

        matching_bundles = [
            bundle
            for bundle in selection.bundles
            if set(bundle.state_ids) == {debug_state_id, rule_state_id}
        ]
        self.assertEqual(len(matching_bundles), 1)
        bundle = matching_bundles[0]
        self.assertEqual(bundle.title, "Aurora Board")
        self.assertIn(debug_state_id, bundle.primary_state_ids)
        self.assertIn(rule_state_id, bundle.supporting_state_ids)
        self.assertIn(("person", "lin-qiao"), bundle.subject_identities)
        self.assertIn(("person", "nadia"), bundle.subject_identities)

    def test_river_incident_keeps_multiple_subjects_in_one_reading_cluster(self) -> None:
        document_id = self.insert_document(
            "input_docs/river-incident.md",
            "River import incident",
        )
        operations_chunk_id = self.insert_chunk(
            document_id,
            0,
            "The operations team triaged the River import incident.",
            section_label="River import incident",
        )
        incident_chunk_id = self.insert_chunk(
            document_id,
            1,
            "The River import incident remained active during the handoff.",
            section_label="River import incident",
        )
        import_team_chunk_id = self.insert_chunk(
            document_id,
            2,
            "The River import team prepared the recovery checklist.",
            section_label="River import incident",
        )
        operations_state_id = self.insert_state(
            "Operations team triaged River import incident",
            detail="operations team 正在分诊 River import incident。",
            subject_type="team",
            subject_key="operations-team",
            subtype="recent_event",
        )
        incident_state_id = self.insert_state(
            "River import incident remains active",
            detail="River import incident 在交接期间仍然活跃。",
            subject_type="event",
            subject_key="river-import-incident",
            subtype="ongoing_project",
        )
        import_team_state_id = self.insert_state(
            "River import team prepares recovery checklist",
            detail="River import team 准备恢复检查清单。",
            subject_type="team",
            subject_key="river-import-team",
            subtype="pending_task",
        )
        self.insert_evidence(operations_state_id, operations_chunk_id)
        self.insert_evidence(incident_state_id, incident_chunk_id)
        self.insert_evidence(import_team_state_id, import_team_chunk_id)

        selection = select_context_bundles_for_output()

        matching_bundles = [
            bundle
            for bundle in selection.bundles
            if set(bundle.state_ids)
            == {operations_state_id, incident_state_id, import_team_state_id}
        ]
        self.assertEqual(len(matching_bundles), 1)
        bundle = matching_bundles[0]
        self.assertEqual(bundle.title, "River import incident")
        self.assertIn(("team", "operations-team"), bundle.subject_identities)
        self.assertIn(("event", "river-import-incident"), bundle.subject_identities)
        self.assertIn(("team", "river-import-team"), bundle.subject_identities)

    def test_unrelated_sections_do_not_merge_across_subjects(self) -> None:
        document_id = self.insert_document(
            "input_docs/unrelated-sections.md",
            "Unrelated Sections",
        )
        docker_chunk_id = self.insert_chunk(
            document_id,
            0,
            "Docker mirror setup is being checked.",
            section_label="Docker",
        )
        mcp_chunk_id = self.insert_chunk(
            document_id,
            6,
            "MCP client setup is being checked separately.",
            section_label="MCP",
        )
        docker_state_id = self.insert_state(
            "Docker mirror setup",
            detail="Docker mirror setup is being checked.",
            subject_type="project",
            subject_key="docker",
        )
        mcp_state_id = self.insert_state(
            "MCP client setup",
            detail="MCP client setup is being checked separately.",
            subject_type="project",
            subject_key="mcp",
        )
        self.insert_evidence(docker_state_id, docker_chunk_id)
        self.insert_evidence(mcp_state_id, mcp_chunk_id)

        selection = select_context_bundles_for_output()

        merged_state_sets = [set(bundle.state_ids) for bundle in selection.bundles]
        self.assertNotIn({docker_state_id, mcp_state_id}, merged_state_sets)

    def test_evaluation_state_can_be_absorbed_with_tool_context(self) -> None:
        document_id = self.insert_document("input_docs/tool-context.md", "Tool Context")
        praise_chunk_id = self.insert_chunk(
            document_id,
            0,
            "WhisperDesktop is part of a local transcription comparison.",
            section_label="WhisperDesktop",
        )
        comparison_chunk_id = self.insert_chunk(
            document_id,
            1,
            "The comparison focuses on stability and replacement choices.",
            section_label="WhisperDesktop",
        )
        praise_state_id = self.insert_state(
            "高度认可WhisperDesktop",
            detail="WhisperDesktop 在本地转写比较中表现更稳定。",
            subject_type="project",
            subject_key="tool-context",
        )
        comparison_state_id = self.insert_state(
            "Compare transcription tools",
            detail="当前正在比较本地转写工具的稳定性和替代选择。",
            subject_type="project",
            subject_key="tool-context",
        )
        self.insert_evidence(praise_state_id, praise_chunk_id)
        self.insert_evidence(comparison_state_id, comparison_chunk_id)
        output_path = self.make_output_path("-tool-context.md")

        generate_output(output_path=output_path)
        content = output_path.read_text(encoding="utf-8")

        self.assertIn("WhisperDesktop 在本地转写比较中表现更稳定。", content)
        self.assertNotIn("高度认可WhisperDesktop：", content)

    def test_llm_narrative_uses_fake_client_without_real_api(self) -> None:
        document_id = self.insert_document("input_docs/llm-alpha.md", "LLM Alpha")
        chunk_id = self.insert_chunk(
            document_id,
            0,
            "The local evidence describes a narrative classifier.",
            section_label="Narrative",
        )
        self.insert_chunk(
            document_id,
            1,
            "Adjacent context keeps the single state in a reliable bundle.",
            section_label="Narrative",
        )
        state_id = self.insert_state(
            "Build narrative classifier",
            subject_type="project",
            subject_key="narrative-alpha",
        )
        self.insert_evidence(state_id, chunk_id)
        selection = select_context_bundles_for_output()
        fake_client = FakeNarrativeClient(
            {
                "topic_title": "LLM 叙事分类器",
                "bundle_summary": "该主题正在验证 LLM 分类器能否整理已有证据。",
                "sections": [
                    {
                        "kind": "current_goal",
                        "text": "验证 LLM 分类器整理已有证据。",
                        "source_state_ids": [state_id],
                    }
                ],
                "absorbed_state_ids": [state_id],
                "omitted_state_ids": [],
            }
        )

        narratives, diagnostics = build_bundle_narratives(
            selection,
            narrative_mode="llm",
            narrative_client=fake_client,
        )
        content = generate_contextual_status_document(
            selection,
            narrative_mode="llm",
            narrative_client=fake_client,
            narratives=narratives,
        )

        self.assertEqual(diagnostics["llm_success_count"], 1)
        self.assertIn("#### LLM 叙事分类器", content)
        self.assertIn("- 验证 LLM 分类器整理已有证据。", content)
        self.assertNotIn("##### 当前目标", content)
        self.assertNotIn("##### 问题", content)
        self.assertNotIn("置信度:", content)

    def test_llm_narrative_invalid_state_id_falls_back_to_rule(self) -> None:
        document_id = self.insert_document("input_docs/fallback-alpha.md", "Fallback Alpha")
        chunk_id = self.insert_chunk(
            document_id,
            0,
            "Fallback evidence can still render without LLM output.",
            section_label="Fallback",
        )
        self.insert_chunk(
            document_id,
            1,
            "Adjacent fallback context is available.",
            section_label="Fallback",
        )
        state_id = self.insert_state(
            "Fallback renders rule narrative",
            subject_type="project",
            subject_key="fallback-alpha",
        )
        self.insert_evidence(state_id, chunk_id)
        selection = select_context_bundles_for_output()
        fake_client = FakeNarrativeClient(
            {
                "topic_title": "Invalid LLM Topic",
                "bundle_summary": "This should not render.",
                "sections": [
                    {
                        "kind": "progress",
                        "text": "References an unknown state.",
                        "source_state_ids": [999],
                    }
                ],
                "absorbed_state_ids": [999],
                "omitted_state_ids": [],
            }
        )

        narratives, diagnostics = build_bundle_narratives(
            selection,
            narrative_mode="llm",
            narrative_client=fake_client,
        )
        content = generate_contextual_status_document(selection, narratives=narratives)

        self.assertEqual(diagnostics["llm_failure_count"], 1)
        self.assertEqual(diagnostics["fallback_count"], 1)
        self.assertIn("#### Fallback", content)
        self.assertNotIn("Invalid LLM Topic", content)

    def test_llm_narrative_empty_summary_falls_back_to_rule(self) -> None:
        document_id = self.insert_document("input_docs/empty-summary.md", "Empty Summary")
        chunk_id = self.insert_chunk(
            document_id,
            0,
            "The local evidence supports rule fallback.",
            section_label="Empty Summary",
        )
        self.insert_chunk(
            document_id,
            1,
            "Adjacent evidence keeps the bundle reliable.",
            section_label="Empty Summary",
        )
        state_id = self.insert_state(
            "Fallback from empty summary",
            subject_type="project",
            subject_key="empty-summary",
        )
        self.insert_evidence(state_id, chunk_id)
        selection = select_context_bundles_for_output()
        fake_client = FakeNarrativeClient(
            {
                "topic_title": "Empty Summary",
                "bundle_summary": "",
                "sections": [
                    {
                        "kind": "progress",
                        "text": "This should fall back.",
                        "source_state_ids": [state_id],
                    }
                ],
                "absorbed_state_ids": [state_id],
                "omitted_state_ids": [],
            }
        )

        narratives, diagnostics = build_bundle_narratives(
            selection,
            narrative_mode="llm",
            narrative_client=fake_client,
        )
        content = generate_contextual_status_document(selection, narratives=narratives)

        self.assertEqual(diagnostics["llm_failure_count"], 1)
        self.assertEqual(diagnostics["fallback_count"], 1)
        self.assertIn("#### Empty Summary", content)
        self.assertNotIn("This should fall back.", content)


if __name__ == "__main__":
    unittest.main()
