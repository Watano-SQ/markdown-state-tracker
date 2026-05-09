# Contextual Bundle Reading View Plan

## Task

任务名：`output_reading_roles_and_clusters`

中文标题：输出层阅读角色与阅读簇修正

这是当前 `contextual_bundle_reading_view` 的 output-only 增量修正。目标是把输出层从“按主体和主题机械展示状态”推进到“按阅读角色和阅读簇组织证据状态”。

## Boundaries

本轮只改：

- `layers/output_layer.py`
- `tests/test_output_layer.py`
- `docs/specs/contextual_bundle_reading_view.md`
- `docs/plans/contextual_bundle_reading_view.md`
- `docs/changes.md`
- `docs/architecture.md`

本轮不改：

- `db/schema.py`
- `layers/aggregator.py`
- `layers/middle_layer.py`
- `layers/extractors/prompts.py`
- `.github/EXTRACTION_JSON_SCHEMA.md`
- `tools/observation_support_audit.py`

明确非目标：

- 不新增 SQLite 表。
- 不新增主体注册表。
- 不做正式关系持久化。
- 不做 retrieval 生命周期裁决。
- 不把 `relation_candidates` 当成正式 `relations`。
- 不把 LLM 作为默认输出依赖。
- 不把 `needs_context` 渲染成正式 Markdown 章节。
- 不把输出层归组合并反向写回 state identity。

## Step 1

- Goal:
  修订 active spec，冻结 `output_reading_roles_and_clusters` 的输出层契约。
- Required content:
  - 输出角色
  - 单状态可读性审查
  - 阅读簇归组
  - 短语用状态不是旧式“低信息评价”
  - subject identity 不被 output layer 改写
  - LLM 审查只是可选审查器，不生成事实
- Files likely touched:
  `docs/specs/contextual_bundle_reading_view.md`
  `docs/plans/contextual_bundle_reading_view.md`
  `docs/changes.md`
  `docs/architecture.md`
- Validation:
  active spec 不再把“低信息评价类 state”作为正式内部分类。
- Stop condition:
  后续实现者无需再决定短句是否按长度降级、阅读簇是否等于主体合并、LLM 审查是否能生成新事实。

## Step 2

- Goal:
  先补 output layer 回归测试，不先改实现。
- Files likely touched:
  `tests/test_output_layer.py`
- Validation:
  新增或改名以下测试：
  - `test_short_pragmatic_evaluation_is_not_low_information`
  - `test_short_sentence_without_subject_or_object_is_deferred`
  - `test_short_blocker_can_support_project_context`
  - `test_aurora_board_groups_primary_and_supporting_states`
  - `test_river_incident_keeps_multiple_subjects_in_one_reading_cluster`
  - `test_unrelated_sections_do_not_merge_across_subjects`
- Stop condition:
  测试能清楚表达短语用状态、单状态可读性审查、多主体阅读簇和防误合并的预期行为。

## Step 3

- Goal:
  实现 `ReadingDecision` 与单状态可读性审查。
- Files likely touched:
  `layers/output_layer.py`
  `tests/test_output_layer.py`
- Implementation notes:
  - 新增 dataclass 字段必须有中文注释解释含义。
  - 审查顺序为证据链、最小语义结构、输出角色。
  - 角色只允许 `standalone`、`supporting`、`defer`。
  - 不硬编码“伟大 / 喜欢 / 好用”之类词表作为降级条件。
  - `relation_candidates` 只能作为解释线索，不能当成正式关系事实。
- Validation:
  `python -m unittest tests.test_output_layer`
  至少覆盖：
  - `WhisperDesktop，伟大。` 不因短小被降级
  - `伟大。` 在缺少主体、对象和上下文时暂不输出
  - 无 `state_evidence` 或无法回到 chunk/document 的 state 暂不输出
- Stop condition:
  短评价、短阻塞、短决策、短计划使用同一套输出角色审查。

## Step 4

- Goal:
  实现 `ReadingCluster` 与阅读簇归组。
- Files likely touched:
  `layers/output_layer.py`
  `tests/test_output_layer.py`
- Implementation notes:
  - 阅读簇是 output-only 临时上下文集合，不落库。
  - 不同文档默认不进入同一阅读簇。
  - 同文档内通过相邻 chunk、同章节、共享对象、共享事件线索或强锚点连接。
  - 一条状态的主体可以作为另一条状态的对象形成“主体—对象连接”，但不是主体合并。
  - 多主体簇保留全部 subject identities，不把整个簇归属给第一个主体。
- Validation:
  `python -m unittest tests.test_output_layer`
  至少覆盖：
  - Aurora Board 形成主状态 + 支撑状态的阅读簇
  - River import incident 形成多主体阅读簇
  - 同文档但不同章节、无共享对象、无事件线索、无强锚点时不误合并
  - 不同文档不误合并
- Stop condition:
  输出层能形成读者可理解的阅读簇，同时不改变任何 state 的 `subject_type` / `subject_key`。

## Step 5

- Goal:
  从 `ReadingCluster` 投影回现有 `ContextBundle` / `CandidateTopicBundle` / `BundleNarrative`，保持既有 Markdown contract。
- Files likely touched:
  `layers/output_layer.py`
  `tests/test_output_layer.py`
- Validation:
  `python -m unittest tests.test_output_layer`
  至少覆盖：
  - 不渲染 `##### 进展` / `##### 问题` / `##### 下一步`
  - 不渲染 `summary：detail`
  - bundle summary 不包含 `主要涉及：` / `核心信息是：`
  - 弱标题 candidate 不以 `工具：` 形式进入正式 Markdown
  - `needs_context` 仍不进入正式 Markdown
- Stop condition:
  阅读角色和阅读簇可以复用现有输出投影，不需要新增 SQLite schema 或改 aggregator。

## Step 6

- Goal:
  增强 diagnostics，使输出角色和阅读簇归组可观察。
- Files likely touched:
  `layers/output_layer.py`
  `tests/test_output_layer.py`
- Validation:
  `python -m unittest tests.test_output_layer`
  至少覆盖：
  - 每个 state 的输出角色和中文理由可观察
  - 每个 reading cluster 的合并依据可观察
  - 暂不输出的 state 记录缺失信号
  - 多主体 reading cluster 记录全部主体身份
  - 疑似误归组风险可进入 diagnostics
- Stop condition:
  后续调参可以基于 diagnostics 判断阈值、排序、拆分和省略策略。

## Step 7

- Goal:
  仅在后续可选阶段接入 LLM 审查。默认规则模式必须可运行、可测试、可复现。
- Files likely touched:
  `layers/output_layer.py`
  `tests/test_output_layer.py`
  `docs/testing.md`，仅当验证命令或环境变量事实变化时更新。
- Proposed env:
  `OUTPUT_READING_REVIEW_MODE=rule|llm|auto`
- Validation:
  `python -m unittest tests.test_output_layer`
  至少覆盖：
  - fake LLM 成功输出时仍只做审查，不生成新事实
  - fake LLM 返回不存在的 state_id 时回退规则模式
  - fake LLM 使用输入中不存在的信息时回退规则模式
  - fake LLM 没有中文理由时回退规则模式
- Stop condition:
  LLM 只能审查输出角色或归组，不得补外部背景，不得生成新的 state fact。

## Step 8

- Goal:
  同步 retained docs 和最小验证集合。只有代码行为真实落地后，再把 `docs/architecture.md` 中的输出层事实改成 reading roles / reading clusters 已实现。
- Files likely touched:
  `docs/architecture.md`
  `docs/testing.md`
  `docs/changes.md`
  `AGENTS.md`
  `README.md`
- Validation:
  后续实现阶段优先运行：
  ```bash
  ruff check .
  python -m unittest tests.test_output_layer
  python -m unittest tests.test_aggregator
  python -m unittest tests.test_input_layer
  python -m tests.test_extraction_schema
  python main.py --help
  ```

  如实际生成输出，再运行：
  ```bash
  python main.py --skip-extraction
  python main.py --stats
  ```
- Stop condition:
  retained docs 清楚区分“当前已实现事实”和“下一阶段 active plan/spec”，且不声称已有完整 typecheck 或完整业务正确性证明。

## Acceptance Criteria

- 不再使用“低信息评价”作为正式内部分类。
- 短句不会因为短小被降级。
- 短评价、短阻塞、短决策、短计划使用同一套输出角色审查。
- 单状态是否输出，由主体、对象、关系、证据链、上下文共同决定。
- 多主体上下文通过阅读簇归组，不改变 state 的 `subject_type` / `subject_key`。
- Aurora Board 能形成一个主状态 + 支撑状态的阅读簇。
- River import incident 能形成一个多主体阅读簇。
- 不同文档不误合并。
- 同文档但不同章节、无共享对象、无事件线索、无强锚点的状态不误合并。
- 正式 Markdown 仍不显示置信度、内部 state_id、硬分类小节、`summary：detail`。
- `needs_context` 仍只作为内部诊断，不渲染成正式章节。
- schema、prompt、aggregator 无改动。
- 所有新增 dataclass 字段和关键函数必须有中文注释解释含义。

## Long-Term Follow-Up

- 先观察无数量阈值的真实输出分布，再决定 max bundle、max item、排序和拆分策略。
- 后续再评估 profile 级 `needs_context` 持久化或诊断报告。
- 白名单补充材料需要明确目录、准入和隐私边界后再扩大使用。
- retrieval / MCP / 联网搜索留到后续版本评估，不进入当前默认补全链路。
- 规则稳定后再评估 `context_bundles` / `context_bundle_evidence` 持久化。
