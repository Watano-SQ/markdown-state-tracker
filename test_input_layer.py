"""
Tests for input-layer inclusion rules and source-aware chunking.
"""
import os
import tempfile
import unittest
from pathlib import Path

import db.connection as db_connection
from db import close_connection, init_db
from layers.input_layer import (
    build_document_context,
    chunk_document,
    extract_document_context,
    process_input,
    should_include_document_path,
    split_document_into_source_blocks,
)


class InputLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_input_dir = Path(__file__).parent / "input_docs"

        fd, temp_db_path = tempfile.mkstemp(prefix="input_layer_", suffix=".db")
        os.close(fd)
        self.temp_db_path = Path(temp_db_path)
        self.original_db_path = db_connection.DB_PATH

        close_connection()
        db_connection.DB_PATH = self.temp_db_path
        init_db()

    def tearDown(self) -> None:
        close_connection()
        db_connection.DB_PATH = self.original_db_path
        self.temp_db_path.unlink(missing_ok=True)

    def test_should_include_document_path_applies_explicit_rules(self) -> None:
        self.assertEqual(should_include_document_path("notes.md"), (True, None))
        self.assertEqual(should_include_document_path("AGENTS.md"), (False, "control_file"))
        self.assertEqual(should_include_document_path("test_fixture.md"), (False, "test_fixture"))
        self.assertEqual(
            should_include_document_path("fixtures/ignored.md"),
            (False, "fixture_directory"),
        )

    def test_source_blocks_and_chunks_skip_non_author_content(self) -> None:
        content = """---
title: Demo
author: 测试者
---

| 作者 | 创建时间 | 更新时间 |
|------|----------|----------|
| 测试者 | 2025-01-01 | 2025-01-02 |

## 复盘
今天我修好了部署问题，并记录了原因。

> Q：这个问题为什么出现？
> A：因为引用块不应进入作者正文抽取。

您可以先安装依赖，再配置环境变量。

```bash
sudo apt update
sudo apt upgrade -y
```

![](https://example.com/demo.png)

我还补上了下一步计划。
"""

        blocks = split_document_into_source_blocks(content)
        source_types = [block.source_type for block in blocks]

        self.assertIn("document_metadata", source_types)
        self.assertIn("metadata_table", source_types)
        self.assertIn("quote_material", source_types)
        self.assertIn("external_material", source_types)
        self.assertIn("structured_dump", source_types)
        self.assertIn("media_placeholder", source_types)

        chunks = chunk_document(content, max_tokens=200)

        self.assertEqual(len(chunks), 2)
        self.assertTrue(all(chunk.section_label == "复盘" for chunk in chunks))
        self.assertIn("今天我修好了部署问题", chunks[0].text)
        self.assertIn("我还补上了下一步计划", chunks[1].text)
        self.assertNotIn("Q：", chunks[0].text + chunks[1].text)
        self.assertNotIn("您可以先安装依赖", chunks[0].text + chunks[1].text)
        self.assertNotIn("sudo apt update", chunks[0].text + chunks[1].text)
        self.assertNotIn("作者 | 创建时间", chunks[0].text + chunks[1].text)

    def test_extract_document_context_uses_front_matter_and_metadata_table(self) -> None:
        content = """---
title: Front Matter Title
author: Front Matter Author
created_at: 2025-01-01
---

| 作者 | 创建时间 | 更新时间 |
|------|----------|----------|
| Table Author | 2025-01-02 | 2025-01-03 |

## 复盘
今天我继续推进项目。
"""

        context = extract_document_context(content)

        self.assertEqual(context["document_title"], "Front Matter Title")
        self.assertEqual(context["document_author"], "Front Matter Author")
        self.assertEqual(
            context["document_time"],
            {
                "normalized": "2025-01-03",
                "source": "document_context",
                "raw": "2025-01-03",
            },
        )

    def test_build_document_context_reads_current_document_without_chunking_metadata(self) -> None:
        base_dir = Path(__file__).parent / "data"
        base_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix="input_context_", suffix=".md", dir=base_dir)
        temp_file = Path(temp_path)
        self.addCleanup(lambda: temp_file.unlink(missing_ok=True))
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(
                """---
title: Demo Context
author: Demo Author
updated_at: 2025-02-03
---

我记录一个正文状态。
"""
            )

        context = build_document_context(temp_file.name, input_dir=base_dir)

        self.assertEqual(context["document_title"], "Demo Context")
        self.assertEqual(context["document_author"], "Demo Author")
        self.assertEqual(context["document_time"]["normalized"], "2025-02-03")

    def test_process_input_purges_excluded_documents_from_db(self) -> None:
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

        result = process_input(self.repo_input_dir)

        paths = [
            row["path"]
            for row in db_connection.get_connection().execute(
                "SELECT path FROM documents ORDER BY path"
            ).fetchall()
        ]

        self.assertNotIn("AGENTS.md", paths)
        self.assertIn("李申亮.md", paths)
        self.assertEqual(result["purged_excluded"], 1)
        self.assertGreaterEqual(result["skipped"], 2)


if __name__ == "__main__":
    unittest.main()
