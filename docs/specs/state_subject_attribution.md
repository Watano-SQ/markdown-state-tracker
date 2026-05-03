# State Subject Attribution Spec

## Goal

在不扩大当前仓库边界的前提下，把第二阶段从“作者状态规范化”升级为“来源感知 + 主体感知的候选准入与主体归属判定”。

这一阶段建立在第一阶段“输入边界与来源类型”之上，不再重新定义文件级扫描边界或块类型识别；它要回答的是：

- 文档作者与状态主体之间是什么关系，而不再默认两者绑定
- 当前文档更像个人文档、团队文档还是混合文档
- 每条候选状态属于 `person / team / project / organization` 中的哪一种主体
- 聚合前哪些候选可以直接准入、条件准入或默认拒绝
- prompt 与 aggregator 在主体判定中的职责边界如何划分

任务完成后，应满足以下事实：

- 仓库后续既能处理个人日志，也能为团队/项目文档保留可扩展的主体归属空间
- “作者 / 用户 / 我”的表面统一不再被当作最终目标，而只是主体归属判定后的一个显示层问题
- 第二阶段与后续“统一状态底座”“场景化输出 profile”阶段的边界被明确拆开

## Stage-2 Problem Focus

本阶段只聚焦以下四类问题：

### 1. document author 不是稳定的 state subject

当前样本让人容易把“文档作者”与“状态主体”混为一谈，但后续仓库要支持：

- 个人日志
- 团队周报
- 项目进展
- 组织公告或团队内部状态文档

因此，document author 只能作为解释线索，不能再被绑定为默认状态主体。

### 2. 同一文档可能包含多种主体

即使在单篇 Markdown 内，也可能同时出现：

- 作者本人状态
- 团队状态
- 项目状态
- 外部组织或第三方对象

第二阶段必须明确：主体归属是“按候选判定”，而不是“按整篇文档一刀切”。

### 3. 候选准入需要同时依赖来源与主体

第一阶段只解决“这段文本来自哪里”。
第二阶段要进一步解决“这段文本在说谁”，以及“它是否值得进入状态层”。

也就是说，候选准入至少要同时看：

- 来源类型是否可靠
- 主体是否明确
- 主体是否属于当前状态底座支持的对象
- 语义是否真的是该主体的状态，而不是教程建议、背景资料或外部事实

### 4. prompt 与 aggregator 的责任不能混淆

如果只让 prompt 负责主体归属，旧数据和漏网候选仍会污染状态层。
如果只让 aggregator 负责全部判断，抽取噪声会继续堆积。

因此必须冻结一条清晰分工：

- prompt 负责减少脏候选、提供主体线索
- aggregator 负责最终准入裁决、主体归属与兜底规范化

## Document Interpretation Model

第二阶段建议引入文档级解释模式，但它只是 prior，不是硬编码结论。

### 1. `document_mode`

最小建议值：

- `personal`
- `team`
- `hybrid`

含义：

- `personal`: 文档主要记录个人状态，但不排除出现团队/项目片段
- `team`: 文档主要记录团队、项目或组织状态，但不排除出现个人贡献片段
- `hybrid`: 文档内部长期混合多种主体，不能依赖单一模式推断

约束：

- `document_mode` 只能提供判定倾向，不能替代候选级主体归属
- 如果无法稳定识别，允许保守落为 `hybrid` 或 `需要人类确认`

## Subject Model

第二阶段建议至少冻结以下主体字段语义；具体字段名可在实现时微调。

### 1. `subject_type`

最小支持范围：

- `person`
- `team`
- `project`
- `organization`
- `unknown`

### 2. `subject_key`

`subject_key` 表示可稳定复用的主体标识，不等于展示用名称。

约束：

- 它应在同一仓库内尽量稳定
- 不应直接依赖自然语言 summary
- 不应默认退化为 document author

### 3. 可选字段

以下字段可作为设计冻结项，是否在第二阶段立刻实现可后置：

- `subject_label`
- `subject_confidence`
- `attribution_basis`

这些字段的作用是帮助后续调试和场景化输出 profile，但不是第二阶段最小实现的唯一前提。

## Subject Attribution Rules

第二阶段实现应至少覆盖以下主体归属规则。

### 1. 个人主体

当正文明确描述某个个人的计划、问题、能力、偏好或事件，并且来源类型可靠时，可以归属到 `person`。

注意：

- 这个人可能是文档作者
- 也可能是文档中被明确讨论的其他成员
- 不能因为出现第一人称就机械绑定作者；仍应结合 `document_mode`、来源类型和上下文

### 2. 团队主体

当正文描述“我们 / 本组 / 团队 / 小组”这类集合主体的当前状态时，可以归属到 `team`。

例子包括：

- 团队计划
- 团队进展
- 团队当前问题
- 团队共识或明确决策

### 3. 项目主体

当正文语义中心是某个项目，而不是个人或团队时，可以归属到 `project`。

例子包括：

- 项目当前阶段
- 项目阻塞点
- 项目待办
- 项目配置/部署状态

### 4. 组织主体

当正文可靠地描述某个组织或机构本身的状态，并且该组织是当前文档希望追踪的对象时，可以归属到 `organization`。

但组织事实不能默认准入；必须区分：

- “这是被追踪主体本身的状态”
- “这只是抓到的一段组织资料”

如果第二点占主导，应默认拒绝。

### 5. 未知主体

如果主体无法稳定解析，允许保守落为 `unknown`。
`unknown` 候选默认不直接升格为正式状态，除非后续规则允许条件准入。

## Candidate Eligibility Rules

第二阶段实现应至少把候选分为三类。

### 1. 直接准入

满足以下条件的候选可直接进入状态层：

- 来源类型可靠，通常来自第一阶段定义的作者正文或其他被允许的正文块
- 主体可以稳定解析到 `person / team / project / organization`
- 候选语义中心确实是该主体的状态，而不是外部资料的转述

### 2. 条件准入

以下候选不能直接照搬，但在满足额外条件时可以进入状态层：

- 主体需结合文档模式、章节或上下文才能补足
- 候选来自引用/资料，但正文明确将其转化为当前主体的计划、判断或实践
- 候选描述的是配置、代码、参数或工具使用，但已被正文赋予主体状态意义

### 3. 默认拒绝

以下候选默认不应直接进入状态层：

- 面向“用户/您”的通用建议
- 通用概念解释、产品说明、教程摘要
- 引用回答中的知识点结论
- 主体不明且无稳定上下文可补足的候选
- 仅描述第三方网页、组织公告、导航、角色信息的事实

## Prompt And Aggregator Boundary

第二阶段需要明确以下职责边界。

### 1. Prompt / Extractor 的责任

prompt 至少应显式要求：

- 输出候选时尽量判断当前主体是谁
- 不要把教程建议、引用知识点、资料性文字直接写成状态候选
- 尽量区分 `personal / team / hybrid` 语境下的主体指向

extractor 的目标是减少脏候选，并为后续聚合提供主体线索，但它不是最终裁判。

### 2. Aggregator 的责任

aggregator 至少需要承担：

- 最终主体归属判定
- 候选准入裁决
- 对 `unknown` 或低可靠主体做保守拒绝
- 对可安全规范化的主体做统一 key 化和类型收敛

也就是说，aggregator 必须把 extractor 结果视为 proposal，而不是事实真相。

## Minimal Contract Recommendation

第二阶段建议冻结以下最小 contract。

### 推荐现在就准备的字段语义

- `document_mode`
- `subject_type`
- `subject_key`

这些字段可以先存在于 extraction JSON 或聚合中间结构中，不要求第二阶段立刻修改 `states` 的长期 SQLite schema。

### 先冻结设计、不急于实现的内容

- 跨文档主体注册表
- 主体 alias 管理
- 主体层级关系（person 属于 team，team 负责 project 等）
- 正式的 subject registry 持久化

## Non-goals

本阶段明确不解决以下问题：

- 不重新定义第一阶段的文件级边界与来源类型
- 不解决状态层与展示层的正式分离
- 不解决 canonical summary、display summary 或场景化输出 profile
- 不解决显著性排序、输出配额与最终输出编排
- 不设计完整的主体关系图谱或 registry 系统
- 不默认扩展 SQLite 为重型多实体平台

## In Scope

- 冻结 `document_mode` 的最小解释模型
- 冻结 `subject_type` / `subject_key` 的最小语义
- 定义主体归属规则与候选准入规则
- 明确 prompt 与 aggregator 的职责边界
- 记录哪些字段建议现在准备，哪些只先冻结设计
- 记录仍需人类确认的产品边界

## Out Of Scope

- 当前 turn 内直接修改 prompt、聚合逻辑或 schema
- 设计完整的主体 registry、关系图谱或场景化输出 profile
- 把 document author 与主体解绑后的全部迁移细节一次做完
- 声称上述主体归属规则已经在仓库中实现

## Constraints

- keep current repository structure unless intentionally changed
- do not assume behavior that is not implemented
- mark uncertain facts as `需要人类确认`
- 第二阶段必须建立在第一阶段来源类型结果之上，不反向改写第一阶段文档边界
- 优先采用轻量、可解释的主体判定与候选准入规则，而不是一次引入完整实体系统
- `input_docs/` 视为潜在敏感输入，不在 retained docs 中复制长篇原文
- 若某些组织/项目事实是否应直接进入状态层无法从当前产品目标稳定推出，标为 `需要人类确认`

## Acceptance Criteria

- 存在一份独立 spec，且其范围只覆盖第二阶段“主体归属判定与候选准入”
- spec 明确区分 document author 与 state subject，不再默认绑定两者
- spec 至少定义 `document_mode: personal / team / hybrid`
- spec 至少定义 `subject_type` 与 `subject_key` 的最小语义
- spec 至少定义三类候选准入规则：直接准入、条件准入、默认拒绝
- spec 明确区分 prompt 责任与 aggregator 责任
- spec 明确指出哪些字段建议现在准备，哪些只先冻结设计不实现

## Reference Files

- AGENTS.md
- docs/specs/state_output_quality.md
- docs/plans/state_output_quality.md
- .github/EXTRACTION_JSON_SCHEMA.md
- input_docs/李申亮.md
- input_docs/邹少乾.md
- input_docs/汪翰元.md
- output/status.md
- layers/extractors/prompts.py
- layers/aggregator.py
- layers/middle_layer.py
