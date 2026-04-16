# Extractions 元数据字段重构说明

## 变更目标

将 `extractions` 表中含义模糊的 `model_version` 字段替换为更清晰、更具体的字段设计。

## 问题分析

### 旧设计的问题

**extractions 表中的 `model_version TEXT` 字段：**
```sql
-- 旧设计
CREATE TABLE extractions (
    ...
    model_version TEXT  -- "v0.1" - 语义不明确
);
```

**缺陷：**
1. ❌ **语义模糊** - "model_version" 可以指：
   - 模型本身的版本（如 GPT-4）
   - Prompt 的版本
   - 抽取器代码的版本
   - 配置的版本

2. ❌ **无法区分抽取器类型** - 无法区分：
   - LLM 抽取（如 GPT-4）
   - 规则引擎抽取
   - 混合方式抽取

3. ❌ **难以追踪变更** - 当以下任一变化时，都只能改 version：
   - 换了模型（GPT-4 → Claude-3）
   - 改了 prompt
   - 修改了规则

4. ❌ **不便于效果对比** - 无法方便地比较：
   - 不同模型的效果
   - 不同 prompt 版本的效果
   - LLM vs 规则引擎

### 新设计的优势

**extractions 表的三个独立字段：**
```sql
CREATE TABLE extractions (
    ...
    extractor_type TEXT,    -- 抽取器类型：llm / rule_based / hybrid
    model_name TEXT,        -- 模型名称：gpt-4 / claude-3 / custom_rules
    prompt_version TEXT,    -- prompt 版本：v1.0 / v2.1
    ...
);
```

**优势：**
1. ✅ **语义明确** - 每个字段职责清晰
2. ✅ **便于筛选** - 可以按类型/模型/版本分别查询
3. ✅ **便于对比** - 容易比较不同配置的效果
4. ✅ **扩展性好** - 新增抽取方式时不破坏现有字段
5. ✅ **支持混合** - hybrid 类型可以记录多种来源

## Schema 变更

### extractions 表
```sql
-- 移除字段
- model_version TEXT

-- 新增字段
+ extractor_type TEXT    -- 抽取器类型
+ model_name TEXT        -- 模型名称  
+ prompt_version TEXT    -- prompt 版本
```

**完整定义：**
```sql
CREATE TABLE extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id INTEGER NOT NULL,
    extraction_json TEXT,
    extractor_type TEXT,           -- llm, rule_based, hybrid
    model_name TEXT,               -- gpt-4, claude-3, custom_rules
    prompt_version TEXT,           -- v1.0, v2.1
    created_at REAL DEFAULT (julianday('now')),
    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
);
```

## 字段含义说明

### 1. extractor_type（抽取器类型）

**作用：** 标识使用的抽取方法类型

**可选值：**
- `llm` - 使用大语言模型抽取
  - 适用：需要语义理解的复杂抽取
  - 示例：GPT-4, Claude-3, Gemini

- `rule_based` - 使用规则引擎抽取
  - 适用：结构化文档、固定模式
  - 示例：正则表达式、关键词匹配、模板解析

- `hybrid` - 混合方式
  - 适用：先用规则预处理，再用 LLM 精炼
  - 或者：多种方法结果融合

**查询示例：**
```sql
-- 统计不同抽取器的使用情况
SELECT extractor_type, COUNT(*) 
FROM extractions 
GROUP BY extractor_type;

-- 查找所有 LLM 抽取的结果
SELECT * FROM extractions WHERE extractor_type = 'llm';
```

### 2. model_name（模型名称）

**作用：** 记录具体使用的模型或规则集名称

**命名建议：**

**LLM 类型：**
- `gpt-4` - OpenAI GPT-4
- `gpt-4-turbo` - GPT-4 Turbo
- `gpt-3.5-turbo` - GPT-3.5 Turbo
- `claude-3-opus` - Anthropic Claude 3 Opus
- `claude-3-sonnet` - Claude 3 Sonnet
- `gemini-pro` - Google Gemini Pro

**规则引擎类型：**
- `custom_rules` - 自定义规则集
- `regex_v1` - 正则表达式规则 v1
- `template_parser` - 模板解析器
- `keyword_matcher` - 关键词匹配器

**混合类型：**
- `rule_gpt4` - 规则 + GPT-4
- `template_claude` - 模板 + Claude

**查询示例：**
```sql
-- 比较不同模型的效果
SELECT model_name, AVG(confidence) 
FROM extractions e
JOIN states s ON e.id = (SELECT extraction_id FROM state_evidence WHERE extraction_id = e.id LIMIT 1)
GROUP BY model_name;

-- 查找特定模型的抽取结果
SELECT * FROM extractions WHERE model_name = 'gpt-4';
```

### 3. prompt_version（prompt 版本）

**作用：** 记录使用的 prompt 版本（仅对 LLM 有意义）

**命名建议：**
- 语义化版本：`v1.0`, `v1.1`, `v2.0`
- 日期版本：`2024-04-01`, `2024-04-15`
- 功能版本：`basic`, `enhanced`, `with_examples`

**可为空：**
- 规则引擎不需要 prompt，可以为 `NULL`
- 或者用版本号表示规则集版本

**查询示例：**
```sql
-- 比较不同 prompt 版本的效果
SELECT prompt_version, COUNT(*) 
FROM extractions 
WHERE extractor_type = 'llm'
GROUP BY prompt_version;

-- A/B 测试：比较两个 prompt 版本
SELECT prompt_version, AVG(extraction_quality)
FROM extractions
WHERE model_name = 'gpt-4' AND prompt_version IN ('v1.0', 'v2.0')
GROUP BY prompt_version;
```

## 代码变更

### save_extraction 函数

**旧版本：**
```python
def save_extraction(
    chunk_id: int, 
    result: ExtractionResult, 
    model_version: str = "v0.1"
) -> int:
    cursor.execute("""
        INSERT INTO extractions (chunk_id, extraction_json, model_version)
        VALUES (?, ?, ?)
    """, (chunk_id, json.dumps(...), model_version))
```

**新版本：**
```python
def save_extraction(
    chunk_id: int,
    result: ExtractionResult,
    extractor_type: str = "rule_based",
    model_name: Optional[str] = None,
    prompt_version: Optional[str] = None
) -> int:
    """保存抽取结果到数据库
    
    Args:
        chunk_id: chunk ID
        result: 抽取结果对象
        extractor_type: 抽取器类型（llm, rule_based, hybrid）
        model_name: 模型名称（如 gpt-4, claude-3, custom_rules）
        prompt_version: prompt 版本（如 v1.0, v2.1）
    """
    cursor.execute("""
        INSERT INTO extractions (chunk_id, extraction_json, 
                                extractor_type, model_name, prompt_version)
        VALUES (?, ?, ?, ?, ?)
    """, (chunk_id, json.dumps(...), 
          extractor_type, model_name, prompt_version))
```

## 使用示例

### 场景 1：LLM 抽取

```python
from layers.middle_layer import save_extraction, ExtractionResult

result = extract_with_gpt4(chunk_text)  # 假设的抽取函数

save_extraction(
    chunk_id=1,
    result=result,
    extractor_type='llm',
    model_name='gpt-4-turbo',
    prompt_version='v2.1'
)
```

### 场景 2：规则引擎抽取

```python
result = extract_with_rules(chunk_text)

save_extraction(
    chunk_id=1,
    result=result,
    extractor_type='rule_based',
    model_name='custom_rules',
    prompt_version=None  # 规则引擎不需要 prompt
)
```

### 场景 3：混合方式

```python
# 先用规则预处理
preprocessed = preprocess_with_rules(chunk_text)
# 再用 LLM 精炼
result = refine_with_llm(preprocessed)

save_extraction(
    chunk_id=1,
    result=result,
    extractor_type='hybrid',
    model_name='rule_gpt4',
    prompt_version='v1.0'
)
```

### 场景 4：效果对比

```python
# 测试多个配置
configs = [
    ('llm', 'gpt-4', 'v1.0'),
    ('llm', 'gpt-4', 'v2.0'),
    ('llm', 'claude-3-opus', 'v1.0'),
    ('rule_based', 'custom_rules', None)
]

for extractor_type, model_name, prompt_version in configs:
    result = extract(chunk_text, extractor_type, model_name, prompt_version)
    save_extraction(
        chunk_id=1,
        result=result,
        extractor_type=extractor_type,
        model_name=model_name,
        prompt_version=prompt_version
    )
```

## Migration 影响

### 对现有数据库

**方式 1：重建（推荐）**
```bash
python main.py --init
```

**方式 2：迁移脚本（如果需要保留数据）**
```python
# 假设旧数据的 model_version 格式为 "gpt4-v1.0" 或 "rules-v1"
cursor.execute("SELECT id, model_version FROM extractions")
for row in cursor.fetchall():
    extraction_id = row['id']
    old_version = row['model_version']
    
    # 解析旧版本字符串（根据实际格式调整）
    if 'gpt' in old_version.lower():
        extractor_type = 'llm'
        model_name = 'gpt-4'
        prompt_version = old_version.split('-')[-1]
    elif 'rule' in old_version.lower():
        extractor_type = 'rule_based'
        model_name = 'custom_rules'
        prompt_version = None
    else:
        extractor_type = 'rule_based'
        model_name = None
        prompt_version = old_version
    
    # 更新到新字段
    cursor.execute("""
        UPDATE extractions 
        SET extractor_type = ?, model_name = ?, prompt_version = ?
        WHERE id = ?
    """, (extractor_type, model_name, prompt_version, extraction_id))
```

## 验证结果

✅ extractions 表已移除 `model_version` 字段  
✅ 新增 `extractor_type`, `model_name`, `prompt_version` 三个字段  
✅ save_extraction 函数更新完成  
✅ 测试通过：
- LLM 类型（gpt-4, v1.0）✓
- 规则类型（custom_rules, NULL）✓

## 未来扩展

1. **添加性能指标**
   - 添加 `processing_time` 字段记录处理耗时
   - 用于性能对比

2. **添加成本追踪**
   - 添加 `token_count`, `cost` 字段
   - 统计 LLM API 成本

3. **添加质量评分**
   - 添加 `quality_score` 字段
   - 人工标注或自动评估

4. **支持多版本对比**
   - 同一 chunk 可以有多个 extraction
   - 通过 A/B 测试选择最优配置

---

日期：2026-04-05  
变更类型：refactor (schema)  
影响范围：extractions 表, save_extraction 函数
