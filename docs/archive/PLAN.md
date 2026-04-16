# 项目改进计划

**项目名称**: Markdown State Tracker  
**当前版本**: v0.1 (原型阶段)  
**最后更新**: 2026-04-15

---

## 📊 当前状态概览

### ✅ 已完成的基础设施

- [x] 三层架构框架（输入层 → 中间层 → 输出层）
- [x] SQLite 数据库 Schema（8张表）
- [x] 文档扫描与 hash 变更检测
- [x] 智能 chunk 切分（段落/句子，含 offset）
- [x] ExtractionResult 结构化 schema 定义
- [x] 固定骨架的输出生成
- [x] 输出快照版本控制
- [x] state_evidence 多对多关联表
- [x] extractions 元数据字段（extractor_type, model_name, prompt_version）
- [x] 文件日志系统（控制台摘要 + 轮转文件日志）

### 🔎 本地验证结果（2026-04-15）

- [x] `python main.py --stats` 可正常执行
- [x] 当前数据库中已有 `documents=4`、`chunks=122`、`extractions=104`
- [ ] 当前数据库中 `states=0`、`state_evidence=0`、`relations=0`、`retrieval_candidates=0`
- [ ] `output/status.md` 只能生成固定骨架，尚无实际状态项

### ❌ 当前阻塞正常产出的缺口

- [x] **抽取器实现** ✅ 2026-04-07（LLM 抽取器已实现）
- [ ] **聚合逻辑未接通**（`state_candidates` 尚未写入 `states/state_evidence`）
- [ ] **失败 chunk 状态流转错误**（部分 chunk 抽取失败后，文档仍可能被标记为 `processed`，后续不会自动重试）
- [ ] **关系/检索候选未落库**（`relation_candidates` / `retrieval_candidates` 仍停留在 `extraction_json`）
- [ ] **LLM 输出健壮性不足**（存在 fenced JSON、超时、`JSONDecodeError` 等问题）
- [ ] **语义去重仍较弱**（状态合并目前仍是精确匹配）
- [ ] **测试覆盖不足**（已有 schema、logging、font 相关测试，输入/聚合/输出/失败重试仍缺）

---

## 🎯 改进任务清单

### 🔴 高优先级（核心功能）

#### 任务 1: 实现 LLM 抽取器（LLM-based Extractor）
**状态**: ✅ 已完成  
**优先级**: P0（最高）  
**完成日期**: 2026-04-07

**目标**:
- 从 chunk.text 中提取基本的实体、事件、状态候选
- 填充 ExtractionResult 对象
- 集成到主流程中

**验收标准**:
- [x] 创建 `layers/extractors/` 模块（含 llm_extractor.py）
- [x] 实现 `LLMExtractor.extract(text) -> ExtractionResult`
- [x] 提取实体（人名、工具名、时间等）
- [x] 提取状态候选（关键短语）
- [x] 在 `main.py` 中集成抽取流程
- [x] 支持 .env 配置和 --skip-extraction 参数

**实现方案**:
- 使用 OpenAI API (gpt-4o-mini)
- 规则预处理：提取显式日期、Markdown 标记实体作为 hints
- JSON Schema 强制输出格式
- 规则后处理：schema 校验、置信度修正、去重
- 重试机制：3次重试，指数退避

---

#### 任务 2: 实现聚合逻辑（Aggregation）
**状态**: ⏳ 待开始  
**优先级**: P0  
**预估工作量**: 中等（3-5 小时）

**目标**:
- 打通 `extractions -> states -> output` 主链路
- 将 `extractions.extraction_json` 中的 `state_candidates` 转换为 `states` / `state_evidence` 表记录
- 保证聚合步骤可重复执行且不会无限重复写入

**验收标准**:
- [ ] 创建 `layers/aggregator.py`
- [ ] 实现 `aggregate_extractions()` 或等价主函数
- [ ] 从 `extractions` 读取并解析 `ExtractionResult`
- [ ] 将每个 `state_candidate` 规范化为 `category/subtype/summary/detail/confidence`
- [ ] 调用 `upsert_state()` 写入 `states`
- [ ] 同时写入 `state_evidence`，至少关联 `chunk_id` 和 `extraction_id`
- [ ] 重复运行聚合时，不产生重复 `state_evidence` 和状态爆炸
- [ ] 在 `main.py` 中于输出前调用聚合逻辑
- [ ] 在现有样本数据上跑通后，`active_states > 0`
- [ ] `output/status.md` 不再只有空骨架

**技术方案**:
```python
def aggregate_extractions():
    # 1. 读取 extractions + chunks + documents
    # 2. 解析 extraction_json -> ExtractionResult
    # 3. 遍历 state_candidates 并做最小规范化
    # 4. 调用 upsert_state() 合并到 states
    # 5. 为每个 state 写入 state_evidence(chunk_id, extraction_id)
    # 6. 返回聚合统计，供 main.py 打印和记录日志
```

---

#### 任务 3: 补充单元测试
**状态**: 🟡 部分完成  
**优先级**: P1  
**预估工作量**: 中等（3-4 小时）

**目标**:
- 为核心模块添加可批量执行的测试覆盖
- 优先统一到 `pytest` 入口，但允许兼容现有 `unittest`
- 当前已存在 `test_extraction_schema.py`、`test_logging.py`、`test_font_filtering.py`

**验收标准**:
- [x] `test_extraction_schema.py` - 覆盖 ExtractionResult schema 往返
- [x] `test_logging.py` - 覆盖日志初始化、截断、重试、跳过抽取、成功抽取
- [x] `test_font_filtering.py` - 覆盖 font tag 清理与预处理
- [ ] 创建 `tests/` 目录
- [ ] `tests/test_input_layer.py` - 测试文档扫描、切分、变更检测
- [ ] `tests/test_middle_layer.py` - 测试状态管理、抽取保存
- [ ] `tests/test_output_layer.py` - 测试状态选择、文档生成
- [ ] `tests/test_extractor.py` - 测试抽取器（任务1完成后）
- [ ] `tests/test_aggregator.py` - 测试聚合逻辑（任务2完成后）
- [ ] `tests/test_pipeline_recovery.py` - 测试失败 chunk 的状态流转与重试
- [ ] 测试覆盖率 > 60%

**重点测试用例**:
```python
# test_input_layer.py
- test_chunk_document_simple()
- test_chunk_document_long_paragraph()
- test_chunk_offsets_accuracy()
- test_get_changed_documents()

# test_middle_layer.py
- test_upsert_state_insert()
- test_upsert_state_update()
- test_state_evidence_association()

# test_output_layer.py
- test_select_states_respects_limits()
- test_generate_markdown_format()
```

---

#### 任务 11: 修复失败 chunk 的状态流转与重试
**状态**: ⏳ 待开始  
**优先级**: P0  
**预估工作量**: 中等（2-4 小时）

**目标**:
- 修复“部分 chunk 抽取失败但文档被提前标记为 `processed`”的问题
- 保证失败 chunk 在后续运行中仍可进入待处理队列

**验收标准**:
- [ ] 明确 `documents.status` 的状态机（至少区分 `pending` / `processed` / `error` 或等价语义）
- [ ] 仅当文档下全部 chunks 完成抽取后，才标记文档为 `processed`
- [ ] 若某文档存在失败 chunk，下一次运行时 `get_pending_chunks()` 仍能重新取到
- [ ] 日志中明确记录失败 chunk 数、未完成文档数和重试结果
- [ ] 增加对应自动化测试

**技术方案**:
```python
def finalize_document_status(document_id):
    # 1. 统计该文档 chunks 总数 / 已抽取数
    # 2. 若全部完成 -> processed
    # 3. 若存在未完成或失败 -> 保持 pending / 标为 error
```

---

#### 任务 12: 落库关系候选与检索候选
**状态**: ⏳ 待开始  
**优先级**: P1  
**预估工作量**: 中等（2-4 小时）

**目标**:
- 将 `relation_candidates` / `retrieval_candidates` 从 `extraction_json` 接入中间层表结构
- 让数据库中的 `relations` / `retrieval_candidates` 不再长期为空

**验收标准**:
- [ ] 聚合或后处理阶段写入 `relations`
- [ ] 调用 `add_retrieval_candidate()` 写入 `retrieval_candidates`
- [ ] 关联 `chunk_id` 或 `extraction_id` 作为证据来源
- [ ] 重复运行时具备基本去重能力
- [ ] 在样本数据上可看到非零记录

---

### 🟡 中优先级（质量提升）

#### 任务 13: 增强 LLM 响应健壮性
**状态**: ⏳ 待开始  
**优先级**: P1  
**预估工作量**: 小（1-2 小时）

**目标**:
- 降低 fenced JSON、超时和脏响应对抽取流程的破坏
- 提升大批量处理时的稳定性

**验收标准**:
- [ ] 在 `json.loads()` 前清理 ```json fenced block 等常见包装
- [ ] 对空响应、无 `choices`、非 JSON 内容给出明确错误分类
- [ ] 将超时、JSON 解析失败、API 失败分别记录到日志
- [ ] 为典型异常场景补测试

---

#### 任务 4: 改进 Token 估算
**状态**: ⏳ 待开始  
**优先级**: P2  
**预估工作量**: 小（1 小时）

**目标**:
- 更精确的 token 估算，避免切分不当

**验收标准**:
- [ ] 评估方案：tiktoken vs 改进启发式
- [ ] 实现新的 `estimate_tokens()` 函数
- [ ] 对比测试旧/新估算的准确性
- [ ] 更新 `chunk_document()` 使用新估算

**技术方案**:
```python
# 方案 A: tiktoken (需要依赖)
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")
return len(enc.encode(text))

# 方案 B: 改进启发式（无依赖）
chinese = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
other = len(text) - chinese
return int(chinese * 1.3 + other * 0.3)
```

---

#### 任务 5: 重构 chunk_document()
**状态**: ⏳ 待开始  
**优先级**: P2  
**预估工作量**: 中等（2-3 小时）

**目标**:
- 简化代码逻辑，修复 offset 计算潜在 bug

**验收标准**:
- [ ] 拆分函数：`_chunk_by_paragraphs()`, `_chunk_by_sentences()`
- [ ] 重写 offset 跟踪逻辑（一次性构建位置映射）
- [ ] 增加边界情况测试
- [ ] 代码行数减少 30%+
- [ ] 通过所有现有测试

**重构方向**:
```python
def chunk_document(content, max_tokens):
    paragraphs = _split_paragraphs_with_offsets(content)
    chunks = []
    for para, offset in paragraphs:
        if estimate_tokens(para.text) > max_tokens:
            sub_chunks = _chunk_by_sentences(para, max_tokens)
            chunks.extend(sub_chunks)
        else:
            chunks.append(_merge_paragraphs([para], max_tokens))
    return chunks
```

---

#### 任务 6: 统一关联表设计
**状态**: ⏳ 待开始  
**优先级**: P2  
**预估工作量**: 小（1-2 小时）

**目标**:
- 将 `retrieval_candidates.source_chunk_ids` JSON 改为关联表

**验收标准**:
- [ ] 创建 `retrieval_evidence` 表
- [ ] 迁移现有数据（如有）
- [ ] 更新 `add_retrieval_candidate()` 逻辑
- [ ] 移除 `source_chunk_ids` 字段
- [ ] 更新文档说明

**Schema 变更**:
```sql
CREATE TABLE retrieval_evidence (
    id INTEGER PRIMARY KEY,
    candidate_id INTEGER NOT NULL,
    chunk_id INTEGER,
    extraction_id INTEGER,
    created_at REAL DEFAULT (julianday('now')),
    FOREIGN KEY (candidate_id) REFERENCES retrieval_candidates(id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE,
    FOREIGN KEY (extraction_id) REFERENCES extractions(id) ON DELETE CASCADE
);

-- 删除 retrieval_candidates.source_chunk_ids
ALTER TABLE retrieval_candidates DROP COLUMN source_chunk_ids;
```

---

#### 任务 7: 添加日志系统
**状态**: ✅ 已完成  
**优先级**: P2  
**完成日期**: 2026-04-11

**目标**:
- 为主流程提供可追踪的运行可观测性
- 保留控制台摘要输出，并同时写入轮转文件日志

**验收标准**:
- [x] 创建 `app_logging.py`
- [x] 配置日志格式、级别、轮转文件输出
- [x] 在主流程、输入层、抽取层、数据库层、输出层接入 logger
- [x] 保留控制台摘要输出，并支持 `--quiet`
- [x] 支持 `--log-level` / `--log-file`

**实现示例**:
```python
# app_logging.py
run_id = setup_logging(log_file="data/logs/pipeline.log", level="INFO")
logger = get_logger("pipeline")
log_event(logger, logging.INFO, "run_start", "Pipeline run started", stage="pipeline")
```

---

### 🟢 低优先级（锦上添花）

#### 任务 8: 配置文件支持
**状态**: ⏳ 待开始  
**优先级**: P3  
**预估工作量**: 小（1 小时）

**目标**:
- 支持通过配置文件覆盖默认设置

**验收标准**:
- [ ] 支持 `config.yaml` 或 `config.toml`
- [ ] 可配置：路径、token 限制、输出格式
- [ ] 向后兼容（无配置文件时用默认值）

---

#### 任务 9: 异常处理增强
**状态**: ⏳ 待开始  
**优先级**: P3  
**预估工作量**: 小（1 小时）

**目标**:
- 捕获常见错误，提供友好提示

**验收标准**:
- [ ] 文件不存在错误
- [ ] 数据库损坏错误
- [ ] Markdown 解析错误
- [ ] 输出目录权限错误
- [ ] 优雅降级策略

---

#### 任务 10: 数据库迁移工具
**状态**: ⏳ 待开始  
**优先级**: P3  
**预估工作量**: 中等（2-3 小时）

**目标**:
- 简单的 schema 版本管理

**验收标准**:
- [ ] 记录 schema 版本号
- [ ] 支持增量迁移脚本
- [ ] `--migrate` 命令自动升级
- [ ] 不使用重型框架（手写即可）

---

## 📝 实施策略

### 阶段 1: 核心功能（优先）
**目标**: 让系统能产出非空、可重复执行的状态结果  
**任务**: 1, 2, 11, 12  
**预估时间**: 4-6 天

### 阶段 2: 质量提升
**目标**: 提升代码质量和健壮性  
**任务**: 3, 13, 4, 5, 6, 7  
**预估时间**: 4-6 天

### 阶段 3: 完善优化
**目标**: 用户体验优化  
**任务**: 8, 9, 10  
**预估时间**: 2-3 天

---

## 📌 注意事项

1. **边界控制**: 所有改进必须在原型边界内，不扩大项目范围
2. **测试先行**: 重构前先补充测试，避免引入 bug
3. **渐进式**: 每个任务独立提交，便于回滚
4. **文档同步**: 代码改动后及时更新 CLAUDE.md 和 README.md

---

## 🔄 更新日志

### 2026-04-15 (更新 4)
- 📝 根据代码与日志核对，重新校准项目计划
- 确认当前 `states` / `state_evidence` / `relations` / `retrieval_candidates` 仍未接通
- 上调任务 2 范围：聚合逻辑必须直接打通到输出层
- 新增任务 11：修复失败 chunk 状态流转与重试
- 新增任务 12：落库关系候选与检索候选
- 新增任务 13：增强 LLM 响应健壮性

### 2026-04-15 (更新 3)
- ✅ 完成任务 7: 文件日志系统
- 新增 `app_logging.py`
- 主流程保留控制台摘要输出，同时写入轮转文件日志
- 支持 `--quiet`、`--log-level`、`--log-file`
- 🟡 任务 3 部分推进：新增 `test_logging.py`

### 2026-04-07 (更新 2)
- ✅ 完成任务 1: LLM 抽取器实现
- 创建 `layers/extractors/` 模块
- 实现 LLMExtractor 类（OpenAI API）
- 添加规则预处理和后处理
- 集成到 main.py 主流程
- 添加 .env 配置支持

### 2026-04-07
- ✅ 创建项目改进计划文档
- ✅ 定义 10 个改进任务
- ✅ 划分 3 个实施阶段

---

## ✅ 完成标记说明

每完成一个验收标准，在对应的 `[ ]` 中填写 `x` 变成 `[x]`。  
任务完成后，将任务状态从 `⏳ 待开始` 改为 `✅ 已完成`。

**示例**:
```markdown
#### 任务 1: 实现规则抽取器
**状态**: ✅ 已完成  
**完成日期**: 2026-04-10

**验收标准**:
- [x] 创建 `layers/extractors/rule_extractor.py`
- [x] 实现 `extract_from_chunk(text: str) -> ExtractionResult`
- [x] 提取实体（人名、工具名、时间等）
- [x] 提取状态候选（关键短语）
- [x] 在 `main.py` 中集成抽取流程
- [x] 端到端测试：输入 → 抽取 → 存储
```
