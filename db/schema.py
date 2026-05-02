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

-- 3. 每个 chunk 的结构化提炼结果
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

-- 4. 聚合后的状态项
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

-- 4a. 状态证据关联表（多对多关系）
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

-- 5. 对象之间的关系
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

-- 6. 待判断是否需要补充检索的候选对象
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

-- 7. 输出文档的版本快照
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
CREATE INDEX IF NOT EXISTS idx_extractions_chunk_id ON extractions(chunk_id);
CREATE INDEX IF NOT EXISTS idx_states_category ON states(category);
CREATE INDEX IF NOT EXISTS idx_states_status ON states(status);
CREATE INDEX IF NOT EXISTS idx_state_evidence_state_id ON state_evidence(state_id);
CREATE INDEX IF NOT EXISTS idx_state_evidence_chunk_id ON state_evidence(chunk_id);
CREATE INDEX IF NOT EXISTS idx_state_evidence_extraction_id ON state_evidence(extraction_id);
CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_type, target_id);
"""
