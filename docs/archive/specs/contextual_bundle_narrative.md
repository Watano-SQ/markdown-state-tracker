# Contextual Bundle Narrative Spec

## Goal

把 `output/status.md` 从“主体下面的 state 条目清单”升级为“主体下的主题报告”。

本阶段在已实现的 `ContextBundle` / `needs_context` 内部诊断 / 强锚点发现之上继续推进，只在 output/profile 层新增只读 narrative 投影，不新增 SQLite schema，不改变 extraction contract，也不让 aggregator 负责最终报告结构。

任务完成后，应满足以下事实：

- 一级输出分组是主体，例如人、项目或文档推断主体。
- 主体下按主题 bundle 展开，而不是直接列出 state。
- 每个主题 bundle 有 `topic_title` 和 `bundle_summary`。
- 小 state 只作为证据材料，不再以 `summary + detail` 双层结构直接渲染。
- 正式 Markdown 不显示 `confidence` / `置信度`。
- `needs_context` 仍只进入内部诊断，不作为正式 `待澄清` 章节。
- LLM 可用于主题内分类和叙事整理，但必须有规则回退。

## Problem Focus

当前 `ContextBundle` 解决了“哪些 state 可以进入同一上下文附近”，但还没有解决“这些 state 共同构成什么主题，以及应该如何被读成报告”。

主要问题：

- 有主体，但主题层不足；一个主体 bundle 里仍可能混合多个项目、工具、问题或行动链。
- 每个小 state 仍渲染自己的 summary/detail，导致概括与详情重复或倒挂。
- 置信度在正式输出中没有清晰读者价值。
- 当前栏目分类主要由固定 subtype 映射和问题关键词决定，容易误分。
- 低信息条目暂不作为本阶段重点过滤，因为完整输出仍有观察价值。

## Output Contract

目标 Markdown 结构：

```markdown
## 上下文报告

### 主体名称

#### 主题标题

主题摘要段落。

##### 当前目标
- 事实句

##### 进展
- 事实句

##### 问题
- 事实句

##### 下一步
- 事实句

##### 相关线索
- 事实句
```

正式输出要求：

- 空栏目不渲染。
- 每条事实句必须能追溯到一个或多个 source state/evidence。
- source ids、confidence、omitted state 只进入内部结构或诊断，不显示给普通读者。
- bundle summary 只能来自已有 state/evidence/chunk 局部上下文，不硬补无法验证的背景。

## Data Model Boundary

新增输出层只读结构，不入库：

- `CandidateTopicBundle`
  - subject type/key/label
  - source document
  - topic key / title hint / merge basis
  - evidence items
  - source state ids
- `BundleNarrative`
  - subject type/key/label
  - topic title
  - bundle summary
  - narrative sections
  - absorbed state ids
  - omitted state ids with reasons
  - diagnostics

`states.summary` / `states.detail` / `states.confidence` 继续作为兼容字段存在，但不再直接决定正式 Markdown 的条目形态。

## Topic Bundle Formation

候选主题 bundle 由代码负责边界，LLM 不直接从全库自由生成主题。

顺序：

1. 从现有 `ContextBundleSelection` 开始。
2. 保留主体作为一级分组。
3. 在主体内按强锚点、section、chunk 邻近关系、canonical/display 主题词拆分主题候选。
4. 同主体同文档内可合并共享强锚点的远距离内容。
5. 默认不做跨主体合并。
6. 默认不做跨文档主题合并；未来如需要，应另立 spec。

## LLM Narrative Classifier

LLM 是 output/profile 层的叙事整理器，不是新的 extractor 或 aggregator。

输入单位是单个 `CandidateTopicBundle`，包含：

- subject
- source document
- merge basis
- state id
- subtype
- summary/detail
- section label
- short evidence excerpt

LLM 输出必须是严格 JSON：

```json
{
  "topic_title": "string",
  "bundle_summary": "string",
  "sections": [
    {
      "kind": "current_goal | progress | problem | next_step | related_context",
      "text": "string",
      "source_state_ids": [1, 2]
    }
  ],
  "absorbed_state_ids": [1, 2],
  "omitted_state_ids": [
    {"state_id": 3, "reason": "too_vague | duplicate | unsupported"}
  ]
}
```

约束：

- 不得补外部背景。
- 不得引用不存在的 state id。
- 不得输出没有 `source_state_ids` 的事实句。
- 不得把 omitted state 渲染进正式 Markdown。
- JSON 解析失败、schema 不合法、source id 不合法或请求失败时，回退到规则 narrative。

运行模式：

- `OUTPUT_NARRATIVE_MODE=rule|llm|auto`
- 默认 `rule`，保证无 API 验证仍可运行。
- `llm` / `auto` 复用现有 OpenAI-compatible 配置。

## Non-goals

- 不新增 SQLite schema。
- 不重写 extraction JSON schema。
- 不让 aggregator 负责最终报告结构。
- 不做跨文档主题合并。
- 不在本阶段过滤所有低信息条目。
- 不重新设计置信度语义。
- 不引入 retrieval / MCP / 联网补全。
- 不把 LLM 输出持久化为状态事实。

## Acceptance Criteria

- `status.md` 中不再出现 `置信度:`。
- `status.md` 中不再把每个 state 渲染为标题加 detail 的双层结构。
- 输出存在主体层和主题层。
- 每个主题 bundle 有 summary。
- 至少一个主体下可以拆成多个主题 bundle。
- LLM 分类可通过 fake client 测试，不依赖真实 API。
- LLM 失败时仍能生成规则回退输出。
- `needs_context` 仍不进入正式 Markdown。
- `docs/changes.md` 记录置信度语义、低信息过滤、跨文档主题合并、LLM 摘要质量评估为后续债务。

## Reference Files

- AGENTS.md
- docs/architecture.md
- docs/testing.md
- docs/changes.md
- docs/archive/specs/contextual_bundle_discovery.md
- docs/archive/plans/contextual_bundle_discovery.md
- layers/output_layer.py
- test_output_layer.py
- output/status.md
