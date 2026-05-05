# Contextual Bundle Narrative Plan

## Step 1

- Goal:
  冻结 narrative 阶段输出契约：主体作为一级分组，主题 bundle 作为阅读单位，正式 Markdown 不显示置信度，也不再渲染 state summary/detail 双层条目。
- Files likely touched:
  `docs/specs/contextual_bundle_narrative.md`
  `docs/plans/contextual_bundle_narrative.md`
  `AGENTS.md`
  `docs/architecture.md`
  `docs/changes.md`
- Validation:
  活跃 `docs/specs/` 与 `docs/plans/` 只保留 narrative pair 和 `_template.md`。
- Stop condition:
  后续实现者无需再决定是否保留主体层、是否增加主题层、是否显示置信度。

## Step 2

- Goal:
  在 output/profile 层新增只读 narrative 数据结构：`CandidateTopicBundle`、`BundleNarrative` 和 narrative diagnostics。
- Files likely touched:
  `layers/output_layer.py`
  `test_output_layer.py`
- Validation:
  至少验证同一主体下不同 section / topic 可以拆成多个主题 bundle，不同主体不合并，无 evidence 的 state 仍进入 `needs_context`。
- Stop condition:
  输出层能从现有 `ContextBundleSelection` 产生主题候选和 narrative 诊断，不新增数据库表。

## Step 3

- Goal:
  替换正式 Markdown 形态：渲染主体、主题标题、主题摘要、语义栏目和事实句；移除置信度和旧式 state title/detail 双层渲染。
- Files likely touched:
  `layers/output_layer.py`
  `test_output_layer.py`
- Validation:
  至少验证：
  - `status.md` 不包含 `置信度:`
  - `status.md` 不包含旧式 `- **state summary**` 条目形态
  - 输出包含主体层、主题层和 bundle summary
  - `needs_context` 不进入正式 Markdown
- Stop condition:
  读者看到的是主题报告，而不是套了 bundle 外壳的 state 清单。

## Step 4

- Goal:
  增加 deterministic rule narrative fallback。无 API 环境下也能生成主题标题、bundle summary 和栏目事实句。
- Files likely touched:
  `layers/output_layer.py`
  `test_output_layer.py`
- Validation:
  `python -m unittest test_output_layer.py`
- Stop condition:
  默认 `OUTPUT_NARRATIVE_MODE=rule` 可稳定生成输出，并且不产生无法追溯 source state 的事实句。

## Step 5

- Goal:
  增加可选 LLM narrative classifier。LLM 只整理单个 `CandidateTopicBundle` 内的阅读语义；失败、非法 JSON、非法 source id 均回退到 rule narrative。
- Files likely touched:
  `layers/output_layer.py`
  `test_output_layer.py`
  `docs/testing.md`
- Validation:
  至少验证：
  - fake LLM 返回合法 JSON 时使用 LLM narrative
  - fake LLM 返回非法 source id 时回退
  - 空栏目不渲染
  - 默认 rule 模式不需要真实 API
- Stop condition:
  LLM 分类可选、可测、可回退，不改变 extractor 或 aggregator 边界。

## Step 6

- Goal:
  同步文档事实源和验证命令。
- Files likely touched:
  `README.md`
  `docs/architecture.md`
  `docs/testing.md`
  `docs/changes.md`
  `AGENTS.md`
- Validation:
  推荐运行：
  `python -m unittest test_output_layer.py`
  `python -m unittest test_aggregator.py`
  `python test_extraction_schema.py`
  `python main.py --skip-extraction`
  `python main.py --stats`
- Stop condition:
  retained docs 不再把 archived discovery 文档描述成当前活跃 spec/plan。

## Long-Term Follow-Up

- 重新设计置信度语义，决定它表示抽取可信度、证据强度还是输出显著性。
- 观察主题 narrative 后再决定低信息条目的过滤、合并或诊断命运。
- 评估跨文档主题合并，但必须先定义更强的确认规则。
- 评估 LLM 摘要质量、成本、隐私和可重复性。
- 在上下文发现规则稳定后，再评估 `context_bundles` / `context_bundle_evidence` 持久化。
