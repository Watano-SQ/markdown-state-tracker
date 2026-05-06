# Contextual Bundle Reading View Plan

## Step 1

- Goal:
  冻结下一阶段输出契约：主题 bundle 内采用平铺证据句，不再渲染 `当前目标` / `进展` / `问题` / `下一步` / `相关线索` 等硬分类标题；bundle 只有一个 summary，子条目不再显示 state summary 标签。
- Files likely touched:
  `docs/specs/contextual_bundle_reading_view.md`
  `docs/plans/contextual_bundle_reading_view.md`
  `docs/archive/specs/contextual_bundle_narrative.md`
  `docs/archive/plans/contextual_bundle_narrative.md`
  `AGENTS.md`
  `README.md`
  `docs/architecture.md`
  `docs/changes.md`
- Validation:
  活跃 `docs/specs/` 与 `docs/plans/` 只保留 reading view pair 和 `_template.md`。
- Stop condition:
  后续实现者无需再决定是否保留硬分类标题、是否允许 `summary：detail`、是否把 `needs_context` 渲染进正式 Markdown。

## Step 2

- Goal:
  修改 Markdown 渲染：`BundleNarrative.sections` 可以继续作为内部结构存在，但正式输出只渲染平铺子项目；子项目文本优先 detail / evidence，不再拼接 summary 和 detail。
- Files likely touched:
  `layers/output_layer.py`
  `tests/test_output_layer.py`
- Validation:
  `python -m unittest tests.test_output_layer`
  至少覆盖：
  - 不渲染 `##### 进展` / `##### 问题` / `##### 下一步`
  - 不渲染 `summary：detail`
  - `needs_context` 仍不进入正式 Markdown
- Stop condition:
  示例中的多个硬分类块能收敛为同一主题 bundle 下的平铺证据句。

## Step 3

- Goal:
  重写规则 bundle summary 和标题清洗策略。summary 说明上下文，不枚举子条目；标题拒绝 `工具：`、`问题：`、`相关线索` 等弱标签，并回退到强锚点、文档标题或 section 上下文。
- Files likely touched:
  `layers/output_layer.py`
  `tests/test_output_layer.py`
- Validation:
  `python -m unittest tests.test_output_layer`
  至少覆盖：
  - summary 不包含 `主要涉及：` / `核心信息是：`
  - 弱标题 candidate 不以 `工具：` 形式进入正式 Markdown
  - 无法生成可靠 summary 的 candidate 被省略到诊断
- Stop condition:
  bundle summary 不再是 details 和 details summary 的拼接。

## Step 4

- Goal:
  强化当前可用的本地上下文发现路径：source evidence chunk、邻近 chunk、同文档其他 chunk，以及显式可用的白名单补充材料。暂不接入 retrieval / MCP / 联网搜索。
- Files likely touched:
  `layers/output_layer.py`
  `tests/test_output_layer.py`
  可选：轻量配置文件或 output profile 配置，如果仓库已有合适入口。
- Validation:
  `python -m unittest tests.test_output_layer`
  至少覆盖：
  - 同文档远距离强锚点可回收为同一 bundle
  - 跨文档无证据关联不误合并
  - 上下文不足 state 不进入正式 Markdown
  - 诊断记录未归组原因
- Stop condition:
  输出层先穷尽本地可用上下文，再决定省略，而不是把碎片状态暴露给读者。

## Step 5

- Goal:
  处理低信息评价类 state。它们不能独立成 bundle；只有能支撑工具选择、替代方案、偏好或决策上下文时才吸收，否则进入 omitted diagnostics。
- Files likely touched:
  `layers/output_layer.py`
  `tests/test_output_layer.py`
- Validation:
  `python -m unittest tests.test_output_layer`
  至少覆盖：
  - `高度认可WhisperDesktop：WhisperDesktop，伟大。` 不出现在正式 Markdown
  - 孤立短评价不独立成 bundle
  - 有工具比较上下文时，评价类 state 可以被吸收为不带 summary 标签的证据句
- Stop condition:
  低信息感叹不再被包装成正式主题。

## Step 6

- Goal:
  对齐可选 LLM narrative classifier。LLM 仍可输出内部 kind，但 renderer 不把 kind 变成可见硬分类；非法 JSON、非法 source id、硬补背景或不可兼容输出仍回退到 rule narrative。
- Files likely touched:
  `layers/output_layer.py`
  `tests/test_output_layer.py`
  `docs/testing.md`，仅当验证命令或环境变量事实变化时更新。
- Validation:
  `python -m unittest tests.test_output_layer`
  至少覆盖：
  - fake LLM 成功输出时仍使用平铺 Markdown
  - fake LLM 返回非法 source id 时回退
  - fake LLM 输出空 summary 或无 source 的事实句时回退或省略
- Stop condition:
  LLM 路径和 rule 路径遵守同一个正式输出契约。

## Step 7

- Goal:
  同步行为文档和最小验证集合。只有代码行为真实落地后，再把 `docs/architecture.md` 中的输出层事实改成 reading view 已实现。
- Files likely touched:
  `docs/architecture.md`
  `docs/testing.md`
  `docs/changes.md`
  `AGENTS.md`
  `README.md`
- Validation:
  后续实现阶段优先运行：
  `python -m unittest tests.test_output_layer`
  如实际生成输出，再运行：
  `python main.py --skip-extraction`
  `python main.py --stats`
- Stop condition:
  retained docs 清楚区分“当前已实现事实”和“下一阶段 active plan/spec”。

## Long-Term Follow-Up

- 先观察无数量阈值的真实输出分布，再决定 max bundle、max item、排序和拆分策略。
- 后续再评估 profile 级 `needs_context` 持久化或诊断报告。
- 白名单补充材料需要明确目录、准入和隐私边界后再扩大使用。
- retrieval / MCP / 联网搜索留到后续版本评估，不进入当前默认补全链路。
- 规则稳定后再评估 `context_bundles` / `context_bundle_evidence` 持久化。
