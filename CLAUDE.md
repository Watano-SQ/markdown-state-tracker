# CLAUDE.md - AI 协助开发指南

这份文档帮助 AI 助手（如 Claude）快速理解项目结构，以便更好地协助开发。

## 项目概览

**项目名称：** Markdown State Tracker  
**核心目标：** 将本地 Markdown 文档转化为可更新、可复用的状态文档  
**技术栈：** Python 3.7+ | SQLite 3 | Markdown  
**架构模式：** 三层处理流程（输入层 → 中间层 → 输出层）

## 核心设计原则

1. **最小可行** - 不过度工程化，优先简单实现
2. **边界明确** - 这是原型，不是平台级产品
3. **模块清晰** - 三层分离，便于替换和扩展
4. **受控边界** - 输出有固定骨架，不是无限列表
5. **Token 分层控制** - 不一次性把全部数据塞给模型

## 项目结构

```
markdown-state-tracker/
├── config.py                    # 全局配置（路径、参数）
├── main.py                      # 主入口，编排完整流程
│
├── db/                          # 数据库层
│   ├── __init__.py
│   ├── schema.py                # 数据库 Schema 定义（7张表）
│   └── connection.py            # SQLite 连接管理（单例模式）
│
├── layers/                      # 三层处理逻辑
│   ├── __init__.py
│   ├── input_layer.py           # 输入层：扫描、切分、变更检测
│   ├── middle_layer.py          # 中间层：状态存储与管理
│   └── output_layer.py          # 输出层：按需选取、文档生成
│
├── data/                        # 数据存储目录（不提交）
│   └── state.db                 # SQLite 数据库
│
├── input_docs/                  # 输入文档目录
│   └── *.md                     # 待处理的 Markdown 文档
│
└── output/                      # 输出目录
    └── status.md                # 生成的状态文档
```

## 数据流

```
Markdown 文档
    ↓
[输入层] 扫描 → 变更检测 → Chunk 切分 → 抽取（TODO）
    ↓
[中间层] SQLite 存储（documents, chunks, extractions, states, relations...）
    ↓
[输出层] 按需选取状态 → 生成 Markdown → 保存快照
    ↓
status.md
```

## 数据库 Schema

### 核心表（7张）

1. **documents** - 文档元信息
   - `id`, `path`, `title`, `modified_time`, `content_hash`, `status`
   - 用途：追踪文档变更，避免重复处理

2. **chunks** - 文档切片（仅保存正文切分结果）
   - `id`, `document_id`, `chunk_index`, `text`, `token_estimate`
   - `start_offset`, `end_offset` - 在原文中的位置（可选）
   - `section_label` - 所属章节标签（可选）
   - 用途：将长文档切分为可处理的片段，不包含文档级 metadata
   - **职责边界**：只负责正文切分，文档级信息（标题、时间等）保存在 documents 表

3. **extractions** - 抽取结果（JSON 格式）
   - `id`, `chunk_id`, `extraction_json`, `model_version`
   - 用途：存储原始抽取结果，便于调试和回溯

4. **states** - 聚合后的状态项
   - `id`, `category`, `subtype`, `summary`, `detail`, `status`, `confidence`
   - 用途：核心状态存储，支持 active/archived
   - 分类：dynamic（动态）/ static（稳定）

5. **relations** - 状态间关系
   - `id`, `source_type`, `source_id`, `target_type`, `target_id`, `relation_type`
   - 用途：表达状态项之间的关联

6. **retrieval_candidates** - 待确认的候选对象
   - `id`, `surface_form`, `normalized_name`, `type_guess`, `decision_status`
   - 用途：处理语义不确定但重要的实体

7. **output_snapshots** - 输出快照
   - `id`, `content_md`, `created_at`, `source_state_version`
   - 用途：版本控制，追踪输出历史

## 关键模块说明

### 1. config.py

全局配置，定义路径和参数：
- `PROJECT_ROOT` - 项目根目录
- `INPUT_DIR` - 输入文档目录
- `OUTPUT_FILE` - 输出文档路径
- `DB_PATH` - 数据库路径

**修改建议：** 需要改路径时直接编辑此文件

### 2. db/schema.py

定义完整的数据库 Schema：
- `SCHEMA_SQL` - 包含所有 CREATE TABLE 和 CREATE INDEX 语句
- 采用 SQLite 内置的 `julianday()` 记录时间

**修改建议：** 
- 新增表时更新此文件
- 修改字段后需要 `--init` 重建数据库

### 3. db/connection.py

数据库连接管理：
- `get_connection()` - 获取单例连接
- `init_db(force=False)` - 初始化 Schema
- `close_connection()` - 关闭连接

**注意事项：**
- 启用了 `PRAGMA foreign_keys = ON`
- 使用 `Row` factory 方便字典访问

### 4. layers/input_layer.py

**核心职责：** 文档扫描、切分、变更检测

**关键函数：**

```python
scan_documents(input_dir) 
    → List[DocumentInfo]
    # 扫描目录下所有 .md 文件，提取元信息

get_changed_documents(documents) 
    → (new_docs, modified_docs)
    # 基于 hash 识别新增和修改的文档

chunk_document(content, max_tokens=500) 
    → List[Chunk]
    # 按段落/句子智能切分，控制 token 数

process_input() 
    → dict
    # 主流程：扫描 → 识别变更 → 切分 → 存储
```

**切分策略：**
1. 优先按空行分段落
2. 超长段落按句子切分（句号、问号、感叹号）
3. 保证每个 chunk 不超过 max_tokens

**修改建议：**
- 调整切分粒度：修改 `max_tokens` 参数
- 改进标题提取：编辑 `extract_title()`
- 更精确的 token 估算：改进 `estimate_tokens()`

### 5. layers/middle_layer.py

**核心职责：** 状态存储、查询、管理

**关键函数：**

```python
save_extraction(chunk_id, result, model_version)
    # 保存抽取结果（JSON 格式）

get_pending_chunks() 
    → List[dict]
    # 获取待抽取的 chunks（未处理的）

upsert_state(category, subtype, summary, ...)
    → state_id
    # 插入或更新状态项（简单匹配去重）

add_retrieval_candidate(surface_form, ...)
    → candidate_id
    # 添加需要进一步确认的候选对象

get_active_states(category, limit)
    → List[dict]
    # 查询活跃状态项

archive_state(state_id)
    # 归档状态项
```

**ExtractionResult 数据结构：**
```python
@dataclass
class ExtractionResult:
    events: List[Dict]         # 事件列表
    states: List[Dict]         # 状态列表
    entities: List[Dict]       # 实体列表
    relations: List[Dict]      # 关系列表
    candidates: List[Dict]     # 候选对象
```

**修改建议：**
- 实现抽取器：填充 `ExtractionResult` 的逻辑
- 改进状态合并：优化 `upsert_state()` 的匹配规则
- 添加语义去重：集成向量相似度匹配

### 6. layers/output_layer.py

**核心职责：** 从中间层按需选取，生成固定结构的文档

**关键配置：**

```python
OUTPUT_CONFIG = {
    'dynamic': {
        'title': '动态状态',
        'subtypes': {
            'ongoing_project': '进行中的项目',
            'recent_event': '近期事件',
            'pending_task': '待办事项',
            'active_interest': '当前关注',
        },
        'max_items_per_subtype': 10,
    },
    'static': { ... }
}
```

**关键函数：**

```python
select_states_for_output() 
    → Dict[category][subtype]
    # 按配置从数据库选取状态项（不是全部导出）

generate_status_document(selected_states)
    → str (Markdown)
    # 生成固定骨架的 Markdown 文档

generate_output()
    → dict
    # 主流程：选取 → 生成 → 保存快照
```

**输出边界控制：**
- 每个子类型有 `max_items_per_subtype` 上限
- 只输出 `status='active'` 的状态
- 按 `last_updated` 倒序，最新的在前

**修改建议：**
- 添加新分类：扩展 `OUTPUT_CONFIG`
- 调整输出上限：修改 `max_items_per_subtype`
- 自定义模板：编辑 `generate_status_document()`

### 7. main.py

**核心职责：** 编排完整流程，提供 CLI 接口

**主流程：**
```python
run_pipeline():
    1. init_db()                  # 初始化数据库
    2. process_input()            # 输入层处理
    3. get_pending_chunks()       # 检查待处理项
    4. generate_output()          # 输出层生成
    5. 返回处理统计
```

**命令行参数：**
- `--init` - 强制重建数据库
- `--stats` - 查看统计信息
- `--quiet` - 安静模式

## 当前开发状态

### ✅ 已实现

- [x] 完整的三层架构框架
- [x] 文档扫描与 hash 变更检测
- [x] 智能 chunk 切分（段落/句子）
- [x] SQLite Schema（7张表）
- [x] 状态项 CRUD 接口
- [x] 固定骨架的输出生成
- [x] 输出快照版本控制

### 🚧 待实现（核心功能）

1. **抽取器实现** - 最高优先级
   - 从 `chunk.text` 提取结构化信息
   - 填充 `ExtractionResult` 对象
   - 可选方案：LLM 抽取 / 规则引擎 / 混合方式

2. **抽取结果聚合**
   - 将多个 `ExtractionResult` 合并为 `states`
   - 去重和冲突解决

3. **状态更新策略**
   - 新文档如何更新已有状态
   - 时间衰减（可选）
   - 归档触发规则

## 协助开发指南

### 如果要添加新功能

1. **确认是否符合项目边界**
   - ✅ 优化现有流程
   - ✅ 实现预留接口（如抽取器）
   - ❌ 引入重型依赖
   - ❌ 改造成平台级系统

2. **选择正确的层级**
   - 输入相关 → `layers/input_layer.py`
   - 状态管理 → `layers/middle_layer.py`
   - 输出格式 → `layers/output_layer.py`
   - 全局配置 → `config.py`

3. **保持模块清晰**
   - 单一职责原则
   - 避免跨层直接调用
   - 通过数据库传递状态

### 如果要修改 Schema

1. 编辑 `db/schema.py`
2. 运行 `python main.py --init` 重建
3. 更新相关的增删改查代码
4. 更新此文档的 Schema 说明

### 如果要实现抽取器

**推荐步骤：**

1. 在 `layers/middle_layer.py` 中创建抽取函数：
   ```python
   def extract_from_chunk(chunk_text: str) -> ExtractionResult:
       # 你的抽取逻辑
       return ExtractionResult(...)
   ```

2. 在 `main.py` 的主流程中添加抽取步骤：
   ```python
   pending = get_pending_chunks()
   for chunk in pending:
       result = extract_from_chunk(chunk['text'])
       save_extraction(chunk['id'], result)
       # 聚合到 states 表
   ```

3. 实现聚合逻辑，将 `ExtractionResult` 写入 `states` 表

### 调试建议

**查看数据库内容：**
```bash
sqlite3 data/state.db
.tables
SELECT * FROM documents;
SELECT * FROM states;
```

**查看处理统计：**
```bash
python main.py --stats
```

**强制重新处理：**
```bash
python main.py --init  # 清空数据库
python main.py         # 重新处理
```

## 常见修改场景

### 场景 1：调整输出分类

编辑 `layers/output_layer.py` 的 `OUTPUT_CONFIG`：
```python
'dynamic': {
    'subtypes': {
        'your_new_type': '你的新分类',  # 添加这一行
    }
}
```

### 场景 2：改变 chunk 大小

编辑 `layers/input_layer.py` 的 `process_input()`：
```python
chunks = chunk_document(doc.content, max_tokens=1000)  # 改这里
```

### 场景 3：添加新的状态字段

1. 修改 `db/schema.py` 的 `states` 表定义
2. 重建数据库：`python main.py --init`
3. 更新 `layers/middle_layer.py` 的 `upsert_state()`

### 场景 4：自定义输出格式

编辑 `layers/output_layer.py` 的 `generate_status_document()`

## 项目限制（不要突破）

- ❌ 不要引入 PostgreSQL / MongoDB 等重型数据库
- ❌ 不要构建 Web 服务或 REST API
- ❌ 不要添加联网搜索功能
- ❌ 不要做完整的知识图谱系统
- ❌ 不要把输出改成无限增长的列表

这些超出了"最小可行原型"的边界。

## 代码风格

- 使用类型提示：`def func(x: str) -> int:`
- 清晰的函数命名，避免缩写
- 关键逻辑添加注释
- 数据库操作用参数化查询（防 SQL 注入）
- 保持函数简短（< 50 行为佳）

## 测试建议

当前项目没有单元测试（原型阶段），但应手工测试：

1. 空目录测试
2. 单文档测试
3. 多文档测试
4. 文档修改后增量更新测试
5. 极端情况（超长文档、空文档、特殊字符）

---

**更新日期：** 2026-04-03  
**适用版本：** v0.1 (初始原型)
