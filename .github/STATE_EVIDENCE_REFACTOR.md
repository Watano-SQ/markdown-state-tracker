# State Evidence 关联表重构说明

## 变更目标

移除 `states` 表中的 `source_chunk_ids` JSON 字段，引入专门的 `state_evidence` 关联表来表达 state 与 chunk/extraction 的多对多关系。

## 问题分析

### 旧设计的问题

**states 表中的 `source_chunk_ids TEXT` 字段：**
```sql
-- 旧设计
CREATE TABLE states (
    ...
    source_chunk_ids TEXT  -- JSON array: [1, 2, 3]
);
```

**缺陷：**
1. ❌ 违反数据库范式 - 在单个字段中存储多值
2. ❌ 无法建立外键约束 - 数据完整性无法保证
3. ❌ 查询困难 - 无法通过 SQL 直接查询"哪些 state 引用了某个 chunk"
4. ❌ 关系不对等 - 只能从 state 找 chunk，反向查询困难
5. ❌ 无法表达证据角色 - 所有 chunk 都是"来源"，没有层次
6. ❌ 无法加权 - 无法表达某些证据比其他证据更重要

### 新设计的优势

**state_evidence 关联表：**
```sql
CREATE TABLE state_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state_id INTEGER NOT NULL,           -- 关联的状态
    chunk_id INTEGER,                     -- 关联的 chunk（可空）
    extraction_id INTEGER,                -- 关联的 extraction（可空）
    evidence_role TEXT DEFAULT 'source',  -- 证据角色
    weight REAL DEFAULT 1.0,              -- 证据权重
    note TEXT,                            -- 备注说明
    created_at REAL DEFAULT (julianday('now')),
    FOREIGN KEY (state_id) REFERENCES states(id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE,
    FOREIGN KEY (extraction_id) REFERENCES extractions(id) ON DELETE CASCADE,
    CHECK (chunk_id IS NOT NULL OR extraction_id IS NOT NULL)
);
```

**优势：**
1. ✅ 符合关系数据库范式 - 多对多关系用关联表
2. ✅ 外键约束完整 - 数据完整性由数据库保证
3. ✅ 查询灵活 - 双向查询都很简单
4. ✅ 可扩展性强 - 可以添加证据角色、权重等属性
5. ✅ 支持细粒度追溯 - 可以关联到 extraction 而非仅 chunk
6. ✅ 语义明确 - 通过 `evidence_role` 区分不同类型的证据

## Schema 变更

### states 表
```sql
-- 移除字段
- source_chunk_ids TEXT

-- 表结构简化
CREATE TABLE states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    subtype TEXT,
    summary TEXT NOT NULL,
    detail TEXT,
    status TEXT DEFAULT 'active',
    confidence REAL DEFAULT 1.0,
    first_seen REAL DEFAULT (julianday('now')),
    last_updated REAL DEFAULT (julianday('now'))
    -- 不再有 source_chunk_ids
);
```

### 新增 state_evidence 表
```sql
CREATE TABLE state_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state_id INTEGER NOT NULL,
    chunk_id INTEGER,                     
    extraction_id INTEGER,                
    evidence_role TEXT DEFAULT 'source',  
    weight REAL DEFAULT 1.0,              
    note TEXT,                            
    created_at REAL DEFAULT (julianday('now')),
    FOREIGN KEY (state_id) REFERENCES states(id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE,
    FOREIGN KEY (extraction_id) REFERENCES extractions(id) ON DELETE CASCADE,
    CHECK (chunk_id IS NOT NULL OR extraction_id IS NOT NULL)
);

-- 索引
CREATE INDEX idx_state_evidence_state_id ON state_evidence(state_id);
CREATE INDEX idx_state_evidence_chunk_id ON state_evidence(chunk_id);
CREATE INDEX idx_state_evidence_extraction_id ON state_evidence(extraction_id);
```

## 代码变更

### 1. 新增辅助函数

```python
def add_state_evidence(
    state_id: int,
    chunk_id: Optional[int] = None,
    extraction_id: Optional[int] = None,
    evidence_role: str = 'source',
    weight: float = 1.0,
    note: Optional[str] = None
) -> int:
    """添加状态证据"""

def get_state_evidence(state_id: int) -> List[Dict[str, Any]]:
    """获取状态的所有证据"""
```

### 2. 更新 upsert_state 函数

**旧版本：**
```python
def upsert_state(
    category: str,
    subtype: str,
    summary: str,
    detail: Optional[str] = None,
    source_chunk_ids: Optional[List[int]] = None,  # JSON 字段
    confidence: float = 1.0
) -> int:
    # 合并 source_chunk_ids
    old_chunks = json.loads(existing['source_chunk_ids'] or '[]')
    new_chunks = list(set(old_chunks + (source_chunk_ids or [])))
    # UPDATE ... SET source_chunk_ids = ?
```

**新版本：**
```python
def upsert_state(
    category: str,
    subtype: str,
    summary: str,
    detail: Optional[str] = None,
    chunk_ids: Optional[List[int]] = None,  # 重命名但保持兼容
    confidence: float = 1.0
) -> int:
    # 添加证据到关联表
    if chunk_ids:
        for chunk_id in chunk_ids:
            add_state_evidence(state_id, chunk_id=chunk_id)
```

### 3. 更新查询逻辑

**output_layer.py：**
```python
# 旧版本
SELECT id, summary, detail, ..., source_chunk_ids FROM states

# 新版本
SELECT id, summary, detail, ... FROM states
# 如果需要证据，单独查询：
SELECT * FROM state_evidence WHERE state_id = ?
```

## 证据角色（evidence_role）

支持的证据角色类型：

- **`source`**（默认）- 主要来源
  - 该 chunk/extraction 是这个 state 的直接来源
  
- **`supporting`** - 支持性证据
  - 该 chunk/extraction 支持或强化这个 state
  
- **`contradicting`** - 矛盾性证据
  - 该 chunk/extraction 与这个 state 存在矛盾
  - 可用于标记需要人工确认的情况

## 使用示例

### 创建带证据的状态

```python
from layers.middle_layer import upsert_state, add_state_evidence

# 方式 1：通过 upsert_state（简单）
state_id = upsert_state(
    category='dynamic',
    subtype='ongoing_project',
    summary='开发状态追踪系统',
    chunk_ids=[1, 2, 3]  # 自动添加为 source 证据
)

# 方式 2：手动添加证据（灵活）
state_id = upsert_state(
    category='dynamic',
    subtype='ongoing_project',
    summary='开发状态追踪系统'
)

# 添加主要来源
add_state_evidence(state_id, chunk_id=1, evidence_role='source', weight=1.0)

# 添加支持性证据
add_state_evidence(state_id, chunk_id=2, evidence_role='supporting', weight=0.7)

# 添加基于 extraction 的证据
add_state_evidence(state_id, extraction_id=5, evidence_role='source', weight=0.9)
```

### 查询证据

```python
from layers.middle_layer import get_state_evidence

# 获取某个 state 的所有证据
evidence_list = get_state_evidence(state_id)
for ev in evidence_list:
    print(f"Chunk {ev['chunk_id']}, role: {ev['evidence_role']}, weight: {ev['weight']}")
```

### 反向查询

```python
# 查询某个 chunk 支撑了哪些 states
cursor.execute("""
    SELECT s.id, s.summary, se.evidence_role, se.weight
    FROM states s
    JOIN state_evidence se ON s.id = se.state_id
    WHERE se.chunk_id = ?
""", (chunk_id,))
```

## Migration 影响

### 对现有数据库

**方式 1：重建（推荐）**
```bash
python main.py --init
```

**方式 2：迁移脚本（如果有数据需要保留）**
```python
# 读取旧数据
cursor.execute("SELECT id, source_chunk_ids FROM states WHERE source_chunk_ids IS NOT NULL")
for row in cursor.fetchall():
    state_id = row['id']
    chunk_ids = json.loads(row['source_chunk_ids'] or '[]')
    
    # 迁移到新表
    for chunk_id in chunk_ids:
        add_state_evidence(state_id, chunk_id=chunk_id)

# 删除旧字段（可选）
cursor.execute("ALTER TABLE states DROP COLUMN source_chunk_ids")
```

## 验证结果

✅ states 表已移除 `source_chunk_ids` 字段  
✅ state_evidence 表创建成功，包含所有必需字段  
✅ 外键约束正确（state_id, chunk_id, extraction_id）  
✅ CHECK 约束生效（至少有一个关联）  
✅ upsert_state 函数正确使用新表  
✅ 测试通过：创建 state → 添加证据 → 查询证据  

## 未来扩展

1. **证据冲突检测**
   - 检测 `contradicting` 类型的证据
   - 自动标记需要人工审核的 state

2. **证据权重聚合**
   - 根据多个证据的权重计算 state 的总置信度
   - 加权平均算法

3. **证据链追溯**
   - 从 state → evidence → chunk → document
   - 完整的溯源路径

4. **证据过期处理**
   - 基于时间自动降低旧证据的权重
   - 证据刷新机制

---

日期：2026-04-05  
变更类型：refactor (schema)  
影响范围：states 表, state_evidence 表, middle_layer 接口
