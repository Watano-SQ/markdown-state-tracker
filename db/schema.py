"""
SQLite 数据库 Schema 定义
"""

SCHEMA_SQL = """
-- 1. 原始文档信息
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    title TEXT,
    modified_time REAL,
    content_hash TEXT,
    status TEXT DEFAULT 'pending',  -- pending, processed, error
    created_at REAL DEFAULT (julianday('now')),
    updated_at REAL DEFAULT (julianday('now'))
);

-- 2. 文档切分后的片段（仅保存正文切分结果）
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    start_offset INTEGER,              -- 在原文中的起始位置（可选）
    end_offset INTEGER,                -- 在原文中的结束位置（可选）
    token_estimate INTEGER,            -- token 估算（可空）
    section_label TEXT,                -- 所属章节标签（可选）
    created_at REAL DEFAULT (julianday('now')),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    UNIQUE(document_id, chunk_index)
);

-- 3. 文档结构分块，记录输入层的来源类型和准入决策
CREATE TABLE IF NOT EXISTS source_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    block_index INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    include_decision TEXT NOT NULL,      -- extract, context_only, exclude
    text TEXT NOT NULL,
    text_hash TEXT,
    start_offset INTEGER,
    end_offset INTEGER,
    section_label TEXT,
    input_processing_version TEXT,
    created_at REAL DEFAULT (julianday('now')),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    UNIQUE(document_id, block_index)
);

-- 3a. chunk 与来源块的映射；chunk 可由多块合并，长块也可拆成多个 chunk
CREATE TABLE IF NOT EXISTS chunk_source_blocks (
    chunk_id INTEGER NOT NULL,
    source_block_id INTEGER NOT NULL,
    order_in_chunk INTEGER NOT NULL,
    source_start_offset INTEGER,
    source_end_offset INTEGER,
    text_fragment_hash TEXT,
    PRIMARY KEY (chunk_id, source_block_id, order_in_chunk),
    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE,
    FOREIGN KEY (source_block_id) REFERENCES source_blocks(id) ON DELETE CASCADE
);

-- 4. 每个 chunk 的结构化提炼结果
CREATE TABLE IF NOT EXISTS extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id INTEGER NOT NULL,
    extraction_json TEXT,
    extractor_type TEXT,           -- 抽取器类型：llm, rule_based, hybrid
    model_name TEXT,               -- 模型名称：如 gpt-4, claude-3, custom_rules
    prompt_version TEXT,           -- prompt 版本：如 v1.0, v2.1
    created_at REAL DEFAULT (julianday('now')),
    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
);

-- 5. 聚合后的状态项
CREATE TABLE IF NOT EXISTS states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,       -- 大类：如 dynamic, static
    subtype TEXT,                 -- 小类：如 ongoing_project, preference
    subject_type TEXT,
    subject_key TEXT,
    canonical_summary TEXT,
    display_summary TEXT,
    summary TEXT NOT NULL,
    detail TEXT,
    status TEXT DEFAULT 'active', -- active, archived
    confidence REAL DEFAULT 1.0,
    first_seen REAL DEFAULT (julianday('now')),
    last_updated REAL DEFAULT (julianday('now'))
);

-- 5a. 状态证据关联表（多对多关系）
CREATE TABLE IF NOT EXISTS state_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state_id INTEGER NOT NULL,
    chunk_id INTEGER,                         -- 关联的 chunk（可空）
    extraction_id INTEGER,                    -- 关联的 extraction（可空）
    evidence_role TEXT DEFAULT 'source',      -- 证据角色：source, supporting, contradicting
    weight REAL DEFAULT 1.0,                  -- 证据权重（0-1）
    note TEXT,                                -- 备注说明
    created_at REAL DEFAULT (julianday('now')),
    FOREIGN KEY (state_id) REFERENCES states(id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE,
    FOREIGN KEY (extraction_id) REFERENCES extractions(id) ON DELETE CASCADE,
    CHECK (chunk_id IS NOT NULL OR extraction_id IS NOT NULL)  -- 至少有一个关联
);

-- 5b. state_candidate 准入记录；记录候选是否允许晋升为 state，不替代 state_evidence
CREATE TABLE IF NOT EXISTS state_candidate_supports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    extraction_id INTEGER NOT NULL,
    candidate_index INTEGER NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('accept', 'reject')),
    reason TEXT NOT NULL CHECK(reason IN (
        'accepted',
        'invalid_candidate',
        'missing_subject',
        'no_text_support',
        'context_only_only'
    )),
    state_id INTEGER,
    created_at REAL DEFAULT (julianday('now')),

    FOREIGN KEY(extraction_id) REFERENCES extractions(id) ON DELETE CASCADE,
    FOREIGN KEY(state_id) REFERENCES states(id) ON DELETE SET NULL,
    UNIQUE(extraction_id, candidate_index)
);

-- 6. 对象之间的关系
CREATE TABLE IF NOT EXISTS relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,    -- 如 state, entity
    source_id INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL,  -- 如 related_to, depends_on
    confidence REAL DEFAULT 1.0,
    created_at REAL DEFAULT (julianday('now'))
);

-- 7. 待判断是否需要补充检索的候选对象
CREATE TABLE IF NOT EXISTS retrieval_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    surface_form TEXT NOT NULL,       -- 原始出现形式
    normalized_name TEXT,             -- 标准化名称
    type_guess TEXT,                  -- 类型猜测
    scope_guess TEXT,                 -- 作用域猜测
    evidence_count INTEGER DEFAULT 1,
    decision_status TEXT DEFAULT 'pending',  -- pending, confirmed, rejected
    priority INTEGER DEFAULT 0,
    source_chunk_ids TEXT,            -- JSON array
    created_at REAL DEFAULT (julianday('now'))
);

-- 8. 输出文档的版本快照
CREATE TABLE IF NOT EXISTS output_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_md TEXT NOT NULL,
    created_at REAL DEFAULT (julianday('now')),
    source_state_version INTEGER      -- 可用于追踪基于哪个状态版本生成
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_path ON documents(path);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_source_blocks_document_id ON source_blocks(document_id);
CREATE INDEX IF NOT EXISTS idx_source_blocks_type ON source_blocks(source_type);
CREATE INDEX IF NOT EXISTS idx_chunk_source_blocks_block_id ON chunk_source_blocks(source_block_id);
CREATE INDEX IF NOT EXISTS idx_extractions_chunk_id ON extractions(chunk_id);
CREATE INDEX IF NOT EXISTS idx_states_category ON states(category);
CREATE INDEX IF NOT EXISTS idx_states_status ON states(status);
CREATE INDEX IF NOT EXISTS idx_state_evidence_state_id ON state_evidence(state_id);
CREATE INDEX IF NOT EXISTS idx_state_evidence_chunk_id ON state_evidence(chunk_id);
CREATE INDEX IF NOT EXISTS idx_state_evidence_extraction_id ON state_evidence(extraction_id);
CREATE INDEX IF NOT EXISTS idx_state_candidate_supports_extraction ON state_candidate_supports(extraction_id);
CREATE INDEX IF NOT EXISTS idx_state_candidate_supports_state ON state_candidate_supports(state_id);
CREATE INDEX IF NOT EXISTS idx_state_candidate_supports_decision ON state_candidate_supports(decision);
CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_type, target_id);

-- 查询视图：文档 source block inventory
CREATE VIEW IF NOT EXISTS v_source_block_inventory AS
SELECT
    d.id AS document_id,
    d.path,
    d.title,
    sb.id AS source_block_id,
    sb.block_index,
    sb.source_type,
    sb.include_decision,
    sb.section_label,
    sb.start_offset,
    sb.end_offset,
    substr(sb.text, 1, 160) AS text_preview
FROM source_blocks sb
JOIN documents d ON d.id = sb.document_id;

-- 查询视图：chunk 正文来源链，只展示进入 chunk 的 extract source blocks
CREATE VIEW IF NOT EXISTS v_chunk_source_trace AS
SELECT
    d.id AS document_id,
    d.path,
    c.id AS chunk_id,
    c.chunk_index,
    substr(c.text, 1, 160) AS chunk_text_preview,
    sb.id AS source_block_id,
    sb.block_index,
    sb.source_type,
    sb.include_decision,
    substr(sb.text, 1, 160) AS source_text_preview
FROM chunks c
JOIN documents d ON d.id = c.document_id
JOIN chunk_source_blocks csb ON csb.chunk_id = c.id
JOIN source_blocks sb ON sb.id = csb.source_block_id
WHERE sb.include_decision = 'extract';

-- 查询视图：extraction 的正文 evidence 来源链
CREATE VIEW IF NOT EXISTS v_extraction_source_trace AS
SELECT
    e.id AS extraction_id,
    c.id AS chunk_id,
    d.id AS document_id,
    d.path,
    c.chunk_index,
    sb.id AS source_block_id,
    sb.block_index,
    sb.source_type,
    sb.include_decision,
    substr(sb.text, 1, 160) AS source_text_preview
FROM extractions e
JOIN chunks c ON c.id = e.chunk_id
JOIN documents d ON d.id = c.document_id
JOIN chunk_source_blocks csb ON csb.chunk_id = c.id
JOIN source_blocks sb ON sb.id = csb.source_block_id
WHERE sb.include_decision = 'extract';

-- 查询视图：state 的正文证据链；不混入 context_only blocks
CREATE VIEW IF NOT EXISTS v_state_source_trace AS
SELECT
    s.id AS state_id,
    s.category,
    s.subtype,
    s.subject_type,
    s.subject_key,
    s.summary,
    s.canonical_summary,
    s.display_summary,
    se.id AS evidence_id,
    se.extraction_id,
    c.id AS chunk_id,
    d.id AS document_id,
    d.path,
    c.chunk_index,
    sb.id AS source_block_id,
    sb.block_index,
    sb.source_type,
    sb.include_decision,
    substr(sb.text, 1, 160) AS source_text_preview
FROM states s
JOIN state_evidence se ON se.state_id = s.id
JOIN chunks c ON c.id = se.chunk_id
JOIN documents d ON d.id = c.document_id
JOIN chunk_source_blocks csb ON csb.chunk_id = c.id
JOIN source_blocks sb ON sb.id = csb.source_block_id
WHERE sb.include_decision = 'extract';

-- 查询视图：state_candidate 准入 trace；candidate 字段来自 extraction_json 原文
CREATE VIEW IF NOT EXISTS v_state_candidate_support_trace AS
SELECT
    scs.id AS support_id,
    scs.extraction_id,
    scs.candidate_index,
    scs.decision,
    scs.reason,
    scs.state_id,
    d.path,
    d.id AS document_id,
    c.id AS chunk_id,
    c.chunk_index,
    json_extract(
        e.extraction_json,
        '$.state_candidates[' || scs.candidate_index || '].summary'
    ) AS candidate_summary,
    json_extract(
        e.extraction_json,
        '$.state_candidates[' || scs.candidate_index || '].canonical_summary'
    ) AS candidate_canonical_summary,
    json_extract(
        e.extraction_json,
        '$.state_candidates[' || scs.candidate_index || '].display_summary'
    ) AS candidate_display_summary,
    json_extract(
        e.extraction_json,
        '$.state_candidates[' || scs.candidate_index || '].subject_type'
    ) AS subject_type,
    json_extract(
        e.extraction_json,
        '$.state_candidates[' || scs.candidate_index || '].subject_key'
    ) AS subject_key,
    json_extract(
        e.extraction_json,
        '$.state_candidates[' || scs.candidate_index || '].category'
    ) AS category,
    json_extract(
        e.extraction_json,
        '$.state_candidates[' || scs.candidate_index || '].subtype'
    ) AS subtype,
    substr(c.text, 1, 160) AS chunk_text_preview
FROM state_candidate_supports scs
JOIN extractions e ON e.id = scs.extraction_id
JOIN chunks c ON c.id = e.chunk_id
JOIN documents d ON d.id = c.document_id;

-- 查询视图：extraction 使用的 context_only source blocks（依赖 SQLite JSON1）
CREATE VIEW IF NOT EXISTS v_extraction_context_trace AS
SELECT
    e.id AS extraction_id,
    c.id AS chunk_id,
    d.id AS document_id,
    d.path,
    sb.id AS context_source_block_id,
    sb.block_index,
    sb.source_type,
    sb.include_decision,
    sb.section_label,
    substr(sb.text, 1, 160) AS context_text_preview
FROM extractions e
JOIN chunks c ON c.id = e.chunk_id
JOIN documents d ON d.id = c.document_id
JOIN json_each(e.extraction_json, '$.context.source_context_blocks') context_block
JOIN source_blocks sb
  ON sb.id = CAST(json_extract(context_block.value, '$.source_block_id') AS INTEGER)
WHERE sb.include_decision = 'context_only';
"""
