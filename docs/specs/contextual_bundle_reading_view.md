# Contextual Bundle Reading View Spec

## Task

任务名：`output_reading_roles_and_clusters`

中文标题：输出层阅读角色与阅读簇修正

本任务是当前 `contextual_bundle_reading_view` 的增量修正，不是新一轮 schema、prompt 或 aggregator 重构。

## Goal

把已实现的主体 / 主题 `BundleNarrative` 继续收敛成真正可读的上下文报告，而不是带有语义栏目外壳的碎片 state 清单。

本阶段只修改 output/profile 层的只读投影、阅读角色判断、阅读簇归组和 Markdown 渲染契约。不新增 SQLite schema，不改变 extractor contract，不让 aggregator 负责最终报告结构，也不把输出层归组结果反向写回 state identity。

任务完成后，应满足以下事实：

- `status.md` 只输出已经形成可靠阅读上下文的主题 bundle。
- 主题 bundle 内不再渲染固定小节标题，例如 `当前目标`、`进展`、`问题`、`下一步`、`相关线索`。
- 每个正式输出的主题 bundle 只有一个 bundle-level summary。
- bundle summary 必须是对上下文的综合说明，不得只是子条目 summary/detail 的拼接或枚举。
- 子条目不渲染 state summary 标签，不出现 `summary：detail` 或等价形态。
- 子条目优先使用 detail / evidence 支撑的事实句；只有缺少 detail 且仍有上下文价值时，才允许 fallback 到 summary。
- 短语用状态是否进入正式输出，不由句子长短决定，也不由“是不是评价句”决定，而由它在阅读视图中的输出角色决定。
- 多主体上下文通过阅读簇归组表达，不改变任何 state 的 `subject_type` / `subject_key`。
- `needs_context` / omitted state 仍不作为正式 Markdown 章节展示。

## Scope

本轮只改：

- `layers/output_layer.py`
- `tests/test_output_layer.py`
- `docs/specs/contextual_bundle_reading_view.md`
- `docs/plans/contextual_bundle_reading_view.md`
- `docs/changes.md`
- `docs/architecture.md`

本轮不改：

- `db/schema.py`
- `layers/aggregator.py`
- `layers/middle_layer.py`
- `layers/extractors/prompts.py`
- `.github/EXTRACTION_JSON_SCHEMA.md`
- `tools/observation_support_audit.py`

## Concepts To Replace

旧说法必须废弃或改写为设计历史，不再作为正式内部分类：

- `低信息评价`
- `孤立低信息评价`
- `评价类 state 不能独立成 bundle`

新说法：

- `短语用状态`
- `输出角色`
- `单状态可读性审查`
- `阅读簇归组`

更准确的判断方式：

一条状态是否进入正式输出，不由句子长短决定，也不由“是不是评价句”决定，而由它在阅读视图中的角色决定。

例如 `WhisperDesktop，伟大。` 不能因为短小被降级。它可能是：

- 可独立输出：如果主体、对象、评价关系都清楚。
- 可作为支撑：如果它服务于工具选择、替代方案、偏好或决策上下文。
- 暂不输出：如果当前无法确定主体、对象或语用关系。

## Output Role

新增 output-only 内部概念：输出角色。

输出角色只决定一条 state 在阅读视图中如何使用，不改变数据库中的 state。

三个角色：

- 可独立输出：这条状态本身已经足以让读者理解“谁 / 什么对象 / 处于什么状态或态度”。
- 可作为支撑：这条状态不适合单独成为主题，但能支撑另一个项目、工具、事件、人物或团队上下文。
- 暂不输出：状态有证据链，但当前输出层没有足够上下文让读者可靠理解；只进入内部诊断。

建议内部结构：

```python
@dataclass(frozen=True)
class ReadingDecision:
    """
    输出层内部审查结果。
    它只决定某条状态在阅读视图中的使用方式，不改变数据库中的 state。
    """

    state_id: int
    # 被审查的状态编号。

    role: str
    # 状态在阅读视图中的角色。
    # "standalone" 表示可独立输出。
    # "supporting" 表示可作为其他阅读簇的支撑材料。
    # "defer" 表示暂不输出，只进入内部诊断。

    reason: str
    # 中文理由。说明为什么采用该角色。

    evidence_signals: tuple[str, ...]
    # 本次判断使用到的证据信号。
    # 例如：有证据 chunk、有明确主体、有明确对象、有相邻上下文、有事件线索。

    missing_signals: tuple[str, ...]
    # 暂不输出或不能独立输出时缺少的信号。
    # 例如：缺少明确对象、缺少主体、缺少可解释上下文。
```

字段名可以是英文，但每个字段必须有中文注释，不允许只靠字段名猜含义。

## Single-State Readability Review

正式名称：单状态可读性审查。

不再使用 `single-rich`。

它回答的问题是：

如果一个 state 没有其他 state 陪伴，它是否仍然能构成读者可理解的输出？

审查逻辑：

第一步：检查证据链。

- 如果没有 `state_evidence`，角色为暂不输出，理由为状态没有可追溯证据。
- 如果证据不能回到 chunk 或 document，角色为暂不输出，理由为状态不能回到原始上下文。

第二步：检查最小语义结构。

- 如果有明确主体，记录“有明确主体”。
- 如果有明确对象或主题，记录“有明确对象”。
- 如果状态表达了动作、变化、阻塞、决策、偏好、评价、计划中的任一类关系，记录“有可读关系”。
- 如果主体、对象、关系三者能形成可解释陈述，进入第三步。
- 否则角色为暂不输出，理由为读者无法从当前状态恢复基本语义结构。

第三步：决定输出角色。

- 如果状态本身已经能形成完整陈述，角色为可独立输出。
- 如果它能支撑附近某个阅读簇，角色为可作为支撑。
- 否则角色为暂不输出。

判断依据优先来自：

- state 的主体字段
- state 的 summary / detail
- `state_evidence` 指向的 chunk
- document title
- section label
- 相邻 chunk
- `extraction_json` 中已有的 entities / events / relation_candidates

限制：

- 不能硬编码“伟大 / 喜欢 / 好用”之类词表作为降级条件。
- `relation_candidates` 只能作为解释线索，不能当成正式关系事实，因为当前架构明确关系持久化还没有完成。

## Reading Cluster Grouping

正式说法：阅读簇归组。

不使用“subject 合并”或“主体合并”来描述本阶段行为。

阅读簇定义：

阅读簇是输出层为了读者理解而临时形成的上下文集合。它可以包含多个不同主体的 state。它不改变任何 state 的 `subject_type` / `subject_key`。

建议内部结构：

```python
@dataclass(frozen=True)
class ReadingCluster:
    """
    阅读视图中的上下文簇。
    它把若干状态组织到同一个读者可理解的上下文中。
    它不是数据库事实，不改变任何 state 的主体字段。
    """

    cluster_id: str
    # 输出层临时编号，只用于诊断和测试，不落库。

    title: str
    # 阅读簇标题。
    # 应来自章节、文档标题、明确项目名、明确事件名或强锚点。

    state_ids: tuple[int, ...]
    # 被放进同一个阅读簇的状态编号。

    primary_state_ids: tuple[int, ...]
    # 构成该阅读簇主叙述的状态编号。

    supporting_state_ids: tuple[int, ...]
    # 只作为支撑材料的状态编号。

    subject_identities: tuple[tuple[str | None, str | None], ...]
    # 阅读簇中出现过的主体身份。
    # 多主体只表示共同出现在同一阅读上下文，不表示主体被合并。

    merge_reasons: tuple[str, ...]
    # 这些状态被放入同一阅读簇的理由。
    # 例如：同一文档、相邻 chunk、同一章节、共享工具对象、共享事件线索。

    risk_flags: tuple[str, ...]
    # 可能误归组的风险提示。
```

归组逻辑：

第一步：先按文档分组。

- 不同文档默认不进入同一阅读簇。

第二步：在同一文档内提取阅读锚点。

阅读锚点包括：

- 主体
- 对象
- 章节标题
- 证据 chunk 位置
- 实体线索
- 事件线索
- 工具名、项目名、代码符号、issue 编号等强锚点

第三步：判断两条状态是否可以连接。

- 如果来自相邻 chunk，且共享章节、实体、对象或事件线索，可以连接。
- 如果不相邻，但共享强锚点，可以连接。
- 如果一条状态的主体是另一条状态的对象，可以连接，但标记为“主体—对象连接”，不是主体合并。
- 如果只是同一文档，没有共享对象、章节、事件或强锚点，不连接。

第四步：形成阅读簇。

- 如果簇内只有一个状态，交给单状态可读性审查。
- 如果簇内有多个主体，保留所有主体身份。
- 多主体簇标题优先来自章节、共享事件、共享项目或文档标题，不把整个簇归属给第一个主体。

## Output Contract

目标 Markdown 结构：

```markdown
## 上下文报告

### 主体名称或阅读簇归属

#### 阅读簇标题

主题摘要段落。

- 事实句或上下文线索。
- 事实句或上下文线索。
- 事实句或上下文线索。
```

正式输出要求：

- 不渲染 `##### 当前目标`、`##### 进展`、`##### 问题`、`##### 下一步`、`##### 相关线索` 等固定语义小节。
- 内部可以继续保留 kind / section / subtype / role / cluster diagnostics，用于排序、诊断、LLM 校验或测试，但这些分类不直接暴露为读者标题。
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
- 仅因句子短小、语气像评价或表达偏好就自动降级

短语用状态处理：

- 若主体、对象和语用关系清楚，可以独立输出。
- 若它支持一个可靠阅读簇，例如工具比较、替代方案选择、使用体验、阻塞排查或决策上下文，可以吸收为子项目。
- 若当前缺少主体、对象或可解释上下文，进入 omitted diagnostics。

## Context Discovery Contract

正式 bundle 必须先形成可靠上下文，再进入 `status.md`。

当前阶段使用本地可用路径，不要求一次走完整补全链路：

1. source evidence chunk
2. 邻近 chunk
3. 同文档其他 chunk
4. 显式白名单目录 / 补充材料，如果当前仓库已有可用入口或可以用轻量配置接入

阅读簇归组分两层：

- 局部归组：同文档、相邻 chunk、同 section、共享对象、共享事件线索。
- 远距离回收：同文档内共享强锚点时可以合并，例如项目名、工具名、模型名、issue 编号、代码符号、canonical/display 主题词、可追溯 retrieval candidate 线索。

限制：

- 暂不把 retrieval / MCP / 联网搜索作为默认补全路径。
- `retrieval_candidates` 只能作为待确认线索，不能渲染成已确认事实。
- `relation_candidates` 可以作为阅读解释线索，但不参与正式 relation 持久化，也不能渲染成已确认关系事实。
- 跨文档主题合并仍默认不做，除非未来 spec 定义更强确认规则。

## LLM Review Boundary

本轮可以预留 LLM 审查模式，但默认实现仍是 rule 模式。

建议环境变量：

```text
OUTPUT_READING_REVIEW_MODE=rule|llm|auto
```

含义：

- `rule`：默认模式，只使用确定性规则和已有数据库/抽取结果。
- `llm`：对输出角色和阅读簇进行 LLM 审查，但不能生成新事实。
- `auto`：规则无法判断时才调用 LLM。

LLM 输出只能是审查，不是事实生成：

```json
{
  "role": "standalone | supporting | defer",
  "reason": "中文理由",
  "target_topic_hint": "建议归入的阅读簇标题，可为空",
  "supporting_to_state_ids": [1, 2],
  "used_evidence": ["state_detail", "chunk_text", "neighbor_state"]
}
```

回退规则：

- 如果 LLM 返回不存在的 state_id，丢弃 LLM 结果，回退规则模式。
- 如果 LLM 使用输入中不存在的信息，丢弃 LLM 结果，回退规则模式。
- 如果 LLM 没有给出中文理由，丢弃 LLM 结果，回退规则模式。

LLM 审查与当前 narrative classifier 方向一致：LLM 可以作为内部整理器或审查器，但 renderer 不把内部 kind 变成可见硬分类，非法输出必须回退。

## Diagnostics Contract

本阶段暂不设置 max bundle / max item / summary length 等数量阈值。

实现后应通过返回值、日志或测试可观察以下诊断：

- bundle / reading cluster 数量
- 每个 reading cluster 的 state 数
- 每个 reading cluster 的合并依据
- 每个 state 的输出角色和中文理由
- 未进入 bundle 的 state 数量和原因
- 弱标题候选数量
- 短语用状态被独立输出、作为支撑或暂不输出的原因
- 多主体阅读簇中的主体身份列表
- 疑似过大 bundle 或疑似误合并候选

这些诊断用于下一轮决定阈值、排序、拆分和 `needs_context` 命运，不直接渲染给普通读者。

## Regression Cases

样例一：短评价句不是降级信号。

- 输入：`WhisperDesktop，伟大。`
- 期望：不得因为短小被降级；不得标记为正式内部分类中的低信息。
- 如果主体、对象、评价关系都清楚，可以独立输出。
- 如果它服务于工具比较或替代决策，可以作为支撑。
- 如果缺主体或对象，才暂不输出。

样例二：短句不等于自动输出。

- 输入：`伟大。`
- 期望：如果没有主体、对象和上下文，则暂不输出。
- 理由：缺少可解释对象或主体。

样例三：短阻塞句也进入同一套机制。

- 输入：`导出又卡死。`
- 期望：如果相邻 chunk 或章节能指向 Aurora Board，可以作为 Aurora Board 阅读簇的主状态或支撑状态。

样例四：Aurora Board。

- Lin Qiao 的调试状态作为主状态。
- Nadia 提供的 renderer grouping rule 作为支撑状态。
- 两者进入同一个 Aurora Board 阅读簇。
- 不生成孤立 Nadia bundle。
- 不改变任何 state 的主体字段。

样例五：River import incident。

- `operations team`、`River import incident`、`River import team` 可以进入同一阅读簇。
- 阅读簇保留多个主体身份。
- 标题来自 River import incident、章节标题、共享事件或项目锚点。
- 不把整个簇归属给第一个主体。

样例六：防误合并。

- 同一文档里的 Docker 与 MCP 两个章节。
- 不同主体，不相邻，无共享实体或强锚点。
- 期望：不得归入同一阅读簇。

## Data Model Boundary

- 继续使用 output/profile 层只读投影。
- 不新增 SQLite schema。
- 不改 `states` / `state_evidence` 的持久化 contract。
- 不改 extraction JSON schema。
- 不让 aggregator 负责最终报告结构。
- 不把 LLM narrative 或 LLM review 结果持久化为状态事实。
- 不把输出层阅读簇归组反向写回 `subject_type` / `subject_key`。

## Non-goals

- 不在本阶段实现完整补全链路。
- 不接入 MCP / 联网搜索。
- 不把 retrieval candidate 当成确认事实。
- 不新增持久化 `context_bundles` / `context_bundle_evidence`。
- 不新增主体注册表。
- 不做正式关系持久化。
- 不把 `relation_candidates` 当成正式 `relations`。
- 不设置输出数量阈值。
- 不重新设计置信度语义。
- 不把 `needs_context` 渲染成正式 Markdown 章节。
- 不把上下文聚合下沉到 extractor。
- 不把 LLM 作为默认输出依赖。

## Long-Term Planning

- 先观察无数量阈值的真实输出分布，再决定 max bundle、max item、排序、拆分和省略策略。
- 若短语用状态 / 需补全条目持续有价值，再评估 profile 级 `needs_context` 持久化或诊断报告。
- 若本地上下文不足，再评估白名单补充材料的显式目录、准入和隐私规则。
- retrieval / MCP / 联网搜索只作为后续版本补全路径，必须先解决隐私、成本、可重复测试和事实确认边界。
- 只有当规则稳定后，才评估持久化 `context_bundles` / `context_bundle_evidence`。
- 长期仍保持 extractor 只产生 chunk 级观察，profile/output 负责阅读视图。

## Acceptance Criteria

- 不再使用“低信息评价”作为正式内部分类。
- 短句不会因为短小被降级。
- 短评价、短阻塞、短决策、短计划使用同一套输出角色审查。
- 单状态是否输出，由主体、对象、关系、证据链、上下文共同决定。
- 多主体上下文通过阅读簇归组，不改变 state 的 `subject_type` / `subject_key`。
- Aurora Board 能形成一个主状态 + 支撑状态的阅读簇。
- River import incident 能形成一个多主体阅读簇。
- 不同文档不误合并。
- 同文档但不同章节、无共享对象、无事件线索、无强锚点的状态不误合并。
- `status.md` 中不出现固定语义小节标题：`##### 当前目标`、`##### 进展`、`##### 问题`、`##### 下一步`、`##### 相关线索`。
- `status.md` 中不出现 `summary：detail` 形态；例如不得输出 `高度认可WhisperDesktop：WhisperDesktop，伟大。`。
- bundle summary 不使用 `主要涉及：` 或 `核心信息是：` 罗列子条目。
- 弱标题如 `工具：` 不作为正式主题标题；必须替换为可靠强锚点、文档/section 推断标题，或省略该 candidate。
- 正式 Markdown 不显示 confidence、内部 state_id、omitted reason、诊断字段或硬分类小节。
- `needs_context` 仍只作为内部诊断，不渲染成正式章节。
- schema、prompt、aggregator 无改动。
- 所有新增 dataclass 字段和关键函数必须有中文注释解释含义。
- `python -m unittest tests.test_output_layer` 覆盖平铺渲染、summary 非拼接、子条目无 summary 标签、弱标题过滤、输出角色、单状态可读性审查、阅读簇归组和诊断。

## Validation

最小验证：

```bash
ruff check .
python -m unittest tests.test_output_layer
python -m unittest tests.test_aggregator
python -m unittest tests.test_input_layer
python -m tests.test_extraction_schema
python main.py --help
```

如实际生成输出，再运行：

```bash
python main.py --skip-extraction
python main.py --stats
```

当前仓库的基础质量门禁是 Ruff 和 no-API 测试子集，不应声称已有完整 typecheck 或完整业务正确性证明。

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
