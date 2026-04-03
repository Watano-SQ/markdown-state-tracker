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

-- 2. 文档切分后的片段
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    token_estimate INTEGER,
    created_at REAL DEFAULT (julianday('now')),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    UNIQUE(document_id, chunk_index)
);

-- 3. 每个 chunk 的结构化提炼结果
CREATE TABLE IF NOT EXISTS extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id INTEGER NOT NULL,
    extraction_json TEXT,
    model_version TEXT,
    created_at REAL DEFAULT (julianday('now')),
    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
);

-- 4. 聚合后的状态项
CREATE TABLE IF NOT EXISTS states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,       -- 大类：如 dynamic, static
    subtype TEXT,                 -- 小类：如 ongoing_project, preference
    summary TEXT NOT NULL,
    detail TEXT,
    status TEXT DEFAULT 'active', -- active, archived
    confidence REAL DEFAULT 1.0,
    first_seen REAL DEFAULT (julianday('now')),
    last_updated REAL DEFAULT (julianday('now')),
    source_chunk_ids TEXT         -- JSON array of chunk ids
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
CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_type, target_id);
"""
