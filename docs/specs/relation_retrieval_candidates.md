# Relation And Retrieval Candidate Fate Spec

## Goal

在不扩大当前仓库边界的前提下，为 `relation_candidates` 与 `retrieval_candidates` 定义正式命运层。

这一阶段采用“候选暂存 + 裁决层”方案：

- `retrieval_candidates` 可以进入中间层候选池，等待确认、拒绝或后续补充。
- `relation_candidates` 不直接写入正式 `relations`，除非两端对象已经能稳定映射到正式 id。
- 无法稳定映射的关系先作为 pending relation candidate 保留，而不是伪装成正式关系。

任务完成后，应满足以下事实：

- 抽取 JSON 中的检索候选不再只停留在 `extraction_json` 内。
- 抽取 JSON 中的关系候选有可追踪的 pending 命运。
- 正式 `relations` 表只保存已经通过裁决、两端可定位的关系。
- 重复运行聚合不会导致同一 chunk/extraction 的候选证据无限增长。

## Problem Focus

### 1. 候选字段已经存在，但主链路没有消费

当前 `ExtractionResult` 已包含：

- `relation_candidates`
- `retrieval_candidates`

数据库也已经存在：

- `relations`
- `retrieval_candidates`

但主流程目前主要消费 `state_candidates`。关系和检索候选大多只留在 `extractions.extraction_json` 里。

### 2. relation candidate 不能直接等同于正式 relation

`RelationCandidate` 的 source/target 是自然语言文本，而正式 `relations` 表要求：

- `source_type`
- `source_id`
- `target_type`
- `target_id`

在主体归属、canonical state、实体注册等能力稳定前，直接把自由文本关系写入正式 `relations` 会制造不可靠图谱。

### 3. retrieval candidate 需要幂等证据累计

当前已有 `add_retrieval_candidate()`，但正式接入聚合时必须避免重复运行导致：

- `evidence_count` 虚增
- `source_chunk_ids` 重复
- 同一 extraction 反复贡献相同候选

## Candidate Fate Model

### 1. Retrieval Candidate

默认命运：

- 进入 `retrieval_candidates` 表。
- `decision_status` 初始为 `pending`。
- 按 `surface_form` 或后续可用的 normalized key 聚合。
- 证据来源至少应包含 chunk 维度；如果后续 schema 支持，也应包含 extraction 维度。

准入要求：

- `surface_form` 非空。
- `priority` 归一化到 0-10。
- 重复聚合同一候选时保持幂等。

### 2. Relation Candidate

默认命运：

- 不直接写入正式 `relations`。
- 先进入 pending relation candidate 持久化层，或等价的候选观察记录。
- 保留 source/target 原文、relation_type、context、confidence、chunk_id、extraction_id、decision_status。

晋升为正式 relation 的条件：

- source 与 target 均能稳定映射到正式对象。
- source_type/source_id/target_type/target_id 不依赖临时自然语言猜测。
- relation_type 通过最小词表或裁决规则。

如果这些条件不满足：

- 保持 `pending`。
- 或被显式标记为 `rejected`。
- 不写入正式 `relations`。

## Persistence Boundary

### Existing Tables

可复用：

- `retrieval_candidates`
- `relations`
- `extractions`
- `chunks`

### Possible Minimal Additions

如果当前 schema 无法表达 pending relation candidate，建议新增轻量表，例如：

- `relation_candidates`

最小字段语义：

- `source_text`
- `target_text`
- `relation_type`
- `context`
- `confidence`
- `chunk_id`
- `extraction_id`
- `decision_status`
- `promoted_relation_id`
- `created_at`
- `updated_at`

字段名可在实现时调整，但必须保留“候选”和“正式关系”的语义分离。

## Prompt, Aggregator, And Middle Layer Boundary

### Prompt / Extractor

- 可以继续输出 `relation_candidates` 与 `retrieval_candidates`。
- 不负责把 relation candidate 晋升为正式 relation。
- 不负责生成数据库 id。

### Aggregator

- 读取 extraction JSON 中的 relation/retrieval candidates。
- 执行最小规范化、准入和幂等处理。
- 对 relation candidate 做 pending 持久化，而不是默认写正式 `relations`。

### Middle Layer

- 提供候选写入与幂等接口。
- 提供候选统计。
- 只有在映射可靠时，才提供正式 relation 写入路径。

### Output Layer

- 本阶段不要求消费这些候选。
- 后续 profile 或诊断输出可以基于 pending candidates 做提示，但不能把 pending candidate 展示成已确认事实。

## Non-goals

本阶段明确不解决以下问题：

- 不实现完整关系图谱。
- 不实现向量检索、联网搜索或外部知识库。
- 不实现主体 registry、alias 管理或实体解析系统。
- 不要求输出层展示 relation/retrieval candidates。
- 不把自然语言 source/target 直接伪装成正式 `relations`。
- 不重新定义 extraction JSON 的全部 schema。
- 不解决第三阶段 canonical state identity。

## In Scope

- 定义 retrieval candidate 的正式落库与幂等规则。
- 定义 relation candidate 的 pending 命运。
- 明确 relation candidate 晋升为正式 relation 的条件。
- 明确 aggregator 与 middle layer 的职责边界。
- 明确必要的最小 schema 或接口扩展方向。
- 为后续实现提供可测试 acceptance criteria。

## Out Of Scope

- 当前 turn 内直接修改代码。
- 当前 turn 内修改 SQLite schema。
- 设计完整对象注册表。
- 让 output profile 消费关系或检索候选。
- 声称 relation/retrieval 主链路已经实现。

## Constraints

- keep current repository structure unless intentionally changed
- do not assume behavior that is not implemented
- mark uncertain facts as `需要人类确认`
- `input_docs/` 视为潜在敏感输入，不在 retained docs 中复制长篇原文
- 保持候选层与正式关系层分离
- 重复执行聚合必须保持幂等
- schema 变更应保持最小，并同步 `db/schema.py`、`layers/middle_layer.py`、`layers/aggregator.py` 与测试

## Acceptance Criteria

- spec 明确区分 pending relation candidate 与正式 relation。
- spec 明确 retrieval candidate 可先落库，但必须幂等。
- spec 明确 relation candidate 不应默认写入 `relations`。
- spec 明确 relation candidate 晋升为正式 relation 的最小条件。
- spec 明确 prompt、aggregator、middle layer、output layer 的职责边界。
- 后续实现若完成本 spec，应至少满足：
  - 聚合能从 extraction JSON 中读取 retrieval candidates 并写入候选池。
  - 重复聚合同一 extraction 不会虚增 retrieval evidence。
  - 聚合能从 extraction JSON 中读取 relation candidates 并保留 pending 记录。
  - 正式 `relations` 表不会出现无法映射 source/target id 的自由文本关系。

## Reference Files

- AGENTS.md
- docs/architecture.md
- docs/testing.md
- docs/specs/state_aggregation.md
- docs/plans/state_aggregation.md
- docs/specs/state_subject_attribution.md
- docs/specs/state_foundation.md
- .github/EXTRACTION_JSON_SCHEMA.md
- db/schema.py
- layers/middle_layer.py
- layers/aggregator.py
- layers/extractors/prompts.py
