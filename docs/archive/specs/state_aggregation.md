# State Aggregation Spec

## Goal

在不改变当前仓库总体结构的前提下，打通 `state_candidates -> states -> output` 主链路。

任务完成后，应满足以下事实：

- `layers/aggregator.py` 成为聚合入口
- 已存在的 `extractions.extraction_json` 可以被解析为 `ExtractionResult`
- `state_candidates` 被最小规范化后写入 `states`
- 每个聚合后的 state 都有对应的 `state_evidence`
- 已失去全部证据的孤儿 state 会被归档，避免继续参与输出
- `main.py` 在输出前执行聚合
- 在现有样本数据上，`python main.py --stats` 可观察到 `active_states > 0`
- `output/status.md` 不再只有空骨架

## Non-goals

本任务明确不解决以下问题：

- 不在本任务中修复失败 chunk 的状态流转
- 不在本任务中落库 `relation_candidates`
- 不在本任务中落库 `retrieval_candidates`
- 不在本任务中引入语义检索、embedding 或向量数据库
- 不在本任务中引入复杂语义去重，只保留当前“最小可用”的合并策略
- 不在本任务中修改 SQLite schema

## In Scope

- 新增 `layers/aggregator.py`
- 从 `extractions` 读取 JSON 数据并反序列化为 `ExtractionResult`
- 对 `state_candidates` 做最小规范化
- 调用 `upsert_state()` 写入 `states`
- 为 state 写入 `state_evidence`
- 归档已无证据支撑的孤儿 state
- 在 `main.py` 中接入聚合调用与日志
- 为聚合链路补最小自动化测试或可重复验证路径

## Out Of Scope

- `documents.status` 状态机设计修复
- `relations` / `retrieval_candidates` 的实际写入
- `llm_extractor.py` 的 JSON 健壮性增强
- `chunk_document()` 重构
- 新增配置文件格式
- 数据库迁移机制

## Constraints

- keep current repository structure unless intentionally changed
- do not assume behavior that is not implemented
- mark uncertain facts as `需要人类确认`
- 保持当前三层结构，不把聚合逻辑塞回 `main.py` 或 `output_layer.py`
- 保持当前 schema 不变，优先复用 `states`、`state_evidence`、`extractions`
- 不能把“规划中的聚合能力”写成“已经实现的现状”
- 仅实现最小可用规范化，不扩展为平台级状态管理系统
- `input_docs/` 视为潜在敏感输入，不在文档中复制大段示例内容
- 当前 `subtype` 的权威词表并未集中定义；若需要冻结或扩展词表，`需要人类确认`

## Acceptance Criteria

- 新增 `layers/aggregator.py`，且存在单一主入口函数，例如 `aggregate_extractions()`
- 聚合函数能读取 `extractions + chunks + documents`，并逐条解析 `ExtractionResult`
- 每个有效 `state_candidate` 都会映射到 `category/subtype/summary/detail/confidence`
- 聚合会调用 `upsert_state()`，并为每条聚合结果写入至少一条 `state_evidence`
- 重复执行聚合时，不会导致同一 extraction 对应的 evidence 无限制重复增长
- 聚合结束后，失去全部证据的活跃 state 会被归档而不是继续输出
- `main.py` 在 `generate_output()` 前调用聚合逻辑
- 运行 `python main.py --stats` 时，现有样本数据下可看到 `active_states > 0`
- 运行主流程后，`output/status.md` 中至少出现一个非“暂无数据”的状态分组

## Reference Files

- AGENTS.md
- docs/architecture.md
- docs/archive/PLAN.md
- main.py
- layers/middle_layer.py
- layers/output_layer.py
- db/schema.py
- .github/EXTRACTION_JSON_SCHEMA.md
