"""Test the grounding audit functions with hand-crafted fixtures.

Does not require a real database or LLM calls.
Validates audit diagnostic language, not pipeline correctness.
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

# ensure repo root and tools on path
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from tools.observation_support_audit import (  # noqa: E402
    _display,
    _iter_list,
    _normalize,
    _contains,
    _keywords,
    _keyword_overlap,
    _phrase_contains,
    _strong_overlap,
    _weak_overlap,
    _text_support_level,
    audit_candidate,
    audit_context_grounding,
    audit_event_grounding,
    audit_relation_grounding,
    audit_retrieval_grounding,
    audit_subject_grounding,
    audit_text_grounding,
    compute_admission_cross_check,
    compute_overall_grounding,
    connect_read_only,
)


# ── lightweight helpers tests ─────────────────────────────────────────────────


class TextHelperTests(unittest.TestCase):
    def test_normalize_none(self):
        self.assertEqual(_normalize(None), "")

    def test_normalize_string(self):
        self.assertEqual(_normalize("  Hello   World  "), "hello world")

    def test_normalize_cjk(self):
        self.assertIn("张三", _normalize("张三"))

    def test_contains_basic(self):
        self.assertTrue(_contains("Hello World", "hello"))

    def test_contains_none(self):
        self.assertFalse(_contains(None, "hello"))

    def test_contains_cjk(self):
        self.assertTrue(_contains("张三在推进项目", "张三"))

    def test_keywords_ascii(self):
        kw = _keywords("Markdown State Tracker output layer")
        self.assertIn("markdown", kw)
        self.assertIn("state", kw)

    def test_keywords_cjk(self):
        kw = _keywords("张三推进项目")
        self.assertTrue(any("张" in k for k in kw))

    def test_text_support_level_not_provided(self):
        self.assertEqual(_text_support_level("text", None), "not_provided")
        self.assertEqual(_text_support_level("text", ""), "not_provided")

    def test_text_support_level_strong(self):
        self.assertEqual(
            _text_support_level("张三推进输出层整理", "张三推进输出层整理"),
            "strong",
        )

    def test_text_support_level_weak(self):
        self.assertEqual(
            _text_support_level("张三推进输出层整理", "李四在写代码"),
            "none",
        )

    def test_phrase_contains_cjk_substring(self):
        self.assertTrue(_phrase_contains("张三在推进 Markdown State Tracker", "张三"))

    def test_strong_overlap_exact(self):
        self.assertTrue(_strong_overlap(
            "张三推进 Markdown State Tracker 输出层整理",
            "张三推进 Markdown State Tracker 输出层整理"
        ))


# ── Case A: 强支撑 ───────────────────────────────────────────────────────────


class CaseAStrongSupportTests(unittest.TestCase):
    """Candidate with subject, action, object all visible in chunk text,
    entities and events."""

    def setUp(self):
        self.chunk_text = (
            "张三最近在推进 Markdown State Tracker 的输出层整理工作。"
            "他计划在下周完成 ContextBundle 的重构。"
        )
        self.entities = [
            {"text": "张三", "type": "person", "context": "项目负责人", "confidence": 1.0},
            {"text": "Markdown State Tracker", "type": "project", "confidence": 1.0},
            {"text": "ContextBundle", "type": "concept", "confidence": 0.9},
        ]
        self.events = [
            {
                "description": "张三推进输出层整理",
                "time": {"normalized": "2026-05", "source": "inferred"},
                "participants": ["张三"],
                "confidence": 0.9,
            }
        ]
        self.relations = [
            {
                "source": "张三",
                "target": "Markdown State Tracker",
                "relation_type": "works_with",
                "confidence": 0.9,
            }
        ]
        self.retrievals: list[dict] = []
        self.context = {
            "document_title": "项目周记",
            "document_author": "张三",
            "document_time": {"normalized": "2026-05-01", "source": "explicit"},
            "section": "本周进展",
        }
        self.source_context_blocks: list[dict] = []

        self.candidate = {
            "summary": "张三正在推进 Markdown State Tracker 的输出层整理",
            "canonical_summary": "张三推进 MST 输出层",
            "display_summary": "输出层整理进行中",
            "detail": "张三计划在下周完成 ContextBundle 的重构",
            "category": "dynamic",
            "subtype": "ongoing_project",
            "subject_type": "person",
            "subject_key": "张三",
            "confidence": 0.9,
        }

    def test_subject_grounding_strong(self):
        result = audit_subject_grounding(
            self.candidate, self.chunk_text, self.entities,
            self.events, self.relations, self.context, self.source_context_blocks,
        )
        self.assertTrue(result["found_in_chunk_text"])
        self.assertTrue(result["found_in_entities"])
        self.assertTrue(result["found_in_event_participants"])
        self.assertTrue(result["found_in_relation_candidates"])
        self.assertFalse(result["found_only_in_context"])
        self.assertTrue(result["entity_type_matches_subject_type"])
        self.assertEqual(result["risk_flags"], [])

    def test_text_grounding_strong(self):
        result = audit_text_grounding(self.candidate, self.chunk_text)
        self.assertIn(result["summary_support"], ("strong",))
        # detail should have at least weak support
        self.assertIn(result["detail_support"], ("strong", "weak"))
        self.assertGreater(len(result["matched_terms"]), 0)

    def test_event_grounding_strong(self):
        result = audit_event_grounding(self.candidate, self.events, self.chunk_text)
        self.assertGreater(len(result["matched_event_indexes"]), 0)
        self.assertTrue(result["action_supported_by_event"])
        self.assertTrue(result["subject_supported_by_event_participants"])
        self.assertIn(result["event_support"], ("strong",))

    def test_relation_grounding_weak(self):
        result = audit_relation_grounding(self.candidate, self.relations)
        # relation exists but doesn't perfectly explain subtype
        self.assertIn(result["relation_support"], ("weak", "strong"))

    def test_overall_strong(self):
        subject_g = audit_subject_grounding(
            self.candidate, self.chunk_text, self.entities,
            self.events, self.relations, self.context, self.source_context_blocks,
        )
        text_g = audit_text_grounding(self.candidate, self.chunk_text)
        event_g = audit_event_grounding(self.candidate, self.events, self.chunk_text)
        relation_g = audit_relation_grounding(self.candidate, self.relations)
        retrieval_g = audit_retrieval_grounding(self.candidate, self.retrievals, self.chunk_text)
        context_g = audit_context_grounding(
            self.candidate, self.context, self.source_context_blocks, self.chunk_text,
        )
        overall = compute_overall_grounding(
            subject_g, text_g, event_g, relation_g, retrieval_g, context_g,
        )
        self.assertIn(overall["level"], ("strong", "medium"))


# ── Case B: context_only_only 风险 ────────────────────────────────────────────


class CaseBContextOnlyOnlyTests(unittest.TestCase):
    """Candidate whose core information appears only in source_context_blocks,
    not in chunk text."""

    def setUp(self):
        self.chunk_text = "本周天气晴朗，心情不错。"
        self.entities: list[dict] = []
        self.events: list[dict] = []
        self.relations: list[dict] = []
        self.retrievals: list[dict] = []
        self.context = {"document_title": "周记"}
        self.source_context_blocks = [
            {
                "source_block_id": 1,
                "source_type": "front_matter",
                "text_preview": "作者: 张三\n标题: Markdown State Tracker 输出层整理",
            }
        ]

        self.candidate = {
            "summary": "张三正在推进 Markdown State Tracker 输出层整理",
            "subject_type": "person",
            "subject_key": "张三",
            "category": "dynamic",
            "subtype": "ongoing_project",
            "detail": "输出层大规模重构",
        }

    def test_subject_only_in_context(self):
        result = audit_subject_grounding(
            self.candidate, self.chunk_text, self.entities,
            self.events, self.relations, self.context, self.source_context_blocks,
        )
        self.assertFalse(result["found_in_chunk_text"])
        self.assertTrue(result["found_in_context_only"])
        self.assertIn("subject_not_in_chunk_text", result["risk_flags"])

    def test_text_grounding_none(self):
        result = audit_text_grounding(self.candidate, self.chunk_text)
        self.assertEqual(result["summary_support"], "none")
        self.assertIn("summary_not_supported_by_chunk_text", result["risk_flags"])

    def test_context_only_support_only(self):
        result = audit_context_grounding(
            self.candidate, self.context, self.source_context_blocks, self.chunk_text,
        )
        self.assertTrue(result["uses_source_context_blocks"])
        self.assertEqual(result["context_only_support"], "only")
        self.assertIn("context_only_only", result["risk_flags"])

    def test_overall_risky(self):
        subject_g = audit_subject_grounding(
            self.candidate, self.chunk_text, self.entities,
            self.events, self.relations, self.context, self.source_context_blocks,
        )
        text_g = audit_text_grounding(self.candidate, self.chunk_text)
        event_g = audit_event_grounding(self.candidate, self.events, self.chunk_text)
        relation_g = audit_relation_grounding(self.candidate, self.relations)
        retrieval_g = audit_retrieval_grounding(self.candidate, self.retrievals, self.chunk_text)
        context_g = audit_context_grounding(
            self.candidate, self.context, self.source_context_blocks, self.chunk_text,
        )
        overall = compute_overall_grounding(
            subject_g, text_g, event_g, relation_g, retrieval_g, context_g,
        )
        self.assertIn(overall["level"], ("risky", "weak"))


# ── Case C: subject 只来自 document_author ────────────────────────────────────


class CaseCSubjectOnlyFromDocumentAuthorTests(unittest.TestCase):
    """Candidate whose subject_key matches document_author but is absent
    from chunk text and entities."""

    def setUp(self):
        self.chunk_text = "本周输出层整理取得了阶段性进展。"
        self.entities: list[dict] = []
        self.events: list[dict] = []
        self.relations: list[dict] = []
        self.retrievals: list[dict] = []
        self.context = {
            "document_title": "项目周记",
            "document_author": "张三",
        }
        self.source_context_blocks: list[dict] = []

        self.candidate = {
            "summary": "张三正在推进输出层整理",
            "subject_type": "person",
            "subject_key": "张三",
            "category": "dynamic",
            "subtype": "ongoing_project",
        }

    def test_found_only_in_context(self):
        result = audit_subject_grounding(
            self.candidate, self.chunk_text, self.entities,
            self.events, self.relations, self.context, self.source_context_blocks,
        )
        self.assertFalse(result["found_in_chunk_text"])
        self.assertFalse(result["found_in_entities"])
        self.assertTrue(result["found_only_in_context"])
        self.assertIn("document_author_used_as_subject_without_text_support", result["risk_flags"])

    def test_context_grounding_author_driven(self):
        result = audit_context_grounding(
            self.candidate, self.context, self.source_context_blocks, self.chunk_text,
        )
        self.assertTrue(result["uses_document_author"])
        self.assertIn("document_author_driven_subject", result["risk_flags"])

    def test_overall_risky_or_weak(self):
        subject_g = audit_subject_grounding(
            self.candidate, self.chunk_text, self.entities,
            self.events, self.relations, self.context, self.source_context_blocks,
        )
        text_g = audit_text_grounding(self.candidate, self.chunk_text)
        event_g = audit_event_grounding(self.candidate, self.events, self.chunk_text)
        relation_g = audit_relation_grounding(self.candidate, self.relations)
        retrieval_g = audit_retrieval_grounding(self.candidate, self.retrievals, self.chunk_text)
        context_g = audit_context_grounding(
            self.candidate, self.context, self.source_context_blocks, self.chunk_text,
        )
        overall = compute_overall_grounding(
            subject_g, text_g, event_g, relation_g, retrieval_g, context_g,
        )
        self.assertIn(overall["level"], ("risky", "weak"))


# ── Case D: event mismatch ────────────────────────────────────────────────────


class CaseDEventMismatchTests(unittest.TestCase):
    """Candidate claims '完成部署' but event only describes '阅读文档'."""

    def setUp(self):
        self.chunk_text = "今天阅读了 Rust 异步编程的官方文档，对 async trait 的设计有了更深入的理解。"
        self.entities = [
            {"text": "Rust", "type": "tool", "confidence": 1.0},
        ]
        self.events = [
            {
                "description": "阅读 Rust 异步编程文档",
                "time": {"normalized": "2026-05-08", "source": "explicit"},
                "participants": [],
                "confidence": 0.9,
            }
        ]
        self.relations: list[dict] = []
        self.retrievals: list[dict] = []
        self.context = {}
        self.source_context_blocks: list[dict] = []

        self.candidate = {
            "summary": "完成生产环境性能优化",
            "category": "dynamic",
            "subtype": "recent_event",
            "detail": "数据库查询延迟降低 80%",
            "subject_type": "project",
            "subject_key": "性能优化",
            "time": {"normalized": "2026-05-08", "source": "inferred"},
        }

    def test_event_action_mismatch(self):
        result = audit_event_grounding(self.candidate, self.events, self.chunk_text)
        self.assertIn("no_matching_event", result["risk_flags"])
        self.assertIn(result["event_support"], ("none", "weak"))

    def test_text_grounding_weak_or_none(self):
        result = audit_text_grounding(self.candidate, self.chunk_text)
        # "完成部署" is semantically different from "阅读...文档"
        self.assertIn(result["summary_support"], ("weak", "none"))
        if result["summary_support"] == "none":
            self.assertIn("summary_not_supported_by_chunk_text", result["risk_flags"])

    def test_overall_risky_or_inconsistent(self):
        subject_g = audit_subject_grounding(
            self.candidate, self.chunk_text, self.entities,
            self.events, self.relations, self.context, self.source_context_blocks,
        )
        text_g = audit_text_grounding(self.candidate, self.chunk_text)
        event_g = audit_event_grounding(self.candidate, self.events, self.chunk_text)
        relation_g = audit_relation_grounding(self.candidate, self.relations)
        retrieval_g = audit_retrieval_grounding(self.candidate, self.retrievals, self.chunk_text)
        context_g = audit_context_grounding(
            self.candidate, self.context, self.source_context_blocks, self.chunk_text,
        )
        overall = compute_overall_grounding(
            subject_g, text_g, event_g, relation_g, retrieval_g, context_g,
        )
        self.assertIn(overall["level"], ("risky", "inconsistent", "weak"))


# ── Case E: retrieval ambiguity ───────────────────────────────────────────────


class CaseERetrievalAmbiguityTests(unittest.TestCase):
    """Candidate uses a vague object reference that matches a retrieval_candidate."""

    def setUp(self):
        self.chunk_text = "那个项目最近进展不错，输出层已经基本稳定了。"
        self.entities: list[dict] = []
        self.events: list[dict] = []
        self.relations: list[dict] = []
        self.retrievals = [
            {
                "surface_form": "那个项目",
                "type_guess": "project",
                "context": "可能指 Markdown State Tracker",
                "priority": 5,
            }
        ]
        self.context = {}
        self.source_context_blocks: list[dict] = []

        self.candidate = {
            "summary": "那个项目的输出层已基本稳定",
            "category": "dynamic",
            "subtype": "ongoing_project",
            "subject_type": "project",
            "subject_key": "那个项目",
        }

    def test_has_ambiguity(self):
        result = audit_retrieval_grounding(self.candidate, self.retrievals, self.chunk_text)
        self.assertTrue(result["has_ambiguity"])
        self.assertTrue(result["ambiguity_affects_subject"])
        self.assertGreater(len(result["matched_retrieval_indexes"]), 0)

    def test_subject_grounding_ambiguous(self):
        result = audit_subject_grounding(
            self.candidate, self.chunk_text, self.entities,
            self.events, self.relations, self.context, self.source_context_blocks,
        )
        # "那个项目" is a vague reference
        self.assertTrue(result["found_in_chunk_text"])  # it IS in the text, but it's vague
        self.assertFalse(result["found_in_entities"])  # no disambiguating entity

    def test_context_grounding_no_context_only(self):
        result = audit_context_grounding(
            self.candidate, self.context, self.source_context_blocks, self.chunk_text,
        )
        self.assertEqual(result["context_only_support"], "none")

    def test_overall_risky_or_weak_or_medium(self):
        subject_g = audit_subject_grounding(
            self.candidate, self.chunk_text, self.entities,
            self.events, self.relations, self.context, self.source_context_blocks,
        )
        text_g = audit_text_grounding(self.candidate, self.chunk_text)
        event_g = audit_event_grounding(self.candidate, self.events, self.chunk_text)
        relation_g = audit_relation_grounding(self.candidate, self.relations)
        retrieval_g = audit_retrieval_grounding(self.candidate, self.retrievals, self.chunk_text)
        context_g = audit_context_grounding(
            self.candidate, self.context, self.source_context_blocks, self.chunk_text,
        )
        overall = compute_overall_grounding(
            subject_g, text_g, event_g, relation_g, retrieval_g, context_g,
        )
        # with ambiguity + text support, could be medium or risky
        self.assertIn(overall["level"], ("medium", "risky", "weak"))


# ── Admission cross-check tests ───────────────────────────────────────────────


class AdmissionCrossCheckTests(unittest.TestCase):
    def test_aligned_accept(self):
        result = compute_admission_cross_check("accept", "accepted", "strong")
        self.assertEqual(result["audit_judgment"], "aligned_accept")

    def test_aligned_reject(self):
        result = compute_admission_cross_check("reject", "context_only_only", "risky")
        self.assertEqual(result["audit_judgment"], "aligned_reject")

    def test_possible_false_accept(self):
        result = compute_admission_cross_check("accept", "accepted", "weak")
        self.assertEqual(result["audit_judgment"], "possible_false_accept")

    def test_possible_false_reject(self):
        result = compute_admission_cross_check("reject", "no_text_support", "strong")
        self.assertEqual(result["audit_judgment"], "possible_false_reject")

    def test_missing_admission_record(self):
        result = compute_admission_cross_check("missing", "", "medium")
        self.assertEqual(result["audit_judgment"], "missing_admission_record")


# ── Full audit_candidate integration tests (with DB for cross-check) ──────────


class AuditCandidateIntegrationTests(unittest.TestCase):
    """Test the full audit_candidate() flow including DB-based support rows."""

    def setUp(self):
        # create temp db with extractions + chunks + documents + supports tables
        fd, self.db_path = tempfile.mkstemp(
            prefix="audit_test_", suffix=".db", dir="tests/data"
        )
        os.close(fd)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_schema()
        self._seed_data()

    def _create_schema(self):
        self.conn.executescript("""
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                title TEXT,
                modified_time REAL DEFAULT (julianday('now')),
                content_hash TEXT,
                status TEXT DEFAULT 'pending'
            );
            CREATE TABLE chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL REFERENCES documents(id),
                chunk_index INTEGER NOT NULL,
                text TEXT,
                token_estimate INTEGER,
                start_offset INTEGER,
                end_offset INTEGER,
                section_label TEXT
            );
            CREATE TABLE extractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_id INTEGER NOT NULL REFERENCES chunks(id),
                extraction_json TEXT NOT NULL,
                extractor_type TEXT,
                model_name TEXT,
                prompt_version TEXT,
                created_at REAL DEFAULT (julianday('now'))
            );
            CREATE TABLE state_candidate_supports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                extraction_id INTEGER NOT NULL REFERENCES extractions(id),
                candidate_index INTEGER NOT NULL,
                decision TEXT NOT NULL CHECK(decision IN ('accept', 'reject')),
                reason TEXT NOT NULL,
                state_id INTEGER,
                created_at REAL DEFAULT (julianday('now')),
                UNIQUE(extraction_id, candidate_index)
            );
        """)

    def _seed_data(self):
        self.conn.execute(
            "INSERT INTO documents (id, path, title) VALUES (1, 'test.md', '测试文档')"
        )
        self.conn.execute(
            "INSERT INTO chunks (id, document_id, chunk_index, text) "
            "VALUES (1, 1, 0, '张三在推进 Markdown State Tracker 的输出层整理。')"
        )
        self.extraction_json = json.dumps({
            "context": {"document_title": "测试文档"},
            "entities": [{"text": "张三", "type": "person", "confidence": 1.0}],
            "events": [{
                "description": "推进输出层整理",
                "participants": ["张三"],
                "confidence": 0.9,
            }],
            "state_candidates": [{
                "summary": "张三正在推进输出层整理",
                "category": "dynamic",
                "subtype": "ongoing_project",
                "subject_type": "person",
                "subject_key": "张三",
                "detail": "输出层整理",
            }],
            "relation_candidates": [],
            "retrieval_candidates": [],
        })
        self.conn.execute(
            "INSERT INTO extractions (id, chunk_id, extraction_json) VALUES (1, 1, ?)",
            (self.extraction_json,),
        )
        # accepted support row
        self.conn.execute(
            "INSERT INTO state_candidate_supports "
            "(extraction_id, candidate_index, decision, reason, state_id) "
            "VALUES (1, 0, 'accept', 'accepted', 1)"
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        Path(self.db_path).unlink(missing_ok=True)

    def test_audit_candidate_with_support_row(self):
        row = self.conn.execute(
            "SELECT e.id as extraction_id, e.chunk_id, e.extraction_json, "
            "c.text as chunk_text, d.path as document_path "
            "FROM extractions e JOIN chunks c ON e.chunk_id=c.id "
            "JOIN documents d ON c.document_id=d.id WHERE e.id=1"
        ).fetchone()
        extraction_json = json.loads(row["extraction_json"])
        candidates = _iter_list(extraction_json.get("state_candidates"))

        support_row = {"decision": "accept", "reason": "accepted", "state_id": 1}

        result = audit_candidate(
            extraction_id=1,
            chunk_id=1,
            document_path="test.md",
            chunk_text=row["chunk_text"],
            extraction_json=extraction_json,
            candidate_index=0,
            candidate=candidates[0],
            support_row=support_row,
        )

        self.assertEqual(result["candidate_info"]["current_support_decision"], "accept")
        self.assertIn(
            result["overall_grounding"]["level"], ("strong", "medium")
        )
        self.assertEqual(
            result["admission_cross_check"]["audit_judgment"], "aligned_accept"
        )

    def test_audit_candidate_missing_support_row(self):
        row = self.conn.execute(
            "SELECT e.id as extraction_id, e.chunk_id, e.extraction_json, "
            "c.text as chunk_text, d.path as document_path "
            "FROM extractions e JOIN chunks c ON e.chunk_id=c.id "
            "JOIN documents d ON c.document_id=d.id WHERE e.id=1"
        ).fetchone()
        extraction_json = json.loads(row["extraction_json"])
        candidates = _iter_list(extraction_json.get("state_candidates"))

        result = audit_candidate(
            extraction_id=1,
            chunk_id=1,
            document_path="test.md",
            chunk_text=row["chunk_text"],
            extraction_json=extraction_json,
            candidate_index=0,
            candidate=candidates[0],
            support_row=None,
        )

        self.assertEqual(result["candidate_info"]["current_support_decision"], "missing")
        self.assertEqual(
            result["admission_cross_check"]["audit_judgment"],
            "missing_admission_record",
        )


if __name__ == "__main__":
    unittest.main()
