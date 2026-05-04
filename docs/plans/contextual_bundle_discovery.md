# Contextual Bundle Discovery Plan

## Step 1

- Goal:
  冻结下一阶段输出契约：`status.md` 只输出可靠 bundle，`needs_context` 不作为正式章节渲染。明确本阶段不设置 max bundle、max item 或待补全数量阈值。
- Files likely touched:
  `docs/specs/contextual_bundle_discovery.md`
  后续实现阶段预计影响：
  `layers/output_layer.py`
  `test_output_layer.py`
- Validation:
  spec 中至少明确：
  - 可靠 bundle 才进入 `status.md`
  - `needs_context` 只进入内部诊断或返回值，不进入正式 Markdown
  - 输出数量阈值后置到诊断观察之后
- Stop condition:
  后续实现者无需再决定是否渲染 `待澄清`、是否先设置阈值、是否把未补全 state 混入主输出。

## Step 2

- Goal:
  将 bundle 构造改成两层上下文发现：先做局部归组，再做同文档远距离强锚点回收。
- Files likely touched:
  `layers/output_layer.py`
  `test_output_layer.py`
- Validation:
  至少验证：
  - 同文档相邻 chunk 仍能形成 bundle
  - 同文档远距离 chunk 共享强锚点时能合并
  - 不共享强锚点的远距离 chunk 不误合并
  - 跨文档默认不因弱关键词误合并
- Stop condition:
  bundle 构造不再只依赖相邻 chunk，能够处理文档开头和结尾谈同一事件的情况。

## Step 3

- Goal:
  为上下文不足的 state 增加当前可用的本地补全能力。先使用 source evidence chunk、邻近 chunk、同文档其他 chunk；白名单目录 / 补充材料仅在显式可用时接入；完整补全链路和 retrieval / MCP / 联网搜索只记录为后续方向。
- Files likely touched:
  `layers/output_layer.py`
  `test_output_layer.py`
  如引入白名单常量或配置，视实际实现同步相关文档
- Validation:
  至少验证：
  - 单条 state 可通过邻近 chunk 补足上下文形成 bundle
  - 单条 state 可通过同文档远距离强锚点补足上下文形成 bundle
  - 未显式配置白名单补充材料时，不扫描任意目录
  - 补全失败的 state 不进入 `status.md`
- Stop condition:
  上下文不足的 state 会先使用当前可用的本地路径；仍无法形成可靠 bundle 时暂不输出。完整补全链路保留为后续版本任务。

## Step 4

- Goal:
  增加诊断信息而不是阈值。记录 bundle 数量、每个 bundle 的 state 数、合并依据、未进入 bundle 的 state 数量和原因，以及疑似过大 bundle / 误合并信号。
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
  实现后可以观察真实 bundle 分布，但 `status.md` 仍只展示可靠 bundle，不展示诊断明细或待澄清清单。

## Long-Term Follow-Up

- After diagnostics:
  再决定是否需要 max bundle、max item、bundle 拆分或排序阈值。
- Needs context:
  若未归组 state 数量长期较高，再评估 `needs_context` 持久化或单独诊断输出。
- Persistence:
  只有在上下文发现规则稳定后，再评估 `context_bundles` / `context_bundle_evidence` schema。
- Full completion chain:
  source evidence chunk、邻近 chunk、同文档其他 chunk、白名单补充材料、retrieval、MCP、联网搜索这条完整链路作为后续版本路线记录，不要求本阶段一次实现。
