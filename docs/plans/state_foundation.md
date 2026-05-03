# State Foundation Plan

## Step 1

- Goal:
  冻结第三阶段的统一状态底座目标。先明确状态层不是展示 bullet 列表，而是 subject-aware 的语义底座；同时明确状态身份至少依赖主体维度与 canonical 语义，而不再只靠 raw summary。
- Files likely touched:
  `docs/specs/state_foundation.md`
  后续实现阶段预计影响：
  `layers/aggregator.py`
  `layers/middle_layer.py`
- Validation:
  spec 中至少要明确：
  - 状态层与展示层的职责分离
  - 状态身份的最小维度
  - 为什么 raw summary 不能继续承担唯一主键职责
- Stop condition:
  后续实现者无需再把 `states.summary` 同时当作语义标识、去重键和展示文案。

## Step 2

- Goal:
  冻结 canonical / display 分离方案与聚合责任。核心是评估 `canonical_summary` / `display_summary` 或等价设计，并明确 aggregator 负责 canonical state 构造，后续场景化输出 profile 只消费底座。
- Files likely touched:
  `docs/specs/state_foundation.md`
  后续实现阶段预计影响：
  `layers/aggregator.py`
  `layers/middle_layer.py`
  必要时 `.github/EXTRACTION_JSON_SCHEMA.md`
- Validation:
  spec 中至少明确以下内容：
  - canonical / display 的职责
  - 过渡方案 A/B
  - 哪些字段或概念可先在中间结构中落地
  - prompt 与 aggregator 在 canonical 化中的边界
- Stop condition:
  后续实现者无需再把“展示上顺口”当作状态归并标准，也无需再把 canonical 责任交给 prompt。

## Step 3

- Goal:
  冻结第三阶段的实现边界与后续衔接方式。重点是明确哪些底座内容适合在主体归属稳定后尽快实现，哪些重型能力只先冻结为第四阶段场景化输出 profile 的设计输入。
- Files likely touched:
  `docs/plans/state_foundation.md`
  `docs/specs/state_foundation.md`
  后续实现阶段可能新增最小测试文件，例如针对 canonical state 构造与归并的测试
- Validation:
  计划文档应明确：
  - 现在可做的最小实现：canonical 概念、subject-aware identity、聚合归并基础
  - 先冻结但不实现：registry、层级状态、重型迁移
  - 后续阶段依赖：场景化输出 profile 与 profile 级显示文案
- Stop condition:
  第三阶段的最小可实施范围与后续冻结设计边界都已明确，后续可以在不破坏前两阶段工作的前提下推进统一状态底座。
