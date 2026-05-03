# State Foundation Spec

## Goal

在不扩大当前仓库边界的前提下，把第三阶段定义为“统一状态底座”建设阶段，而不是直接跳到展示层优化。

这一阶段建立在前两阶段之上；它要回答的是：

- 状态层与展示层是否需要正式分离
- 现在的 `summary` 是否需要拆成 `canonical_summary` 和 `display_summary`，或等价设计
- 状态的唯一性应由哪些维度决定，而不再只靠 `summary` 原文
- 统一状态底座应如何为后续场景化输出 profile 提供稳定输入

任务完成后，应满足以下事实：

- 状态底座不再隐含“作者中心 + 固定单输出”的前提
- 状态的语义身份、去重归并和展示表达被明确拆分
- 后续不同场景的输出 profile 可以消费同一套底座，而不是各写各的 summary

## Stage-3 Problem Focus

本阶段只聚焦以下四类问题：

### 1. `summary` 职责过载

当前 `summary` 同时承担：

- 语义表达
- 去重主键
- 展示文案

这会导致：

- 轻微改写就生成新 state
- 同一主题难以跨文档、跨主体合并
- 为展示而写的句子反过来影响状态唯一性

### 2. 状态身份没有显式底座

当前状态层没有稳定表达：

- 这个状态属于哪个主体
- 这条状态的 canonical identity 是什么
- 这条状态在不同输出 profile 里是否允许用不同显示文案

没有这层底座，就很难支持后续场景化输出。

### 3. 证据聚合与状态归并缺少稳定锚点

即使前两阶段解决了来源与主体问题，如果状态层仍然只按 raw summary 合并：

- 证据仍会被摊散
- 近义状态仍会爆炸
- 后续显著性和 profile 级排序也没有稳定基础

### 4. 单一输出产物耦合反推状态设计

当前容易把 `status.md` 的展示需求反向写进状态层。
第三阶段需要明确：状态底座先服务语义一致性，再服务场景化输出 profile。

## Foundation Model

第三阶段默认采用“统一状态底座 + 场景化输出 profile 消费”的模型。

### 1. 状态层是语义底座，不是展示文案集合

状态记录首先是“某主体在某主题上的规范化状态单元”，而不是“最终 Markdown 中的一条 bullet”。

### 2. 状态身份至少由以下因素决定

最小推荐维度：

- `subject_type`
- `subject_key`
- 状态类别 / 子类
- canonical 语义表达

这意味着：

- 同一 canonical 语义在不同主体下不能机械合并
- 同一主体下的展示改写不应天然制造新 state

### 3. 展示层消费状态底座，而不是定义状态底座

第三阶段建议冻结一个原则：

- 状态底座负责语义身份、证据汇总、归并基础
- profile / 输出层负责场景选择、文案渲染、排序与布局

## Canonical And Display Separation

第三阶段需要正式评估并冻结“语义层 / 展示层分离”方案。

### 推荐方向

优先推荐以下二分模型，或语义等价设计：

- `canonical_summary`
- `display_summary`

### 1. `canonical_summary`

职责：

- 表达该状态最稳定、最可复用的语义核心
- 服务去重、归并和跨 profile 复用
- 不必追求最终展示语气

### 2. `display_summary`

职责：

- 面向具体输出场景的可读表达
- 可以因 audience / purpose / output profile 而有所差异
- 不应作为底层去重主键

### 3. 过渡策略

第三阶段不要求立即完成完整迁移，但需要冻结一条可执行的过渡路径：

- 方案 A：先新增 canonical 字段，保留现有 `summary` 作为过渡 display 字段
- 方案 B：不立刻新增字段，但在聚合中先引入“canonical 语义”概念，并明确后续迁移目标

如果当前阶段不宜马上改 schema，可以先冻结设计，不立即实现。

## State Identity And Merge Rules

第三阶段应至少冻结以下规则。

### 1. 主体优先于展示文案

不同主体下，即使 `display_summary` 看起来相似，也不应先于主体维度合并。

### 2. canonical 语义优先于 raw wording

同一主体下，如果多条候选只是 wording 变化，但 canonical 语义一致，应优先合并。

### 3. 证据向 canonical state 汇聚

`state_evidence` 的长期作用应是支撑 canonical state，而不是支撑展示文案碎片。

### 4. 主题级扩展可后置

完整主题聚类、层级状态树、关系网络都可以后置，但 canonical identity 的设计不能再缺席。

## Schema Boundary Evaluation

第三阶段需要明确“现在做什么”和“先冻结什么”。

### 建议现在就冻结设计的内容

- `canonical_summary` / `display_summary` 的职责分离
- 状态身份至少依赖 `subject_key`
- 统一状态底座先于场景化输出 profile

### 建议先冻结但不实现的内容

- 正式 subject registry
- 复杂状态层级结构
- 多表重构或重型迁移
- 关系图谱与跨主体推理

### 可能需要最小实现的内容

实现时可根据成本评估：

- 在状态层引入 canonical 概念
- 为后续 profile 保留 display 层表达
- 更新聚合合并逻辑，使其不再只依赖 raw summary

## Prompt And Aggregator Boundary

第三阶段继续沿用前两阶段的原则，并进一步明确：

### Prompt / Extractor

- 可以输出更干净的原始候选
- 可以尝试生成更稳定的候选摘要
- 但不应承担最终 canonical identity 建模责任

### Aggregator / State Layer

- 必须承担 canonical state 构造
- 必须承担状态归并与证据汇总
- 必须为 profile / 展示层提供稳定可消费的状态单元

## Non-goals

本阶段明确不解决以下问题：

- 不重新定义第一阶段的来源类型边界
- 不重新定义第二阶段的主体归属判定与准入规则
- 不实现完整场景化输出 profile 渲染
- 不引入重型 registry、graph、embedding 或外部知识库
- 不设计平台级长期记忆系统

## In Scope

- 冻结“统一状态底座”的目标模型
- 评估并冻结 canonical / display 分离方案
- 冻结状态身份的最小维度
- 冻结聚合层在 canonical state 构造中的职责
- 明确哪些内容可现在做、哪些先冻结不实现

## Out Of Scope

- 当前 turn 内直接修改 schema、聚合逻辑或输出逻辑
- 完成所有 canonical / display 字段迁移
- 直接实现 profile 选择或场景化输出渲染
- 声称统一状态底座已经在仓库中实现

## Constraints

- keep current repository structure unless intentionally changed
- do not assume behavior that is not implemented
- mark uncertain facts as `需要人类确认`
- 第三阶段必须建立在第一、二阶段输出之上，不反向改写前序阶段文档边界
- 优先冻结职责与字段语义，再决定最小实现步幅
- `input_docs/` 视为潜在敏感输入，不在 retained docs 中复制长篇原文
- 若 `canonical_summary` / `display_summary` 是否应在本阶段立刻落 schema 无法稳定判断，标为 `需要人类确认`

## Acceptance Criteria

- 存在一份独立 spec，且其范围只覆盖第三阶段“统一状态底座”
- spec 明确说明当前 `summary` 的职责过载问题
- spec 明确冻结“状态层先于展示层”的原则
- spec 明确评估 `canonical_summary` / `display_summary` 或等价设计
- spec 明确状态身份至少依赖 `subject_type` / `subject_key` 与 canonical 语义
- spec 明确指出统一状态底座是后续场景化输出 profile 的输入层，而不是输出层副产物
- spec 明确指出哪些内容建议现在做，哪些只冻结设计不实现

## Reference Files

- AGENTS.md
- docs/specs/state_output_quality.md
- docs/specs/state_subject_attribution.md
- docs/plans/state_output_quality.md
- docs/plans/state_subject_attribution.md
- .github/EXTRACTION_JSON_SCHEMA.md
- layers/aggregator.py
- layers/middle_layer.py
- output/status.md
