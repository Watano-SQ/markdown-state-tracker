# State Subject Attribution Plan

## Step 1

- Goal:
  冻结第二阶段的解释模型：文档作者不再等于默认状态主体，候选主体需要按文档模式与上下文判定。明确 `document_mode` 的最小范围，以及 person / team / project / organization 的主体分类边界。
- Files likely touched:
  `docs/specs/state_subject_attribution.md`
  后续实现阶段预计影响：
  `layers/extractors/prompts.py`
  `layers/aggregator.py`
- Validation:
  spec 中至少要明确：
  - document author 与 state subject 的关系
  - `document_mode: personal / team / hybrid`
  - `subject_type` 的最小范围
  - 哪些主体归属场景需要 `需要人类确认`
- Stop condition:
  后续实现者无需再以“文档作者本人”作为唯一默认主体，也无需再把团队/项目语义塞回作者口径。

## Step 2

- Goal:
  冻结候选准入规则与 contract 边界。核心是定义 `subject_key`、直接准入 / 条件准入 / 默认拒绝 的裁决逻辑，并明确 prompt 负责减脏候选、aggregator 负责最终裁决。
- Files likely touched:
  `docs/specs/state_subject_attribution.md`
  后续实现阶段预计影响：
  `layers/extractors/prompts.py`
  `layers/aggregator.py`
  必要时 `.github/EXTRACTION_JSON_SCHEMA.md`
- Validation:
  spec 中至少明确以下内容：
  - `subject_key` 的最小语义
  - 三类准入规则
  - prompt 与 aggregator 的职责边界
  - 哪些字段建议现在就准备，哪些先冻结设计
- Stop condition:
  后续实现者无需再用“像状态句就准入”的标准处理候选，也无需再把主体判定完全交给 prompt。

## Step 3

- Goal:
  冻结第二阶段的实现边界与后续衔接方式。重点是明确哪些内容适合在第一阶段完成后立即实现，哪些内容只保留为第三阶段统一状态底座与第四阶段场景化输出 profile 的设计输入。
- Files likely touched:
  `docs/plans/state_subject_attribution.md`
  `docs/specs/state_subject_attribution.md`
  后续实现阶段可能新增最小测试文件，例如针对主体归属与候选裁决的测试
- Validation:
  计划文档应明确：
  - 现在可做的最小实现：`document_mode`、`subject_type`、`subject_key`、准入裁决
  - 先冻结但不实现：主体 registry、alias、层级关系
  - 后续阶段依赖：统一状态底座与场景化输出 profile
- Stop condition:
  第二阶段的最小可实施范围与后续冻结设计边界都已明确，后续可以在不打断第一阶段工作的前提下继续推进。
