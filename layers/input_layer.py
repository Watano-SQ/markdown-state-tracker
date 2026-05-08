"""
输入层：文档扫描、切分、抽取
"""
import hashlib
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging
from time import perf_counter

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app_logging import get_logger, log_event
from config import INPUT_DIR
from db import get_connection


logger = get_logger("input")

INPUT_PROCESSING_VERSION = "input-v4-context-source-blocks"
CONTROL_DOCUMENT_FILENAMES = {"agents.md"}
EXCLUDED_DOCUMENT_PREFIXES = ("test_",)
EXCLUDED_DIRECTORY_NAMES = {"tests", "fixtures", "validation"}
INCLUDE_DECISIONS = {
    "author_narrative": "extract",
    "table_block": "context_only",
    "front_matter": "context_only",
    "quote_material": "context_only",
    "structured_dump": "exclude",
    "media_placeholder": "exclude",
}
MAX_SOURCE_CONTEXT_BLOCKS = 8
MAX_SOURCE_CONTEXT_PREVIEW_CHARS = 240
MAX_SOURCE_CONTEXT_TOTAL_PREVIEW_CHARS = 1200

@dataclass
class DocumentInfo:
    """文档信息"""
    path: str
    title: str
    modified_time: float
    content: str
    content_hash: str


@dataclass  
class Chunk:
    """文档片段（仅包含正文切分结果）
    
    Attributes:
        text: 片段文本内容
        index: 片段在文档中的序号（从0开始）
        token_estimate: token 数量估算（可选）
        start_offset: 在原文中的起始位置（可选）
        end_offset: 在原文中的结束位置（可选）
        section_label: 所属章节标签（可选）
    """
    text: str
    index: int
    token_estimate: Optional[int] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    section_label: Optional[str] = None


@dataclass
class SourceBlock:
    """带结构来源类型和准入决策的文档块。"""
    text: str
    source_type: str
    include_decision: str
    start_offset: int
    end_offset: int
    section_label: Optional[str] = None


@dataclass
class ChunkSourceReference:
    """chunk 中一个片段对应的 SourceBlock。"""
    source_block_index: int
    order_in_chunk: int
    source_start_offset: Optional[int]
    source_end_offset: Optional[int]
    text_fragment_hash: Optional[str]


@dataclass
class ChunkWithSources:
    """带来源映射的 chunk。"""
    chunk: Chunk
    source_references: List[ChunkSourceReference]


@dataclass
class ProcessedDocumentBlocks:
    """输入层结构分块和可抽取 chunk 的处理结果。"""
    source_blocks: List[SourceBlock]
    chunks: List[ChunkWithSources]


def compute_hash(content: str) -> str:
    """计算带输入处理版本的内容 hash。"""
    payload = f"{INPUT_PROCESSING_VERSION}\0{content}"
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]


def compute_text_hash(text: str) -> str:
    """计算来源块或片段的短 hash。"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数（中英文混合，简单按字符估算）"""
    # 简单启发式：中文约 1.5 token/字，英文约 0.25 token/词
    # 这里用粗略估计：字符数 / 2
    return max(1, len(text) // 2)


def parse_front_matter(content: str) -> Dict[str, str]:
    """解析文档顶部 front matter 的简单键值。"""
    lines = content.splitlines()
    if not lines or lines[0].strip() != '---':
        return {}

    metadata: Dict[str, str] = {}
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == '---':
            return metadata
        if ':' not in line or line.startswith((' ', '\t')):
            continue
        key, value = line.split(':', 1)
        key = key.strip()
        value = value.strip().strip('"\'')
        if key:
            metadata[key] = value
    return {}


def extract_document_context(content: str, title: Optional[str] = None) -> Dict[str, Any]:
    """提炼可传给抽取层的轻量文档上下文。

    只有文档开头 front matter 作为文档元信息来源。正文段落和表格
    即使包含“作者”“标题”等列名或词语，也不再被当作当前文档 metadata。
    """
    front_matter = parse_front_matter(content)
    metadata = front_matter

    context: Dict[str, Any] = {}
    document_title = title or metadata.get('title') or metadata.get('标题')
    if document_title:
        context['document_title'] = document_title

    author = metadata.get('author') or metadata.get('作者')
    if author:
        context['document_author'] = author

    document_mode = metadata.get('document_mode') or metadata.get('mode') or metadata.get('文档模式')
    if document_mode:
        context['document_mode'] = document_mode

    time_key = next(
        (
            key for key in (
                'updated_at',
                '更新时间',
                'created_at',
                '创建时间',
                'date',
                'time',
                '日期',
                '时间',
            )
            if metadata.get(key)
        ),
        None,
    )
    if time_key:
        context['document_time'] = {
            'normalized': metadata[time_key],
            'source': 'document_context',
            'raw': metadata[time_key],
        }

    return context


def build_document_context(relative_path: Optional[str], title: Optional[str] = None, input_dir: Path = INPUT_DIR) -> Dict[str, Any]:
    """按输入文档路径构建抽取上下文；读取失败时退化为标题上下文。"""
    context: Dict[str, Any] = {}
    if title:
        context['document_title'] = title

    if not relative_path:
        return context

    try:
        content = (input_dir / relative_path).read_text(encoding='utf-8')
    except OSError:
        return context

    extracted_context = extract_document_context(content, title=title)
    return {**context, **extracted_context}


def build_extraction_context_for_chunk(chunk_row: Dict[str, Any]) -> Dict[str, Any]:
    """Build canonical extraction context for a pending chunk row.

    extract blocks are represented by chunks.text. context_only blocks are
    passed as bounded previews for interpretation, not as extraction text.
    exclude blocks stay queryable in source_blocks but do not enter context.
    """
    conn = get_connection()
    chunk_id = chunk_row.get('id') or chunk_row.get('chunk_id')
    if chunk_id is None:
        raise ValueError("chunk_row must include id or chunk_id")

    cursor = conn.execute("""
        SELECT c.id,
               c.document_id,
               c.chunk_index,
               c.section_label,
               d.path,
               d.title
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.id = ?
    """, (chunk_id,))
    db_chunk = cursor.fetchone()
    if db_chunk is None:
        raise ValueError(f"chunk not found: {chunk_id}")

    path = chunk_row.get('path') or db_chunk['path']
    title = chunk_row.get('title') or db_chunk['title']
    section = chunk_row.get('section_label')
    if section is None:
        section = db_chunk['section_label']

    context = {
        **_build_document_context_from_source_blocks(
            document_id=int(db_chunk['document_id']),
            path=path,
            title=title,
        ),
        'chunk_position': _calculate_chunk_position(
            int(db_chunk['document_id']),
            int(db_chunk['chunk_index']),
        ),
        'section': section,
    }
    source_context_blocks = _load_source_context_blocks(
        document_id=int(db_chunk['document_id']),
        section_label=section,
    )
    context['source_context_blocks'] = source_context_blocks
    return context


def _build_document_context_from_source_blocks(
    *,
    document_id: int,
    path: Optional[str],
    title: Optional[str],
) -> Dict[str, Any]:
    row = get_connection().execute("""
        SELECT text
        FROM source_blocks
        WHERE document_id = ?
          AND source_type = 'front_matter'
        ORDER BY block_index
        LIMIT 1
    """, (document_id,)).fetchone()
    if row is not None:
        context: Dict[str, Any] = {}
        if title:
            context['document_title'] = title
        return {**context, **extract_document_context(row['text'], title=title)}

    return build_document_context(path, title=title)


def _calculate_chunk_position(document_id: int, chunk_index: int) -> str:
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS count, MAX(chunk_index) AS max_index FROM chunks WHERE document_id = ?",
        (document_id,),
    ).fetchone()
    if row is None or row['count'] <= 1:
        return "middle"
    if chunk_index == 0:
        return "start"
    if chunk_index == row['max_index']:
        return "end"
    return "middle"


def _load_source_context_blocks(
    *,
    document_id: int,
    section_label: Optional[str],
) -> List[Dict[str, Any]]:
    rows = get_connection().execute("""
        SELECT id,
               source_type,
               section_label,
               text,
               start_offset,
               end_offset,
               block_index
        FROM source_blocks
        WHERE document_id = ?
          AND include_decision = 'context_only'
        ORDER BY
            CASE WHEN source_type = 'front_matter' THEN 0 ELSE 1 END,
            block_index
    """, (document_id,)).fetchall()

    selected: List[Dict[str, Any]] = []
    total_preview_chars = 0
    for row in rows:
        source_type = row['source_type']
        row_section = row['section_label']
        if source_type != 'front_matter' and section_label and row_section != section_label:
            continue

        preview = _truncate_source_context_preview(row['text'])
        if total_preview_chars + len(preview) > MAX_SOURCE_CONTEXT_TOTAL_PREVIEW_CHARS:
            break

        selected.append({
            'source_block_id': row['id'],
            'source_type': source_type,
            'section_label': row_section,
            'text_preview': preview,
            'start_offset': row['start_offset'],
            'end_offset': row['end_offset'],
        })
        total_preview_chars += len(preview)
        if len(selected) >= MAX_SOURCE_CONTEXT_BLOCKS:
            break

    return selected


def _truncate_source_context_preview(text: str) -> str:
    normalized = re.sub(r'\s+', ' ', text).strip()
    if len(normalized) <= MAX_SOURCE_CONTEXT_PREVIEW_CHARS:
        return normalized
    return normalized[:MAX_SOURCE_CONTEXT_PREVIEW_CHARS - 3].rstrip() + "..."


def extract_title(content: str, filepath: Path) -> str:
    """提取文档标题"""
    front_matter = parse_front_matter(content)
    if front_matter.get('title'):
        return front_matter['title']

    # 尝试从第一行 # 标题提取
    lines = content.strip().split('\n')
    for line in lines[:20]:
        line = line.strip()
        if line.startswith('# '):
            return line[2:].strip()
    # 否则用文件名
    return filepath.stem


def should_include_document_path(relative_path: Path | str) -> Tuple[bool, Optional[str]]:
    """判断相对路径是否应进入正式输入链路。"""
    relative = Path(relative_path)
    filename = relative.name.lower()

    if filename in CONTROL_DOCUMENT_FILENAMES:
        return False, "control_file"

    if filename.startswith(EXCLUDED_DOCUMENT_PREFIXES):
        return False, "test_fixture"

    if any(part.lower() in EXCLUDED_DIRECTORY_NAMES for part in relative.parts[:-1]):
        return False, "fixture_directory"

    return True, None


def _clean_inline_markdown(text: str) -> str:
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def _is_heading_line(stripped_line: str) -> bool:
    return bool(re.match(r'^#{1,6}\s+\S', stripped_line))


def _is_horizontal_rule(stripped_line: str) -> bool:
    return stripped_line in {'---', '***', '___'}


def _is_table_line(stripped_line: str) -> bool:
    return stripped_line.startswith('|') and stripped_line.endswith('|')


def _is_fence_start(stripped_line: str) -> Optional[str]:
    match = re.match(r'^(```+|~~~+)', stripped_line)
    return match.group(1) if match else None


def _make_source_block(
    lines: List[str],
    line_offsets: List[int],
    start_index: int,
    end_index: int,
    source_type: str,
    section_label: Optional[str],
) -> SourceBlock:
    raw_text = ''.join(lines[start_index:end_index])
    text = raw_text.strip()
    start_offset = line_offsets[start_index]
    end_offset = line_offsets[end_index - 1] + len(lines[end_index - 1].rstrip('\r\n'))
    include_decision = INCLUDE_DECISIONS.get(source_type, "extract")
    return SourceBlock(
        text=text,
        source_type=source_type,
        include_decision=include_decision,
        start_offset=start_offset,
        end_offset=end_offset,
        section_label=section_label,
    )


def _looks_like_media_placeholder(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True

    if re.fullmatch(r'[#*_\-\s]+', stripped):
        return True

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if not lines:
        return True

    patterns = (
        re.compile(r'^!\[[^\]]*\]\([^)]+\)$'),
        re.compile(r'^\[[^\]]+\]\([^)]+\)$'),
        re.compile(r'^https?://\S+$'),
        re.compile(r'^<https?://[^>]+>$'),
    )
    return all(any(pattern.match(line) for pattern in patterns) for line in lines)


def _looks_like_structured_dump(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False

    if stripped.startswith('<') and stripped.endswith('>') and re.search(r'<[^>]+>', stripped):
        return True

    if (stripped.startswith('{') and stripped.endswith('}')) or (stripped.startswith('[') and stripped.endswith(']')):
        try:
            json.loads(stripped)
            return True
        except json.JSONDecodeError:
            pass

    command_lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(command_lines) >= 2 and all(
        re.match(r'^(sudo |apt |pip |python |docker |git |scp |curl |wget |npm |pnpm |yarn |cd |ls |chmod |chown )', line)
        for line in command_lines
    ):
        return True

    return False


def classify_text_block(
    text: str,
    *,
    near_document_start: bool,
    section_label: Optional[str],
) -> str:
    """为普通文本块分配结构来源类型。

    near_document_start 和 section_label 保留在签名中以兼容调用点，但当前
    不再用它们根据“作者/标题/建议/步骤/配置”等词做语义排除。
    """
    _ = near_document_start, section_label
    if _looks_like_media_placeholder(text):
        return "media_placeholder"

    if _looks_like_structured_dump(text):
        return "structured_dump"

    return "author_narrative"


def split_document_into_source_blocks(content: str) -> List[SourceBlock]:
    """按 Markdown 结构切分并标记最小来源类型。"""
    lines = content.splitlines(keepends=True)
    if not lines:
        return []

    line_offsets: List[int] = []
    offset = 0
    for line in lines:
        line_offsets.append(offset)
        offset += len(line)

    blocks: List[SourceBlock] = []
    current_section: Optional[str] = None
    author_block_seen = False
    index = 0

    if lines[0].strip() == '---':
        for closing_index in range(1, len(lines)):
            if lines[closing_index].strip() == '---':
                blocks.append(
                    _make_source_block(
                        lines,
                        line_offsets,
                        0,
                        closing_index + 1,
                        "front_matter",
                        None,
                    )
                )
                index = closing_index + 1
                break

    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue

        if _is_heading_line(stripped):
            current_section = _clean_inline_markdown(re.sub(r'^#{1,6}\s+', '', stripped))
            index += 1
            continue

        fence = _is_fence_start(stripped)
        if fence:
            end_index = index + 1
            while end_index < len(lines):
                if re.match(rf'^{re.escape(fence)}', lines[end_index].strip()):
                    end_index += 1
                    break
                end_index += 1
            blocks.append(
                _make_source_block(
                    lines,
                    line_offsets,
                    index,
                    min(end_index, len(lines)),
                    "structured_dump",
                    current_section,
                )
            )
            index = end_index
            continue

        if stripped.startswith('>'):
            end_index = index + 1
            while end_index < len(lines):
                next_stripped = lines[end_index].strip()
                if next_stripped.startswith('>') or not next_stripped:
                    end_index += 1
                    continue
                break
            blocks.append(
                _make_source_block(
                    lines,
                    line_offsets,
                    index,
                    end_index,
                    "quote_material",
                    current_section,
                )
            )
            index = end_index
            continue

        if _is_table_line(stripped):
            end_index = index + 1
            while end_index < len(lines) and _is_table_line(lines[end_index].strip()):
                end_index += 1
            block = _make_source_block(
                lines,
                line_offsets,
                index,
                end_index,
                "table_block",
                current_section,
            )
            blocks.append(block)
            index = end_index
            continue

        end_index = index + 1
        while end_index < len(lines):
            next_stripped = lines[end_index].strip()
            if (
                not next_stripped
                or _is_horizontal_rule(next_stripped)
                or _is_heading_line(next_stripped)
                or _is_fence_start(next_stripped)
                or next_stripped.startswith('>')
                or _is_table_line(next_stripped)
            ):
                break
            end_index += 1

        raw_text = ''.join(lines[index:end_index]).strip()
        near_document_start = (not author_block_seen) and line_offsets[index] < 1200
        source_type = classify_text_block(
            raw_text,
            near_document_start=near_document_start,
            section_label=current_section,
        )
        blocks.append(
            _make_source_block(
                lines,
                line_offsets,
                index,
                end_index,
                source_type,
                current_section,
            )
        )
        if source_type == "author_narrative":
            author_block_seen = True
        index = end_index

    return blocks


def scan_documents(input_dir: Path = INPUT_DIR) -> Tuple[List[DocumentInfo], List[Dict[str, str]]]:
    """扫描目录中的 Markdown 文件并应用显式纳入规则。"""
    start_time = perf_counter()
    documents = []
    skipped_documents: List[Dict[str, str]] = []

    for md_file in sorted(input_dir.rglob('*.md')):
        relative_path = md_file.relative_to(input_dir)
        include, reason = should_include_document_path(relative_path)
        if not include:
            skipped_documents.append({'path': str(relative_path), 'reason': reason or 'excluded'})
            log_event(
                logger,
                logging.INFO,
                "document_scan_skipped",
                "Skipped markdown document by explicit inclusion rule",
                stage="input",
                path=str(relative_path),
                reason=reason,
            )
            continue

        content = md_file.read_text(encoding='utf-8')
        doc = DocumentInfo(
            path=str(relative_path),
            title=extract_title(content, md_file),
            modified_time=md_file.stat().st_mtime,
            content=content,
            content_hash=compute_hash(content)
        )
        documents.append(doc)
        log_event(
            logger,
            logging.INFO,
            "document_scanned",
            "Scanned markdown document",
            stage="input",
            path=doc.path,
            title=doc.title,
            content_hash=doc.content_hash,
        )

    log_event(
        logger,
        logging.INFO,
        "document_scan_done",
        "Completed markdown document scan",
        stage="input",
        total_documents=len(documents),
        skipped_documents=len(skipped_documents),
        duration_ms=(perf_counter() - start_time) * 1000,
    )
    return documents, skipped_documents


def purge_excluded_documents() -> List[str]:
    """删除数据库中不再允许进入正式链路的文档。"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT path FROM documents")
    paths = [row['path'] for row in cursor.fetchall()]

    removed_paths: List[str] = []
    for path in paths:
        include, _ = should_include_document_path(path)
        if include:
            continue
        cursor.execute("DELETE FROM documents WHERE path = ?", (path,))
        removed_paths.append(path)

    if removed_paths:
        conn.commit()
        log_event(
            logger,
            logging.INFO,
            "excluded_documents_purged",
            "Purged excluded documents from database",
            stage="input",
            removed_documents=len(removed_paths),
        )

    return removed_paths


def get_changed_documents(documents: List[DocumentInfo]) -> Tuple[List[DocumentInfo], List[DocumentInfo]]:
    """识别新增和修改过的文档
    
    Returns:
        (new_docs, modified_docs)
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    new_docs = []
    modified_docs = []
    
    for doc in documents:
        cursor.execute(
            "SELECT id, content_hash FROM documents WHERE path = ?",
            (doc.path,)
        )
        row = cursor.fetchone()
        
        if row is None:
            new_docs.append(doc)
        elif row['content_hash'] != doc.content_hash:
            modified_docs.append(doc)
    
    log_event(
        logger,
        logging.INFO,
        "document_changes_detected",
        "Calculated document changes",
        stage="input",
        total_documents=len(documents),
        new_documents=len(new_docs),
        modified_documents=len(modified_docs),
    )
    return new_docs, modified_docs


def chunk_document_with_sources(content: str, max_tokens: int = 500) -> ProcessedDocumentBlocks:
    """将文档切分为来源块和可抽取 chunks。"""
    source_blocks = split_document_into_source_blocks(content)
    chunks: List[ChunkWithSources] = []
    current_blocks: List[SourceBlock] = []
    current_block_indexes: List[int] = []
    current_tokens = 0
    chunk_index = 0

    def flush_current_blocks() -> None:
        nonlocal current_blocks, current_block_indexes, current_tokens, chunk_index
        if not current_blocks:
            return

        chunk_text = '\n\n'.join(block.text for block in current_blocks)
        source_references = [
            ChunkSourceReference(
                source_block_index=block_index,
                order_in_chunk=order,
                source_start_offset=block.start_offset,
                source_end_offset=block.end_offset,
                text_fragment_hash=compute_text_hash(block.text),
            )
            for order, (block_index, block) in enumerate(
                zip(current_block_indexes, current_blocks)
            )
        ]
        chunks.append(
            ChunkWithSources(
                chunk=Chunk(
                    text=chunk_text,
                    index=chunk_index,
                    token_estimate=current_tokens,
                    start_offset=current_blocks[0].start_offset,
                    end_offset=current_blocks[-1].end_offset,
                    section_label=current_blocks[-1].section_label,
                ),
                source_references=source_references,
            )
        )
        chunk_index += 1
        current_blocks = []
        current_block_indexes = []
        current_tokens = 0

    def append_long_block(block_index: int, block: SourceBlock) -> None:
        nonlocal chunk_index
        sentences = re.split(r'([。！？.!?])', block.text)
        temp_chunk: List[str] = []
        temp_tokens = 0
        temp_start = block.start_offset

        index = 0
        while index < len(sentences):
            sentence = sentences[index]
            if index + 1 < len(sentences) and len(sentences[index + 1]) == 1:
                sentence += sentences[index + 1]
                index += 1

            sentence_tokens = estimate_tokens(sentence)
            if temp_tokens + sentence_tokens > max_tokens and temp_chunk:
                chunk_text = ''.join(temp_chunk)
                chunks.append(
                    ChunkWithSources(
                        chunk=Chunk(
                            text=chunk_text,
                            index=chunk_index,
                            token_estimate=temp_tokens,
                            start_offset=temp_start,
                            end_offset=temp_start + len(chunk_text),
                            section_label=block.section_label,
                        ),
                        source_references=[
                            ChunkSourceReference(
                                source_block_index=block_index,
                                order_in_chunk=0,
                                source_start_offset=temp_start,
                                source_end_offset=temp_start + len(chunk_text),
                                text_fragment_hash=compute_text_hash(chunk_text),
                            )
                        ],
                    )
                )
                chunk_index += 1
                # Offset accounting is conservative: SourceBlock text is stripped
                # from the raw lines, so leading/trailing whitespace is not modeled.
                temp_start += len(chunk_text)
                temp_chunk = []
                temp_tokens = 0

            temp_chunk.append(sentence)
            temp_tokens += sentence_tokens
            index += 1

        if temp_chunk:
            chunk_text = ''.join(temp_chunk)
            chunks.append(
                ChunkWithSources(
                    chunk=Chunk(
                        text=chunk_text,
                        index=chunk_index,
                        token_estimate=temp_tokens,
                        start_offset=temp_start,
                        end_offset=temp_start + len(chunk_text),
                        section_label=block.section_label,
                    ),
                    source_references=[
                        ChunkSourceReference(
                            source_block_index=block_index,
                            order_in_chunk=0,
                            source_start_offset=temp_start,
                            source_end_offset=temp_start + len(chunk_text),
                            text_fragment_hash=compute_text_hash(chunk_text),
                        )
                    ],
                )
            )
            chunk_index += 1

    for block_index, block in enumerate(source_blocks):
        if block.include_decision != "extract":
            flush_current_blocks()
            continue

        block_tokens = estimate_tokens(block.text)
        if block_tokens > max_tokens:
            flush_current_blocks()
            append_long_block(block_index, block)
            continue

        if current_blocks and (
            current_tokens + block_tokens > max_tokens
            or current_blocks[-1].section_label != block.section_label
            or current_blocks[-1].source_type != block.source_type
        ):
            flush_current_blocks()

        current_blocks.append(block)
        current_block_indexes.append(block_index)
        current_tokens += block_tokens

    flush_current_blocks()
    return ProcessedDocumentBlocks(source_blocks=source_blocks, chunks=chunks)


def chunk_document(content: str, max_tokens: int = 500) -> List[Chunk]:
    """将文档切分为 chunks，保持旧调用方只拿正文 chunk 的外部行为。"""
    processed = chunk_document_with_sources(content, max_tokens=max_tokens)
    return [chunk_with_sources.chunk for chunk_with_sources in processed.chunks]


def save_document_and_chunks(doc: DocumentInfo, processed: ProcessedDocumentBlocks) -> int:
    """保存文档、SourceBlocks、chunks 和来源映射到数据库，返回 document_id。"""
    start_time = perf_counter()
    conn = get_connection()
    cursor = conn.cursor()
    old_chunk_count = 0
    old_source_block_count = 0
    action = "insert"
    
    # 检查是否已存在
    cursor.execute("SELECT id FROM documents WHERE path = ?", (doc.path,))
    existing = cursor.fetchone()
    
    if existing:
        doc_id = existing['id']
        action = "update"
        cursor.execute("SELECT COUNT(*) FROM chunks WHERE document_id = ?", (doc_id,))
        old_chunk_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM source_blocks WHERE document_id = ?", (doc_id,))
        old_source_block_count = cursor.fetchone()[0]
        # 更新文档
        cursor.execute("""
            UPDATE documents 
            SET title = ?, modified_time = ?, content_hash = ?, 
                status = 'pending', updated_at = julianday('now')
            WHERE id = ?
        """, (doc.title, doc.modified_time, doc.content_hash, doc_id))
        
        # 删除旧 chunks（CASCADE 会删除相关 extractions）
        cursor.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
        cursor.execute("DELETE FROM source_blocks WHERE document_id = ?", (doc_id,))
    else:
        # 插入新文档
        cursor.execute("""
            INSERT INTO documents (path, title, modified_time, content_hash, status)
            VALUES (?, ?, ?, ?, 'pending')
        """, (doc.path, doc.title, doc.modified_time, doc.content_hash))
        doc_id = cursor.lastrowid

    source_block_ids: Dict[int, int] = {}
    for block_index, block in enumerate(processed.source_blocks):
        cursor.execute("""
            INSERT INTO source_blocks (
                document_id,
                block_index,
                source_type,
                include_decision,
                text,
                text_hash,
                start_offset,
                end_offset,
                section_label,
                input_processing_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id,
            block_index,
            block.source_type,
            block.include_decision,
            block.text,
            compute_text_hash(block.text),
            block.start_offset,
            block.end_offset,
            block.section_label,
            INPUT_PROCESSING_VERSION,
        ))
        source_block_ids[block_index] = cursor.lastrowid

    # 插入 chunks 和来源映射
    for chunk_with_sources in processed.chunks:
        chunk = chunk_with_sources.chunk
        cursor.execute("""
            INSERT INTO chunks (document_id, chunk_index, text, token_estimate, 
                              start_offset, end_offset, section_label)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (doc_id, chunk.index, chunk.text, chunk.token_estimate,
              chunk.start_offset, chunk.end_offset, chunk.section_label))
        chunk_id = cursor.lastrowid

        for reference in chunk_with_sources.source_references:
            source_block_id = source_block_ids[reference.source_block_index]
            cursor.execute("""
                INSERT INTO chunk_source_blocks (
                    chunk_id,
                    source_block_id,
                    order_in_chunk,
                    source_start_offset,
                    source_end_offset,
                    text_fragment_hash
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                chunk_id,
                source_block_id,
                reference.order_in_chunk,
                reference.source_start_offset,
                reference.source_end_offset,
                reference.text_fragment_hash,
            ))
    
    conn.commit()
    log_event(
        logger,
        logging.INFO,
        "document_saved",
        "Saved document and chunks",
        stage="input",
        document_id=doc_id,
        path=doc.path,
        title=doc.title,
        source_block_count=len(processed.source_blocks),
        chunk_count=len(processed.chunks),
        replaced_source_block_count=old_source_block_count,
        replaced_chunk_count=old_chunk_count,
        action=action,
        duration_ms=(perf_counter() - start_time) * 1000,
    )
    return doc_id


def process_input(input_dir: Path = INPUT_DIR) -> Dict[str, Any]:
    """输入层主流程：扫描 → 识别变更 → 切分 → 存储
    
    Returns:
        处理统计信息
    """
    stage_start = perf_counter()
    # 1. 扫描文档
    documents, skipped_documents = scan_documents(input_dir)
    purged_paths = purge_excluded_documents()
    
    if not documents:
        log_event(
            logger,
            logging.INFO,
            "input_no_documents",
            "No markdown documents found",
            stage="input",
            total_documents=0,
            skipped_documents=len(skipped_documents),
            purged_documents=len(purged_paths),
            duration_ms=(perf_counter() - stage_start) * 1000,
        )
        return {
            'total': 0,
            'new': 0,
            'modified': 0,
            'skipped': len(skipped_documents),
            'purged_excluded': len(purged_paths),
            'processed': [],
        }
    
    # 2. 识别变更
    new_docs, modified_docs = get_changed_documents(documents)
    docs_to_process = new_docs + modified_docs
    
    # 3. 处理每个文档
    processed = []
    for doc in docs_to_process:
        chunk_start = perf_counter()
        processed_blocks = chunk_document_with_sources(doc.content)
        doc_id = save_document_and_chunks(doc, processed_blocks)
        processed.append({
            'path': doc.path,
            'title': doc.title,
            'doc_id': doc_id,
            'source_block_count': len(processed_blocks.source_blocks),
            'chunk_count': len(processed_blocks.chunks),
            'is_new': doc in new_docs
        })
        log_event(
            logger,
            logging.INFO,
            "document_chunked",
            "Chunked changed document",
            stage="input",
            document_id=doc_id,
            path=doc.path,
            title=doc.title,
            source_block_count=len(processed_blocks.source_blocks),
            chunk_count=len(processed_blocks.chunks),
            action="new" if doc in new_docs else "modified",
            duration_ms=(perf_counter() - chunk_start) * 1000,
        )
    
    result = {
        'total': len(documents),
        'new': len(new_docs),
        'modified': len(modified_docs),
        'skipped': len(skipped_documents),
        'purged_excluded': len(purged_paths),
        'processed': processed
    }

    log_event(
        logger,
        logging.INFO,
        "input_processing_done",
        "Completed input processing",
        stage="input",
        total_documents=result['total'],
        new_documents=result['new'],
        modified_documents=result['modified'],
        skipped_documents=result['skipped'],
        purged_documents=result['purged_excluded'],
        processed_documents=len(result['processed']),
        duration_ms=(perf_counter() - stage_start) * 1000,
    )
    return result
