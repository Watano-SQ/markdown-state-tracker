# Contextual Bundle Reading View Spec

## Goal

把已实现的主体 / 主题 `BundleNarrative` 继续收敛成真正可读的上下文报告，而不是带有语义栏目外壳的碎片 state 清单。

本阶段仍只修改 output/profile 层的只读投影和 Markdown 渲染契约，不新增 SQLite schema，不改变 extractor contract，不让 aggregator 负责最终报告结构。

任务完成后，应满足以下事实：

- `status.md` 只输出已经形成可靠上下文的主题 bundle。
- 主题 bundle 内不再渲染固定小节标题，例如 `当前目标`、`进展`、`问题`、`下一步`、`相关线索`。
- 每个正式输出的主题 bundle 只有一个 bundle-level summary。
- bundle summary 必须是对上下文的综合说明，不得只是子条目 summary/detail 的拼接或枚举。
- 子条目不渲染 state summary 标签，不出现 `summary：detail` 或等价形态。
- 子条目优先使用 detail / evidence 支撑的事实句；只有缺少 detail 且仍有上下文价值时，才允许 fallback 到 summary。
- 低信息评价类 state 不得独立构成正式 bundle；只有在能支撑工具选择、偏好判断或决策上下文时才可被吸收，否则进入内部诊断。
- `needs_context` / omitted state 仍不作为正式 Markdown 章节展示。

## Problem Focus

当前实现方向正确，但真实输出暴露了新的阅读问题：

- 硬分类把同一上下文切成很多小块。读者看到 `进展`、`问题`、`相关线索` 交替出现，仍需要自己把它们拼回一个事件。
- 子条目仍可能输出 `高度认可WhisperDesktop：WhisperDesktop，伟大。` 这类 `summary：detail` 形态，说明 state summary 仍在正式条目中泄漏。
- 规则 summary 可能退化成 `details + details 的 summary`，例如用 `主要涉及：A；B` 枚举子条目，而不是说明这个 bundle 到底是什么上下文。
- 弱标题如 `工具：` 会把一组状态包装成没有主题感的 bundle。
- 主观赞美、短感叹、单独的工具名等低信息 state，如果没有更大的排查或选择上下文，不应进入正式输出。

## Output Contract

目标 Markdown 结构：

```markdown
## 上下文报告

### 主体名称

#### 主题标题

主题摘要段落。

- 事实句或上下文线索。
- 事实句或上下文线索。
- 事实句或上下文线索。
```

正式输出要求：

- 不渲染 `##### 当前目标`、`##### 进展`、`##### 问题`、`##### 下一步`、`##### 相关线索` 等固定语义小节。
- 内部可以继续保留 kind / section / subtype，用于排序、诊断、LLM 校验或测试，但这些分类不直接暴露为读者标题。
- 每条子项目必须能追溯到一个或多个 source state/evidence。
- 子项目文本不使用 state summary 作为前缀标签。
- 子项目不显示 source ids、confidence、omitted reason 或诊断字段。
- 空 bundle、弱标题 bundle、无法生成可靠 summary 的 bundle 不进入正式输出。
- `status.md` 不渲染 `待澄清` 章节；上下文不足条目只进入内部诊断。

## Bundle Summary Contract

bundle summary 是读者进入该 bundle 的上下文入口，不是子项目列表的压缩版。

允许：

- 用一两句话说明主题范围、当前状态、主要矛盾或已知结论。
- 使用 state/evidence/chunk 局部上下文中可追溯的信息。
- 在信息不足时保持保守，例如只说明“这是一次围绕某工具/问题的排查上下文”，但前提是标题和证据足够可靠。

禁止：

- 用 `主要涉及：A；B；C` 罗列子条目。
- 用 `核心信息是：A` 复制第一条子项目。
- 把 state summary 和 detail 拼接成 summary。
- 为了让 summary 看起来完整而补不存在的背景。
- 使用 `工具：`、`问题：`、`相关线索` 等泛化标签作为主题标题或 summary 主体。

若无法生成比条目罗列更有价值的 summary，该 candidate bundle 暂不进入正式输出，并在诊断中记录原因。

## Child Item Contract

正式子条目是 bundle 内的证据句，不是 state 卡片。

文本选择顺序：

1. 优先使用 `detail` 中可独立阅读且可追溯的事实。
2. 若 `detail` 不可用，使用 evidence excerpt 或 chunk 局部上下文形成保守事实句。
3. 只有缺少 detail/evidence 文本但 summary 本身仍有上下文价值时，才 fallback 到 `summary`。

禁止：

- `summary：detail`
- `summary - detail`
- `summary（detail）`
- 旧式 `- **summary**` + detail 双层渲染
- 单独输出无法说明上下文的短评价，例如只有“伟大”“好用”“失败了”而没有对象和场景

评价类 state 的处理：

- 若它支持一个可靠 bundle，例如工具比较、替代方案选择或使用体验总结，可以吸收为子项目。
- 若它只是孤立赞美或情绪记录，不构成正式输出事实，进入 omitted diagnostics。

## Context Discovery Contract

正式 bundle 必须先形成可靠上下文，再进入 `status.md`。

当前阶段使用本地可用路径，不要求一次走完整补全链路：

1. source evidence chunk
2. 邻近 chunk
3. 同文档其他 chunk
4. 显式白名单目录 / 补充材料，如果当前仓库已有可用入口或可以用轻量配置接入

归组分两层：

- 局部归组：同文档、相邻 chunk、同 section。
- 远距离回收：同文档内共享强锚点时可以合并，例如 subject、项目名、工具名、模型名、issue 编号、canonical/display 主题词、可追溯 retrieval candidate 线索。

限制：

- 暂不把 retrieval / MCP / 联网搜索作为默认补全路径。
- `retrieval_candidates` 只能作为待确认线索，不能渲染成已确认事实。
- `relation_candidates` 不参与正式 bundle 构造。
- 跨文档主题合并仍默认不做，除非未来 spec 定义更强确认规则。

## Diagnostics Contract

本阶段暂不设置 max bundle / max item / summary length 等数量阈值。

实现后应通过返回值、日志或测试可观察以下诊断：

- bundle 数量
- 每个 bundle 的 state 数
- 每个 bundle 的合并依据
- 未进入 bundle 的 state 数量和原因
- 弱标题候选数量
- 低信息评价类 state 的吸收或省略原因
- 疑似过大 bundle 或疑似误合并候选

这些诊断用于下一轮决定阈值、排序、拆分和 `needs_context` 命运，不直接渲染给普通读者。

## Data Model Boundary

- 继续使用 output/profile 层只读投影。
- 不新增 SQLite schema。
- 不改 `states` / `state_evidence` 的持久化 contract。
- 不改 extraction JSON schema。
- 不让 aggregator 负责最终报告结构。
- 不把 LLM narrative 结果持久化为状态事实。

## LLM Boundary

LLM narrative classifier 仍是可选输出整理器。

- 默认 rule 模式必须可运行、可测试、可复现。
- LLM 可帮助生成主题标题、bundle summary 和子项目事实句，但必须只消费单个 candidate bundle 的证据材料。
- LLM 输出如果仍包含 kind，可作为内部排序/诊断字段；Markdown 渲染不把 kind 变成固定小节标题。
- LLM 不得补外部背景，不得引用不存在的 source state id。
- LLM 失败、JSON 非法、source id 非法、输出硬分类不可兼容时，回退到 rule narrative。

## Non-goals

- 不在本阶段实现完整补全链路。
- 不接入 MCP / 联网搜索。
- 不把 retrieval candidate 当成确认事实。
- 不新增持久化 `context_bundles` / `context_bundle_evidence`。
- 不设置输出数量阈值。
- 不重新设计置信度语义。
- 不把低信息 state 全部删除；只是不进入正式 Markdown。
- 不把上下文聚合下沉到 extractor。

## Long-Term Planning

- 先观察无数量阈值的真实输出分布，再决定 max bundle、max item、排序、拆分和省略策略。
- 若低信息 / 需补全条目持续有价值，再评估 profile 级 `needs_context` 持久化或诊断报告。
- 若本地上下文不足，再评估白名单补充材料的显式目录、准入和隐私规则。
- retrieval / MCP / 联网搜索只作为后续版本补全路径，必须先解决隐私、成本、可重复测试和事实确认边界。
- 只有当规则稳定后，才评估持久化 `context_bundles` / `context_bundle_evidence`。
- 长期仍保持 extractor 只产生 chunk 级观察，profile/output 负责阅读视图。

## Acceptance Criteria

- `status.md` 中不出现固定语义小节标题：`##### 当前目标`、`##### 进展`、`##### 问题`、`##### 下一步`、`##### 相关线索`。
- `status.md` 中不出现 `summary：detail` 形态；例如不得输出 `高度认可WhisperDesktop：WhisperDesktop，伟大。`。
- bundle summary 不使用 `主要涉及：` 或 `核心信息是：` 罗列子条目。
- 弱标题如 `工具：` 不作为正式主题标题；必须替换为可靠强锚点、文档/section 推断标题，或省略该 candidate。
- 同一上下文内的进展、问题、线索、下一步作为同一个 bundle 的平铺证据句输出，而不是拆成多个可见小节。
- 无 evidence 或上下文不足的 state 不进入正式 Markdown。
- 低信息评价类 state 不独立成 bundle；能支撑上下文时吸收，不能支撑时省略到诊断。
- 不新增 SQLite schema，不运行 `python main.py --init`。
- `python -m unittest tests.test_output_layer` 覆盖平铺渲染、summary 非拼接、子条目无 summary 标签、弱标题过滤、低信息评价类处理和诊断。

## Reference Files

- AGENTS.md
- README.md
- docs/architecture.md
- docs/testing.md
- docs/changes.md
- docs/archive/specs/contextual_bundle_narrative.md
- docs/archive/plans/contextual_bundle_narrative.md
- layers/output_layer.py
- tests/test_output_layer.py
- output/status.md
