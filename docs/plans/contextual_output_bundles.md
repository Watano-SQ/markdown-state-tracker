# Contextual Output Bundles Plan

## Step 1

- Goal:
  冻结 v1 输出契约。定义 `ContextBundle` 的字段语义、降级规则、bundle 小节，以及禁止硬补背景的边界。明确 v1 不新增 schema、不新增 CLI profile、不运行 `python main.py --init`。
- Files likely touched:
  `docs/specs/contextual_output_bundles.md`
  后续实现阶段预计影响：
  `layers/output_layer.py`
  `test_output_layer.py`
- Validation:
  spec 中至少明确：
  - `status.md` 的主输出单位是 bundle，不是单个 state item
  - bundle 从 `state_evidence` 回查 source chunk / document
  - 无法形成可靠上下文的 state 降级
  - 不把 pending relation/retrieval candidate 展示成确认事实
- Stop condition:
  后续实现者无需再决定 v1 是否新增 schema、是否改 extractor、是否继续输出碎片清单。

## Step 2

- Goal:
  实现只读 bundle 构造。输出层从 active states 出发，join `state_evidence -> chunks -> documents`，按同文档、相邻 chunk、section、主体线索和 canonical/display 语义线索做保守归组。
- Files likely touched:
  `layers/output_layer.py`
  `test_output_layer.py`
- Validation:
  至少验证：
  - 同文档相邻 chunk 的多个 state 输出为同一个 bundle
  - 跨文档且缺少共享主体/语义线索的 state 不误合并
  - 没有 evidence 的 state 不进入主 bundle
  - `generate_output()` 默认入口仍可生成 `output/status.md`
- Stop condition:
  输出层具备内存级 `ContextBundle` 构造路径，且不改变数据库 schema 或抽取 contract。

## Step 3

- Goal:
  改造 Markdown 渲染并补齐验证。将 `status.md` 从分类清单改为上下文报告；bundle 小节只在有证据时渲染；孤立状态进入待澄清或暂不展示。
- Files likely touched:
  `layers/output_layer.py`
  `test_output_layer.py`
  实现后视实际行为同步：
  `docs/architecture.md`
  `docs/testing.md`
  `docs/changes.md`
- Validation:
  至少运行：
  `python -m unittest test_output_layer.py`
  `python -m unittest test_aggregator.py`
  `python test_extraction_schema.py`
  `python main.py --skip-extraction`
  `python main.py --stats`
- Stop condition:
  `output/status.md` 的主阅读单位已经变成证据支撑的上下文 bundle，且测试覆盖聚合、降级、空小节省略和入口兼容。

## Long-Term Follow-Up

- v2:
  引入 profile 级完整性提示和更明确的 `needs_context` 输出策略。
- v3:
  在只读 bundle 规则稳定后，评估是否持久化 `context_bundles` / `context_bundle_evidence`。
- v4:
  在隐私、成本、可重复测试都可接受时，再评估 LLM 辅助标题和摘要生成。
- Boundary:
  长期仍保持 extractor 只负责 chunk 级观察，aggregator 负责状态底座，profile / output layer 负责上下文阅读视图。
