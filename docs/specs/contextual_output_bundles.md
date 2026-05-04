# Contextual Output Bundles Spec

## Goal

将 `output/status.md` 的主阅读单位从单个 `state` 条目升级为证据驱动的 `ContextBundle`。

当前问题不是单条状态都错误，而是很多状态离开上下文后失去含义。例如“关注 issue #1260”“找到几个模型待比较”“仍找不到原因”这类碎片，应该作为某个项目、问题、排查过程、模型比较任务或插件配置尝试中的线索出现，而不是作为独立状态输出。

任务完成后，应满足以下事实：

- `status.md` 优先展示上下文整体，而不是长条目清单。
- 输出层通过 `state_evidence` 回到 source chunk / document 构造 bundle。
- 碎片状态会先尝试归入可靠上下文；无法归入时降级为待澄清或暂不展示。
- 系统不会为了让单条状态看起来完整而硬补不确定背景。

## ContextBundle Model

`ContextBundle` 是 v1 的输出层内存结构，不是持久化表。

最小字段语义：

- `title`：上下文标题，优先来自文档标题、section、主体线索或多条状态的共享语义。
- `source_document`：主要证据来源文档。
- `subject_type` / `subject_key`：可用时保留主体线索。
- `state_ids`：bundle 消费的 active state。
- `evidence_chunk_ids`：支撑 bundle 的 source chunks。
- `sections`：渲染小节，允许为空或缺省。
- `needs_context_items`：证据不足、无法可靠归组的状态。

v1 不要求为这些字段新增 schema。后续如需要持久化，应先验证只读输出规则稳定。

## Bundle Construction

bundle 构造优先使用现有证据链：

1. 从 active `states` 出发。
2. 通过 `state_evidence` 找到相关 `chunks` 和 `documents`。
3. 按证据接近性归组，而不是按单条 state 文案孤立输出。

v1 推荐的归组信号：

- 同一 document。
- chunk index 相邻或距离较近。
- 相同或相近的 `section_label`。
- 共享 `subject_type` / `subject_key`。
- 共享 `canonical_summary` / `display_summary` 中的稳定主题词。
- 相近的 `last_updated`。

这些信号是保守启发式，不代表完整语义聚类。跨文档合并必须有明确共享主体或共享 canonical 线索；否则默认不合并。

## Rendering Contract

`status.md` 中的主输出应按 bundle 渲染。

推荐小节：

- `当前目标`
- `进展`
- `问题`
- `下一步`
- `相关线索`

约束：

- 小节可以缺省；没有证据支撑的小节不渲染。
- 不为了填满结构而生成伪完整背景。
- `pending_task` 可优先进入 `下一步`。
- `recent_event`、`ongoing_project`、`active_interest` 可根据语义进入 `进展` 或 `相关线索`。
- 明确阻塞、异常、失败、找不到原因、issue 未回复等内容可进入 `问题`。
- 输出应保留来源感，但不复制 `input_docs/` 中的大段原文。

## Downgrade Rules

上下文不足的状态不应直接混入主清单。

v1 降级方式：

- 如果 state 没有 `state_evidence`，进入待澄清或暂不展示。
- 如果 state 只有单条孤立 evidence，且无法从同文档相邻 chunk 或共享主体获得上下文，进入待澄清或暂不展示。
- 如果 state 的主体为 unknown 或缺少必要主体线索，保持保守输出。
- 降级状态可以计数或列在 `待澄清` 区域，但不能伪装成已完成的上下文报告。

## Candidate Boundaries

`retrieval_candidates` 可以作为“需要补充确认”的线索，但不得展示成已确认事实。

`relation_candidates` v1 不参与正式 bundle 构造。它们仍是 extraction JSON 中的局部观察，当前没有 pending relation 持久化层，也不能直接被当成已确认上下文关系。

## Long-Term Roadmap

- v1：在 output layer 只读构造 `ContextBundle`，验证输出单位是否正确。
- v2：引入 profile 级完整性提示和更明确的 `needs_context` 输出策略。
- v3：在 v1 规则稳定后，评估是否新增 `context_bundles` / `context_bundle_evidence` 等持久化结构。
- v4：在隐私、成本、可重复测试都可接受时，再评估 LLM 辅助 bundle 标题和摘要生成。

长期边界：

- 上下文聚合不下沉到 extractor。
- extractor 仍只产生 chunk 级局部观察。
- aggregator 仍负责 state identity 和 evidence 汇聚。
- profile / output layer 负责把状态底座投影成面向阅读的上下文视图。

## Non-goals

- 不在 v1 新增 SQLite schema。
- 不改 LLM prompt 或 extraction JSON contract。
- 不引入联网搜索、embedding、外部知识库或 MCP 补全。
- 不把 relation candidate 直接写入正式关系或正式上下文。
- 不把所有碎片状态都强行补成完整段落。
- 不一次性实现所有场景化 profile。

## In Scope

- 定义 `ContextBundle` 的 v1 输出语义。
- 定义基于 `state_evidence` 的只读归组策略。
- 定义 bundle Markdown 渲染契约。
- 定义上下文不足状态的降级规则。
- 记录长期规划和后续可能的持久化方向。

## Out Of Scope

- 当前文档任务内直接改代码。
- 当前文档任务内运行 `python main.py --init`。
- 当前文档任务内更新 `docs/architecture.md` 为已实现事实。
- 当前文档任务内新增测试命令正典。

## Constraints

- keep current repository structure unless intentionally changed
- do not assume behavior that is not implemented
- mark uncertain facts as `需要人类确认`
- `input_docs/` 视为潜在敏感输入，不在 retained docs 中复制长篇原文
- 先验证只读输出投影，再评估持久化 bundle 层
- 输出层不得反向改写 state identity、subject attribution 或 extraction contract

## Acceptance Criteria

- spec 明确 `status.md` 的主输出单位应从单个 state item 转为 `ContextBundle`。
- spec 明确 `ContextBundle` v1 是输出层内存结构，不是持久化表。
- spec 明确 bundle 构造优先沿 `state_evidence -> chunks -> documents` 回查证据。
- spec 明确无法归入可靠上下文的状态应降级为待澄清或暂不展示。
- spec 明确不允许为了完整感硬补不确定背景。
- spec 明确 retrieval/relation candidate 的 v1 边界。
- spec 记录 v1 到 v4 的长期规划。

## Reference Files

- AGENTS.md
- docs/architecture.md
- docs/testing.md
- docs/changes.md
- docs/specs/state_output_profiles.md
- docs/plans/state_output_profiles.md
- docs/specs/relation_retrieval_candidates.md
- layers/output_layer.py
- layers/middle_layer.py
- layers/aggregator.py
- output/status.md
