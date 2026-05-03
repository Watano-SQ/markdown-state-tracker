# State Output Profiles Spec

## Goal

在不扩大当前仓库边界的前提下，把第四阶段定义为“统一状态底座 + 场景化输出 profile”阶段，而不是继续默认只服务一个作者中心 `status.md`，也不是要求系统同时产出所有可能视图。

这一阶段建立在前三阶段之上；它要回答的是：

- 如何让同一套统一状态底座适配不同使用情景，而不是同时满足所有情景
- 什么是 `output_profile`，它应包含哪些最小策略维度
- 当前 `output/status.md` 应如何被重新定位为默认 profile 的兼容产物
- 哪些选择属于 profile 层，哪些仍应留在状态底座层

任务完成后，应满足以下事实：

- 项目通过“可切换的输出 profile”支持不同情景，而不是并行维护个人 / 团队 / 项目多套产物
- `output/status.md` 仍可保留，但被重新定义为默认 profile 的当前落地产物
- profile 的增加不会反向迫使状态层为每个场景分别建模

## Stage-4 Problem Focus

本阶段只聚焦以下四类问题：

### 1. 多视图并行产出不可持续

如果把个人、团队、项目等情景都直接实现成并行输出：

- 产品复杂度会快速膨胀
- 输出契约会变成“每种主体类型都要有一份成品”
- 很多关系策略会被过早硬编码

第四阶段要避免的是这种“每个场景都单独满足一次”的路线。

### 2. 同一状态在不同情景下确实需要不同取舍

即使底座稳定，同一个 canonical state 在不同情景下仍可能出现差异：

- 是否纳入最终输出
- 排在什么优先级
- 以什么语气或粒度表达

因此需要一个比“单一 status.md”更灵活、但又比“多视图并行系统”更轻的中间层。

### 3. 场景层应该是策略契约，而不是第二套状态模型

`output_profile` 的职责应是表达：

- 当前输出服务什么目的
- 当前输出聚焦哪些主体
- 当前输出采用什么显著性与细节策略

而不是重新定义状态身份、主体归属或证据归并。

### 4. 场景化输出仍受完成度约束

场景化输出不能绕过完成度问题。
如果相关文档仍有未抽取 chunk，profile 输出也不能假装已经完整稳定。

## Profile Model

第四阶段建议冻结 `output_profile` 这一最小概念。
它可以叫 `output_profile`、`scenario_profile` 或语义等价名称，关键是它表达“当前输出策略”，而不是“新的状态表”。

### 1. `output_profile` 的最小职责

一个 profile 至少应定义：

- 当前输出的 audience / purpose
- 当前输出的主体聚焦范围
- 当前输出的显著性策略
- 当前输出的细节密度
- 当前输出是否纳入关联主体

### 2. 推荐的最小 profile 维度

字段名可以后续微调，但建议至少冻结以下语义：

- `focus_subject_scope`
- `audience_or_purpose`
- `salience_policy`
- `detail_level`
- `include_related_subjects`

### 3. 约束

- profile 不是新的状态存储层
- profile 不等于 `subject_type`
- profile 不要求与个人 / 团队 / 项目一一绑定
- 单次运行默认只选择一个 profile 生成主输出，而不是一次性生成所有 profile 文件

## Scenario Families

第四阶段可以冻结“情景族”，但不要求同时实现全部实例。

### 1. 个人复盘型

关注某个个人主体及其直接相关上下文，适合自我回顾或个人状态整理。

### 2. 团队同步型

关注团队当前进展、风险、决策和少量必要的个人/项目支撑信息。

### 3. 项目推进型

关注项目阶段、阻塞、待办和必要的负责主体背景。

这些只是 profile family 的例子，不是第四阶段必须并行产出的三套固定视图。

## Output Contract

第四阶段建议冻结以下过渡思路。

### 1. 当前 `output/status.md` 作为默认 profile 产物

在 profile 机制正式实现前，`output/status.md` 可以继续存在，但应被视为：

- 默认 profile 的当前渲染结果
- 或兼容旧流程的单文件产物

而不是唯一正式目标。

### 2. 单 profile 先于多文件矩阵

第四阶段默认采用：

- 一次运行选择一个 profile
- 一个 profile 产出一个主 Markdown

而不是：

- 一次运行自动生成所有主体类型的所有输出文件

### 3. profile 选择先冻结设计，不抢跑实现

后续可选方式包括：

- CLI 参数选择
- 配置文件选择
- 默认 profile 自动运行

但第四阶段当前只冻结契约，不要求立刻做完整选择机制。

## Recommended Implementation Strategy

第四阶段建议采用“单 profile 选择机制 + profile-aware 输出策略”，但要分阶段落地，避免在统一状态底座尚未完成时做表面筛选。

### 1. 兼容壳层先行

先引入最小 `OutputProfile` 概念与 profile registry，但只要求 `default` profile 可用。

这一阶段的要求：

- `generate_output(profile_name="default")` 保持当前 `output/status.md` 的兼容输出。
- `default` profile 包装现有 `OUTPUT_CONFIG`、分组、排序和 Markdown 骨架。
- 不引入多文件矩阵。
- 不要求立刻实现个人、团队、项目 profile 的真实筛选。

这样可以先把输出层从硬编码入口迁移到 profile-aware 结构，而不改变用户可见结果。

### 2. 单 profile 选择入口

在兼容壳层稳定后，再加入一个明确的 profile 选择入口。

可选入口包括：

- CLI 参数，例如 `--profile default`
- 轻量配置常量

约束：

- 单次运行只选择一个 profile。
- 未知 profile 应明确报错，而不是回退到任意默认行为。
- 默认值仍为 `default`。
- `output/status.md` 仍是默认兼容产物；是否允许 profile 改变输出路径，后续需要人类确认。

### 3. 真实 profile 策略后置到状态底座成熟之后

`personal_review`、`team_sync`、`project_push` 等 profile 可以先作为设计目标存在，但不宜在缺少主体归属和 canonical/display 分离时抢跑实现。

真正的 profile 策略应建立在以下能力之上：

- `subject_type`
- `subject_key`
- `canonical_summary`
- `display_summary`
- 可靠的 pending chunk / 完成度信号

在这些能力成熟前，profile 最多只能基于 `category`、`subtype`、`summary` 做浅层策略；实现时必须避免把这种浅层策略描述成完整场景化输出。

## Profile-Level Curation

第四阶段需要把显著性、截断和展示策略明确落在 profile 层。

### 1. 不是所有底座状态都进入当前 profile

统一状态底座是总池，profile 只是按目的筛选后的投影。

### 2. 显著性依然是输出策略的一部分

即使 canonical state 已稳定，profile 仍要决定：

- 哪些状态优先展示
- 哪些状态降为 supporting context
- 哪些状态留在底座层但不进入当前输出

### 3. 显示表达可以随 profile 变化

如果第三阶段引入 `display_summary` 或等价设计，它在这里应被理解为：

- 面向 profile 的可读表达
- 而不是底层去重锚点

## Prompt, Aggregator, And Output Boundary

第四阶段继续沿用前序阶段的职责边界，并进一步明确：

### Prompt / Extractor

- 不负责选择输出 profile
- 不负责最终输出的情景化编排

### Aggregator / State Foundation

- 负责提供可供不同 profile 消费的 canonical state 与主体归属
- 不负责把每种情景都提前写成独立最终文案

### Profile / Output Layer

- 负责选择当前输出 profile
- 负责显著性排序、纳入裁剪、布局与展示文案
- 不负责重新发明主体归属或状态底座规则

## Completion Constraints

第四阶段继续要求输出完整性与完成度约束联动。

至少应满足：

- profile 输出不能忽略 pending chunks
- 相关文档尚未完整抽取时，profile 结果只能被视为阶段性结果
- `processed` 的最小语义必须与 profile 输出保持一致

## Now Vs Design-Frozen Later

### 现在建议冻结设计但不实现的内容

- `output_profile` 的最小概念与字段语义
- 默认 profile 与 `status.md` 的兼容定位
- “单次运行选一个 profile”的执行模型
- profile 层与状态底座层的职责边界

### 现在不建议立即实现的内容

- 一次性产出所有 profile 文件
- 复杂的 profile 组合与继承机制
- 基于关系图谱的自动场景拼装
- 用户可视化 profile 管理界面

### 后续可逐步实现的内容

- `default` profile 兼容壳层
- 单 profile 选择入口
- 默认 profile 的显著性与渲染策略
- 少量高价值 profile 的逐个落地
- profile 级完整性提示

## Non-goals

本阶段明确不解决以下问题：

- 不重新定义第一阶段来源类型边界
- 不重新定义第二阶段主体归属规则
- 不重新定义第三阶段统一状态底座模型
- 不要求系统同时满足所有情景
- 不建设 UI、服务端 API 或平台级权限系统
- 不引入重型关系推理与外部知识库
- 不在统一状态底座成熟前声称已经实现完整场景化筛选

## In Scope

- 冻结场景化输出 profile 的最小概念
- 冻结 profile 层与状态底座的消费边界
- 冻结 `status.md` 的默认 profile / 兼容定位
- 冻结 profile 层显著性与完整性约束的角色
- 明确哪些内容只冻结设计，不立即实现
- 明确推荐实施路径：兼容壳层先行，单 profile 选择其次，真实策略后置

## Out Of Scope

- 当前 turn 内直接实现 profile 选择机制或多文件输出
- 设计完整跨主体关系推理与权限逻辑
- 替换当前全部输出产物
- 声称场景化输出 profile 已经在仓库中实现

## Constraints

- keep current repository structure unless intentionally changed
- do not assume behavior that is not implemented
- mark uncertain facts as `需要人类确认`
- 第四阶段必须建立在前三阶段输出之上，不反向改写前序阶段文档边界
- 优先冻结 profile 契约与职责，再决定实际输出入口与文件布局
- `input_docs/` 视为潜在敏感输入，不在 retained docs 中复制长篇原文
- 若某些情景是否值得单独变成 profile 无法稳定判断，标为 `需要人类确认`

## Acceptance Criteria

- 存在一份独立 spec，且其范围只覆盖第四阶段“场景化输出 profile”
- spec 明确指出最终目标是“统一状态底座 + 场景化输出”，而不是“并行多视图输出”
- spec 明确规定项目通过 profile 满足不同情景，而不是同时满足所有情景
- spec 明确给出 `status.md` 的默认 profile / 兼容定位
- spec 明确规定 profile 层消费统一状态底座，而不是重新定义状态
- spec 明确指出哪些内容现在只冻结设计，不立即实现
- spec 明确推荐实现方式是“单 profile 选择机制 + profile-aware 输出策略”
- spec 明确 default profile 应先保持兼容输出
- spec 明确真实个人/团队/项目 profile 策略依赖主体归属与统一状态底座

## Reference Files

- AGENTS.md
- docs/specs/state_output_quality.md
- docs/specs/state_subject_attribution.md
- docs/specs/state_foundation.md
- docs/plans/state_output_quality.md
- docs/plans/state_subject_attribution.md
- docs/plans/state_foundation.md
- output/status.md
- layers/output_layer.py
- main.py
