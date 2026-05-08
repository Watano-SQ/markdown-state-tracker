"""
Tests for input-layer inclusion rules, structural source blocks, and chunk provenance.
"""
import os
import tempfile
import unittest
from pathlib import Path

import db.connection as db_connection
from db import close_connection, init_db
from layers.middle_layer import (
    ExtractionResult,
    ensure_state_evidence,
    save_extraction,
    upsert_state,
)
from layers.input_layer import (
    build_extraction_context_for_chunk,
    build_document_context,
    chunk_document,
    extract_document_context,
    process_input,
    should_include_document_path,
    split_document_into_source_blocks,
)


SAMPLE_PATH = Path(__file__).parent / "fixtures" / "source_context_sample.md"


class InputLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        fd, temp_db_path = tempfile.mkstemp(prefix="input_layer_", suffix=".db")
        os.close(fd)
        self.temp_db_path = Path(temp_db_path)
        self.original_db_path = db_connection.DB_PATH

        self.temp_input_dir = Path(tempfile.mkdtemp(prefix="input_docs_"))
        self.addCleanup(self._cleanup_temp_input_dir)

        close_connection()
        db_connection.DB_PATH = self.temp_db_path
        init_db()

    def tearDown(self) -> None:
        close_connection()
        db_connection.DB_PATH = self.original_db_path
        self.temp_db_path.unlink(missing_ok=True)

    def _cleanup_temp_input_dir(self) -> None:
        for path in sorted(self.temp_input_dir.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        self.temp_input_dir.rmdir()

    def write_input_doc(self, relative_path: str, content: str) -> Path:
        path = self.temp_input_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_sample_doc(self, relative_path: str = "source_context_sample.md") -> Path:
        return self.write_input_doc(relative_path, SAMPLE_PATH.read_text(encoding="utf-8"))

    def test_should_include_document_path_applies_explicit_rules(self) -> None:
        self.assertEqual(should_include_document_path("notes.md"), (True, None))
        self.assertEqual(should_include_document_path("AGENTS.md"), (False, "control_file"))
        self.assertEqual(should_include_document_path("test_fixture.md"), (False, "test_fixture"))
        self.assertEqual(
            should_include_document_path("fixtures/ignored.md"),
            (False, "fixture_directory"),
        )

    def test_structural_source_block_classification(self) -> None:
        content = """---
title: Demo
author: 测试者
updated_at: 2025-01-02
---

## 复盘
作者：陀思妥耶夫斯基
标题：卡拉马佐夫兄弟读书笔记

你可以先记录建议、步骤和配置，再决定是否采纳。

| 作者 | 观点 |
|------|------|
| 张三 | 表格里也可能是项目事实 |

> 引用材料不应被当作作者正文抽取。

```bash
python main.py --help
git status --short
```

{"kind": "structured"}

![](https://example.com/demo.png)

---
"""

        blocks = split_document_into_source_blocks(content)
        source_types = [block.source_type for block in blocks]

        self.assertEqual(blocks[0].source_type, "front_matter")
        self.assertEqual(blocks[0].include_decision, "context_only")
        self.assertIn("table_block", source_types)
        self.assertIn("quote_material", source_types)
        self.assertIn("structured_dump", source_types)
        self.assertIn("media_placeholder", source_types)
        self.assertNotIn("external_material", source_types)
        self.assertNotIn("metadata_table", source_types)
        self.assertNotIn("document_metadata", source_types)

        narrative_blocks = [
            block for block in blocks if block.source_type == "author_narrative"
        ]
        self.assertGreaterEqual(len(narrative_blocks), 2)
        self.assertTrue(any("作者：陀思妥耶夫斯基" in block.text for block in narrative_blocks))
        self.assertTrue(any("你可以先记录建议" in block.text for block in narrative_blocks))

    def test_extract_document_context_only_uses_front_matter(self) -> None:
        content = """---
title: Front Matter Title
author: Front Matter Author
created_at: 2025-01-01
---

| 作者 | 更新时间 |
|------|----------|
| Table Author | 2025-01-03 |

作者：正文作者
标题：正文标题
"""

        context = extract_document_context(content)

        self.assertEqual(context["document_title"], "Front Matter Title")
        self.assertEqual(context["document_author"], "Front Matter Author")
        self.assertEqual(context["document_time"]["normalized"], "2025-01-01")

        no_front_matter_context = extract_document_context(
            "作者：陀思妥耶夫斯基\n标题：读书笔记\n"
        )
        self.assertEqual(no_front_matter_context, {})

    def test_chunk_document_keeps_author_narrative_but_excludes_context_only(self) -> None:
        content = """---
title: Demo
author: 测试者
---

## 复盘
你可以把建议、步骤、配置先写下来，然后我再判断是否采用。

| 作者 | 事项 |
|------|------|
| 张三 | 推进输入层持久化 |

> 引用块只作为上下文。

```json
{"tool": "demo"}
```

![](https://example.com/demo.png)
"""

        chunks = chunk_document(content, max_tokens=200)
        chunk_text = "\n\n".join(chunk.text for chunk in chunks)

        self.assertIn("你可以把建议、步骤、配置先写下来", chunk_text)
        self.assertNotIn("| 作者 | 事项 |", chunk_text)
        self.assertNotIn("title: Demo", chunk_text)
        self.assertNotIn("引用块只作为上下文", chunk_text)
        self.assertNotIn('{"tool": "demo"}', chunk_text)
        self.assertNotIn("example.com/demo.png", chunk_text)

    def test_process_input_persists_source_blocks_and_chunk_mappings(self) -> None:
        self.write_sample_doc("demo.md")
        self.write_input_doc("AGENTS.md", "control file\n")

        result = process_input(self.temp_input_dir)

        conn = db_connection.get_connection()
        source_rows = conn.execute(
            """
            SELECT source_type, include_decision, text
            FROM source_blocks
            ORDER BY block_index
            """
        ).fetchall()
        chunk_rows = conn.execute(
            "SELECT id, text FROM chunks ORDER BY chunk_index"
        ).fetchall()
        mapping_rows = conn.execute(
            """
            SELECT csb.chunk_id, sb.source_type, csb.order_in_chunk
            FROM chunk_source_blocks csb
            JOIN source_blocks sb ON sb.id = csb.source_block_id
            ORDER BY csb.chunk_id, csb.order_in_chunk
            """
        ).fetchall()

        decisions = {row["source_type"]: row["include_decision"] for row in source_rows}
        source_types = [row["source_type"] for row in source_rows]
        chunk_text = "\n\n".join(row["text"] for row in chunk_rows)
        mapped_source_types = [row["source_type"] for row in mapping_rows]

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(decisions["front_matter"], "context_only")
        self.assertEqual(decisions["table_block"], "context_only")
        self.assertEqual(decisions["quote_material"], "context_only")
        self.assertEqual(decisions["structured_dump"], "exclude")
        self.assertEqual(decisions["media_placeholder"], "exclude")
        self.assertIn("author_narrative", source_types)
        self.assertIn("今天我完成了 include_decision", chunk_text)
        self.assertNotIn("| 作者 | 事项 |", chunk_text)
        self.assertNotIn("title: Source Context Sample", chunk_text)
        self.assertNotIn("这段引用提供背景", chunk_text)
        self.assertIn("author_narrative", mapped_source_types)
        self.assertNotIn("table_block", mapped_source_types)
        self.assertNotIn("front_matter", mapped_source_types)
        self.assertEqual(len(mapping_rows), len(mapped_source_types))

    def test_context_only_blocks_enter_extraction_context(self) -> None:
        self.write_sample_doc()
        process_input(self.temp_input_dir)

        chunk_row = dict(
            db_connection.get_connection()
            .execute(
                """
                SELECT c.id, c.document_id, c.section_label, d.path, d.title
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                """
            )
            .fetchone()
        )

        context = build_extraction_context_for_chunk(chunk_row)
        source_context_blocks = context["source_context_blocks"]
        source_types = {block["source_type"] for block in source_context_blocks}
        context_text = " ".join(block["text_preview"] for block in source_context_blocks)

        self.assertEqual(context["document_title"], "Source Context Sample")
        self.assertEqual(context["document_author"], "测试作者")
        self.assertEqual(context["document_time"]["normalized"], "2026-05-08")
        self.assertEqual(context["document_mode"], "personal")
        self.assertEqual(context["section"], "进展")
        self.assertIn("front_matter", source_types)
        self.assertIn("table_block", source_types)
        self.assertIn("quote_material", source_types)
        self.assertNotIn("structured_dump", source_types)
        self.assertNotIn("media_placeholder", source_types)
        self.assertIn("表格作为上下文解释当前章节", context_text)
        self.assertIn("这段引用提供背景", context_text)
        self.assertLessEqual(len(source_context_blocks), 8)

    def test_trace_views_separate_source_and_context_chains(self) -> None:
        self.write_sample_doc()
        process_input(self.temp_input_dir)
        conn = db_connection.get_connection()
        chunk_row = dict(
            conn.execute(
                """
                SELECT c.id, c.document_id, c.section_label, d.path, d.title
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                """
            ).fetchone()
        )
        context = build_extraction_context_for_chunk(chunk_row)
        extraction = ExtractionResult.from_dict(
            {
                "context": context,
                "entities": [],
                "events": [],
                "state_candidates": [],
                "relation_candidates": [],
                "retrieval_candidates": [],
            }
        )
        extraction_id = save_extraction(
            chunk_id=chunk_row["id"],
            result=extraction,
            extractor_type="test",
            model_name="fake",
            prompt_version="test",
        )
        state_id = upsert_state(
            category="dynamic",
            subtype="recent_event",
            summary="完成 include_decision 语义收敛",
            subject_type="person",
            subject_key="测试作者",
            canonical_summary="完成 include_decision 语义收敛",
        )
        ensure_state_evidence(
            state_id=state_id,
            chunk_id=chunk_row["id"],
            extraction_id=extraction_id,
        )

        inventory_types = {
            row["source_type"]
            for row in conn.execute("SELECT source_type FROM v_source_block_inventory")
        }
        chunk_trace_types = {
            row["source_type"]
            for row in conn.execute("SELECT source_type FROM v_chunk_source_trace")
        }
        context_trace_types = {
            row["source_type"]
            for row in conn.execute("SELECT source_type FROM v_extraction_context_trace")
        }
        state_trace_types = {
            row["source_type"]
            for row in conn.execute("SELECT source_type FROM v_state_source_trace")
        }

        self.assertTrue(
            {
                "front_matter",
                "author_narrative",
                "table_block",
                "quote_material",
                "structured_dump",
                "media_placeholder",
            }.issubset(inventory_types)
        )
        self.assertEqual(chunk_trace_types, {"author_narrative"})
        self.assertIn("front_matter", context_trace_types)
        self.assertIn("table_block", context_trace_types)
        self.assertIn("quote_material", context_trace_types)
        self.assertNotIn("structured_dump", context_trace_types)
        self.assertEqual(state_trace_types, {"author_narrative"})

    def test_build_document_context_reads_front_matter_only(self) -> None:
        self.write_input_doc(
            "context.md",
            """---
title: Demo Context
author: Demo Author
updated_at: 2025-02-03
---

我记录一个正文状态。
""",
        )

        context = build_document_context("context.md", input_dir=self.temp_input_dir)

        self.assertEqual(context["document_title"], "Demo Context")
        self.assertEqual(context["document_author"], "Demo Author")
        self.assertEqual(context["document_time"]["normalized"], "2025-02-03")

    def test_process_input_purges_excluded_documents_from_db(self) -> None:
        self.write_input_doc("notes.md", "我记录一个正文状态。\n")
        conn = db_connection.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO documents (path, title, modified_time, content_hash, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("AGENTS.md", "Control", 1.0, "legacy-hash", "processed"),
        )
        document_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO chunks (document_id, chunk_index, text, token_estimate)
            VALUES (?, ?, ?, ?)
            """,
            (document_id, 0, "legacy control chunk", 10),
        )
        conn.commit()

        result = process_input(self.temp_input_dir)

        paths = [
            row["path"]
            for row in db_connection.get_connection().execute(
                "SELECT path FROM documents ORDER BY path"
            ).fetchall()
        ]

        self.assertNotIn("AGENTS.md", paths)
        self.assertIn("notes.md", paths)
        self.assertEqual(result["purged_excluded"], 1)


if __name__ == "__main__":
    unittest.main()
