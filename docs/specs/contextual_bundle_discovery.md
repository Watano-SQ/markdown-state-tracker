# Contextual Bundle Discovery Spec

## Goal

在已实现的 `ContextBundle` v1 之上，下一步优化“不规范文档”的上下文发现流程。

本阶段目标不是限制输出数量，也不是一次走完整补全链路，而是先使用当前可用的本地上下文能力，让 output/profile 层按证据和强锚点形成更可靠的 bundle。

任务完成后，应满足以下事实：

- `status.md` 只输出已经形成可靠上下文的 bundle。
- `needs_context` 是内部诊断 / 补全状态，不作为正式 `待澄清` 章节渲染进 `status.md`。
- bundle 构造支持局部归组和同文档远距离强锚点回收。
- 本阶段先使用 source evidence chunk、邻近 chunk、同文档其他 chunk。
- 白名单补充材料只在显式可用时接入；完整补全链路记录为后续版本方向。
- 暂不设置 max bundle、max item 或待补全数量阈值，先观察真实分布。

## Problem Focus

当前 v1 方向正确，但仍有两个关键不足：

- 过于依赖相邻 chunk。文档开头和结尾可能谈同一事件，同一模型、插件、issue、项目或工具也可能跨多个 section 反复出现。
- `needs_context` 若直接渲染进 `status.md`，会把内部诊断噪音暴露给最终读者。

下一阶段应优先提升上下文发现，而不是做单条美化、输出截断或正式待澄清展示。

## Reliable Output Contract

`status.md` 只渲染可靠 bundle。

可靠 bundle 至少应满足：

- 有 active state。
- 有可追溯的 `state_evidence`。
- 能回到 source chunk / document。
- 通过局部证据或强锚点之一形成上下文闭合。
- bundle 标题、内容和小节只来自已有 state/evidence/chunk 局部上下文，不硬补无法验证的背景。

不可靠 state 的命运：

- 不进入 `status.md`。
- 不作为正式 `待澄清` 章节渲染。
- 进入内部诊断数据，用于观察未归组数量、原因和后续补全方向。

## Two-Layer Grouping

bundle 归组分两层执行。

### Local Grouping

局部归组用于顺序清晰、相邻上下文明显的文档片段。

可用信号：

- 同一 document。
- 相邻或近邻 chunk。
- 相同或相近 `section_label`。
- 同一 subject。
- 同一 canonical/display 主题。

### Distant Strong-Anchor Recovery

远距离归组用于同一 document 内前后呼应的上下文。

同一 document 内，即使 chunk 不相邻，只要共享强锚点也可以合并。

强锚点包括：

- `subject_type` / `subject_key`。
- 明确项目名。
- 明确工具名或插件名。
- 明确模型名。
- issue 编号。
- canonical 主题词。
- retrieval candidate 线索。

约束：

- retrieval candidate 只能作为待确认锚点线索，不代表已确认事实。
- relation candidate 不参与正式 bundle 构造，除非未来已有 pending/confirmed relation 语义。
- 跨文档远距离合并默认不做；如未来需要，应另行定义更强确认规则。

## Context Completion Scope

本阶段不要求走完整补全链路。

先使用当前已经可用或实现成本很低的本地路径：

1. source evidence chunk。
2. 邻近 chunk。
3. 同文档其他 chunk。

可选扩展：

- 白名单目录 / 补充材料只有在显式配置、显式传入或已有明确可用来源时才接入。

后续版本再评估完整补全链路：

- 更正式的白名单目录 / 补充材料策略。
- retrieval candidate 辅助补全。
- MCP 或联网搜索。

## Diagnostics Before Thresholds

本阶段暂不设置输出数量阈值。

先生成诊断信息，观察真实分布：

- bundle 数量。
- 每个 bundle 的 state 数。
- 每个 bundle 的合并依据。
- 未进入 bundle 的 state 数量。
- 未进入 bundle 的原因。
- 是否出现过大 bundle。
- 是否出现疑似误合并。

诊断信息可以进入日志、返回值或开发用调试对象，但不应作为正式 `status.md` 内容。

只有观察到真实分布后，后续阶段才评估：

- max bundle。
- max item。
- bundle 拆分规则。
- needs_context 持久化或输出策略。

## Architecture Boundary

本阶段继续保持只读 output/profile 层投影。

- 不新增 SQLite schema。
- 不改 extractor contract。
- 不让 aggregator 负责最终报告结构。
- 不把 relation/retrieval candidate 当成确认事实。
- 不把无法验证的背景硬补进输出。

长期边界：

- extractor 仍只产生 chunk 级观察。
- aggregator 仍负责 state identity 和 evidence 汇聚。
- profile / output layer 负责上下文阅读视图。
- needs_context 若未来需要持久化，应先定义单独候选 / 诊断命运，不反向污染 `states`。

## Non-goals

- 不在本阶段设置输出数量阈值。
- 不在 `status.md` 渲染 `needs_context` / `待澄清` 章节。
- 不新增 schema。
- 不要求一次实现白名单、retrieval、MCP、联网搜索的完整补全链路。
- 不让 LLM 生成无法证实的 bundle 背景。
- 不重新定义 extraction JSON。
- 不直接消费未持久化 relation candidate。

## In Scope

- 冻结可靠 bundle 输出契约。
- 冻结局部归组与远距离强锚点回收模型。
- 冻结当前可用本地上下文的使用范围。
- 冻结“先诊断、后阈值”的阶段策略。
- 冻结 `needs_context` 不进入正式 `status.md` 的边界。
- 记录完整补全链路的后续版本方向。

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
- 优先使用当前可用的本地上下文，再讨论完整补全链路和外部补全
- 输出层不得反向改写 state identity、subject attribution 或 extraction contract

## Acceptance Criteria

- spec 明确 `status.md` 只输出可靠 bundle。
- spec 明确 `needs_context` 是内部诊断 / 补全流程，不是正式输出章节。
- spec 明确 bundle 归组包含局部归组和远距离强锚点回收。
- spec 明确本阶段先使用当前可用路径：source evidence chunk、邻近 chunk、同文档其他 chunk。
- spec 明确白名单补充材料和 retrieval / MCP / 联网搜索作为后续版本方向。
- spec 明确本阶段不设置数量阈值，而是先记录诊断分布。
- spec 明确不新增 schema、不改 extractor contract、不让 aggregator 负责报告结构。

## Reference Files

- AGENTS.md
- docs/architecture.md
- docs/testing.md
- docs/changes.md
- docs/archive/specs/contextual_output_bundles.md
- docs/archive/plans/contextual_output_bundles.md
- layers/output_layer.py
- layers/middle_layer.py
- layers/aggregator.py
- output/status.md
