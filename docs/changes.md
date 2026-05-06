# 变更与决策
>本文档应当按照日期倒序来写，也即最新日期在前。


## 2026-05-06

### 决策

测试代码统一迁移到 `tests/` 目录，根目录不再直接放置 `test_*.py` 测试模块。

- Decision:
  - 所有 Python 测试与诊断测试脚本移动到 `tests/`
  - 当前验证命令改为模块路径，例如 `python -m unittest tests.test_output_layer` 与 `python -m tests.test_extraction_schema`
  - `test_config.bat` 改为调用 `python -m tests.test_config`
  - 清理确认无内容的 0 字节 Markdown 占位文件；空的 `input_layer_test_*` 临时目录因 ACL 拒绝删除，先加入 `.gitignore`
- Why:
  - 根目录测试文件和临时目录会稀释仓库入口，恢复工作时也更难区分长期文档、运行产物和测试代码
  - 测试代码集中到 `tests/` 后，验证命令和路径引用更稳定
  - 空 Markdown 占位文件没有内容来源，容易被误认为待恢复的活跃文档
- Implemented:
  - 测试模块路径更新到 retained docs、局部 `AGENTS.md`、当前 active spec/plan 和辅助脚本
  - 移动后测试里需要仓库根目录的路径改为从 `Path(__file__).resolve().parents[1]` 推导
  - 测试临时数据库和日志默认落在 `tests/data/` 下，不再混用运行时 `data/`
  - `input_layer_test_*` 空目录仍在本地文件系统中，但已被 `.gitignore` 屏蔽，不再影响 Git 状态
- Alternatives rejected:
  - 继续把测试模块留在根目录
  - 使用旧的根目录测试命令作为主要验证入口
  - 保留空 Markdown 文件等待人工猜测其用途
- Risk / debt accepted:
  - `docs/archive/` 中的旧测试路径仍保留为历史语境，不作为当前命令事实源
  - `tests/test_config.py` 仍是可选诊断脚本，不纳入常规验证路径
  - `input_layer_test_*` 空目录需要人工或系统权限层面清理，当前变更不强行修改目录所有权
- Follow-up:
  - 后续新增测试默认放入 `tests/`
  - 如果测试命令继续变化，优先更新 `docs/testing.md`

### 决策

在现有 retained docs / active spec-plan / archive 工作流上增加轻量恢复与中断协议，而不是新增独立项目管理层。

- Decision:
  - `AGENTS.md` 新增 `Resume Protocol`，规定恢复工作时从 retained docs 开始，而不是从 `docs/archive/` 或旧文件名推断当前状态
  - `docs/plans/_template.md` 新增可选 `If interrupted` 区块，只在单次执行无法完成时记录最小恢复信息
  - 新增 `docs/archive/INDEX.md`，用短表格标注可由现有文档支持的归档 spec/plan supersession、替代项、原因和不可盲用内容
- Why:
  - 当前仓库已经规定 retained docs 是活跃事实源，archive 只是历史上下文，但恢复中断任务时仍容易从旧设计分支或历史文件名误判当前状态
  - plan 应保持有边界的执行单元；中断记录只应帮助下一位贡献者续上上下文，不应把 active plan 变成长期状态看板
  - archive 需要一个小入口说明“为什么这些旧 pair 不再活跃”，避免贡献者重开已经被取代的方案
- Implemented:
  - 恢复阅读顺序固定为：`AGENTS.md`、最新相关 `docs/changes.md`、当前 active spec、当前 active plan，最后才按需查 archive
  - 中断计划模板记录 `Last completed step`、`Next step`、`Known blocker`、`Do not restart from` 和 `Relevant files to inspect next`
  - archive index 明确历史文档不可作为当前任务状态来源，并对无法从现有 docs 可靠支持的语义保持保守
- Alternatives rejected:
  - 新增大型 `RESUME.md`
  - 把 active plan 改成持续维护的状态 dashboard
  - 继续只靠文件名、目录位置或提交历史判断当前任务状态
  - 重写旧归档文档来补齐所有历史原因
- Risk / debt accepted:
  - archive index 只记录现有文档能支持的 supersession 线索，不尝试重建完整历史
  - 后续如果归档新 spec/plan，仍需要在同一变更中更新 `docs/changes.md`，并按需更新 archive index
  - 若旧 archive 条目的替代关系缺少可靠文档依据，应标为 `需要人类补充`，而不是猜测
- Follow-up:
  - 后续新增或归档 active spec/plan 时，同步维护 `docs/changes.md` 和必要的 `docs/archive/INDEX.md` 行
  - Durable decisions/results 继续写入 `docs/changes.md`，不要只留在 interrupted plan 中

## 2026-05-05

### 决策

下一阶段从 `contextual_bundle_narrative` 切换到 `contextual_bundle_reading_view`：继续保留主体 / 主题 bundle 方向，但修正正式 Markdown 的阅读形态，避免硬分类小节、弱标题和 `summary：detail` 式子条目。

- Why:
  - 最新输出已经能形成主题 bundle，但 `进展`、`问题`、`下一步`、`相关线索` 等硬分类会把同一上下文切碎，读者仍要自己拼回事件整体
  - 子条目仍可能渲染 `summary：detail`，例如 `高度认可WhisperDesktop：WhisperDesktop，伟大。`，说明 state summary 仍泄漏成正式条目标签
  - 规则 bundle summary 可能退化为 details 的拼接或枚举，不能提供真正的上下文入口
  - 弱标题如 `工具：` 会把低信息 state 包装成看似正式的主题
- Decision:
  - 新增 `docs/specs/contextual_bundle_reading_view.md` 与 `docs/plans/contextual_bundle_reading_view.md` 作为当前活跃 spec/plan
  - 已实现的 `contextual_bundle_narrative` 文档归档到 `docs/archive/specs/contextual_bundle_narrative.md` 与 `docs/archive/plans/contextual_bundle_narrative.md`
  - 正式 `status.md` 下一阶段不再渲染固定语义小节标题；kind / section / subtype 只保留为内部排序、诊断或 LLM 校验信息
  - 每个正式主题 bundle 只保留一个 bundle-level summary；summary 不得只是子条目 summary/detail 的拼接或 `主要涉及：...` 式枚举
  - 子条目优先渲染 detail / evidence 支撑的事实句，不再使用 state summary 作为标签或前缀
  - 低信息评价类 state 不得独立构成正式 bundle；能支撑工具选择或偏好上下文时吸收，否则进入 omitted diagnostics
  - 继续保持 `needs_context` 不进入正式 Markdown，且暂不设置输出数量阈值
- Implemented:
  - `layers/output_layer.py` 的正式 Markdown 渲染改为主题 summary 后直接平铺事实句，不再显示固定语义小节标题
  - 规则 summary 改为上下文说明，不再使用 `主要涉及：` / `核心信息是：` 枚举子条目
  - 子条目优先使用 detail / evidence，不再拼接 `summary：detail`
  - 弱标题会回退到强锚点、evidence、文档或主体线索；`工具：` 等泛化标签不作为正式主题标题
  - 孤立低信息评价类 state 进入 omitted diagnostics；有工具比较等上下文时可作为平铺事实句被吸收
  - fake LLM 路径继续可用，但 renderer 不把 LLM kind 渲染成可见小节；空 summary、非法 source id 等仍回退 rule
  - `tests/test_output_layer.py` 覆盖平铺渲染、summary 非拼接、弱标题清洗、低信息评价省略/吸收和 LLM 回退
- Alternatives rejected:
  - 继续只调小节分类或设置输出数量阈值
  - 把 `needs_context` 渲染成正式章节来解释缺口
  - 允许子条目继续以 `summary：detail` 形态出现
  - 为了 summary 完整感硬补无法验证的背景
- Follow-up:
  - 后续实现先跑 `python -m unittest tests.test_output_layer`
  - 实际生成输出后再观察 bundle 数量、每个 bundle 的 state 数、合并依据、未归组原因、弱标题和低信息评价类省略情况

## 2026-05-04

### 决策

输出从 `ContextBundle` state 清单升级为主体 / 主题 narrative 报告；`contextual_bundle_narrative` 成为当前活跃 spec/plan。

- Why:
  - 最新 `status.md` 已有主体和上下文 bundle，但仍把小 state 作为 `summary + detail + confidence` 条目渲染，读者看到的仍是碎片清单
  - 主体分类有价值，但主体下面还需要主题层，才能表达一个人或项目围绕哪件事形成了什么进展、问题和下一步
  - 置信度目前没有明确读者语义，应先从正式 Markdown 移除，保留为内部诊断 / 后续设计债务
  - LLM 可以帮助主题内语义分类和叙事整理，但必须限制在 output/profile 层，并保留规则回退
- Decision:
  - 新增 `docs/specs/contextual_bundle_narrative.md` 与 `docs/plans/contextual_bundle_narrative.md` 作为当前活跃 spec/plan
  - 已实现的 discovery 阶段文档保留在 `docs/archive/specs/contextual_bundle_discovery.md` 与 `docs/archive/plans/contextual_bundle_discovery.md`
  - 输出层新增只读 `CandidateTopicBundle` / `BundleNarrative` narrative 投影，不新增 SQLite schema
  - 正式 Markdown 按主体和主题输出，每个主题有标题、summary 和语义栏目
  - 正式 Markdown 不再显示 `置信度:`，也不再渲染旧式 state title/detail 双层条目
  - 新增 `OUTPUT_NARRATIVE_MODE=rule|llm|auto`；默认 `rule`，`llm` / `auto` 失败后回退到规则 narrative
- Implemented:
  - `layers/output_layer.py` 从 `ContextBundleSelection` 生成候选主题 bundle 和 narrative
  - 默认规则 narrative 能生成主题标题、bundle summary、栏目事实句和诊断信息
  - 可选 LLM narrative classifier 支持 fake client 测试，并校验 JSON、栏目 kind 与 source state ids
  - `generate_output()` 返回 topic bundle 数、narrative mode 和 narrative diagnostics
  - `tests/test_output_layer.py` 覆盖主题拆分、无置信度、无旧式条目、fake LLM 成功和 LLM 非法 source id 回退
- Alternatives rejected:
  - 继续只清理单条 state 渲染
  - 让 LLM 直接从全库生成完整报告
  - 把 narrative 结果持久化为正式状态事实
  - 在本阶段过滤所有低信息条目
- Risk / debt accepted:
  - 规则 narrative 的摘要仍偏保守，主要用于无 API 回退和可重复测试
  - 低信息条目暂不全面过滤，先观察主题 narrative 后的真实输出
  - 置信度语义、跨文档主题合并、LLM 摘要质量和成本/隐私策略仍需后续设计
- Follow-up:
  - 观察生成的 narrative 输出，决定是否引入显著性排序、bundle 拆分阈值或低信息条目命运
  - 后续若要跨文档主题合并，应先定义更强确认规则和独立 spec

### 决策

后续输出单位从碎片 `state` 条目转向证据驱动的上下文 `ContextBundle`，先在 output/profile 层做只读投影，而不是新增持久化 schema 或继续美化单条状态。

- Why:
  - 当前 `status.md` 把许多离开上下文就失效的碎片状态当作独立状态输出，容易制造信息噪音
  - 给每条碎片状态单独补背景会造成重复、臃肿，并诱导系统硬补不确定上下文
  - 过滤掉上下文不足的条目也不够好；它们应先尝试沿 `state_evidence` 回到 source chunk / document 归入上下文整体
  - 现有 `states`、`state_evidence`、`retrieval_candidates` 与 `OutputProfile` 已支持先在输出层验证只读上下文投影
- Decision:
  - 新增 `docs/specs/contextual_output_bundles.md` 和 `docs/plans/contextual_output_bundles.md` 作为当时的 v1 设计文档；当前已归档到 `docs/archive/specs/contextual_output_bundles.md` 与 `docs/archive/plans/contextual_output_bundles.md`
  - v1 的 `ContextBundle` 是 output layer 内存结构，不新增 SQLite 表
  - bundle 构造优先使用同文档、相邻 chunk、同 section、共享主体和 canonical/display 语义线索
  - `status.md` 后续主输出应从分类清单转为上下文报告，推荐小节包括当前目标、进展、问题、下一步和相关线索
  - 无法归入可靠上下文的 state 降级为待澄清或暂不展示，不再混入主清单
- Implemented:
  - `layers/output_layer.py` 新增 `ContextBundle` / `ContextBundleSelection` 只读投影结构
  - 输出层从 active states 沿 `state_evidence -> chunks -> documents` 回查证据，并按同文档、主体线索、相邻 chunk 与 section 做保守归组
  - `generate_output()` 现在生成以上下文报告为主体的 `status.md`，孤立或缺少 evidence 的 state 进入待澄清区域
  - `tests/test_output_layer.py` 覆盖相邻 chunk 归组、跨文档不误合并、缺失 evidence 降级和默认输出入口
- Alternatives rejected:
  - 只做单条状态美化
  - 为每条状态硬补背景
  - 第一步直接新增 `context_bundles` 等重型持久化 schema
  - 让 extractor 承担上下文聚合责任
  - 把未持久化的 `relation_candidates` 当作正式上下文关系使用
- Risk / debt accepted:
  - v1 的 bundle 归组会依赖保守启发式，短期聚合质量有限
  - 无法可靠归组的状态可能暂时不展示，需要后续 `needs_context` 策略继续细化
  - `retrieval_candidates` 只能作为待确认线索，不代表已确认实体或背景
- Follow-up:
  - v1 先验证只读 bundle 输出单位是否正确
  - v2 再引入 profile 级完整性提示和更明确的 `needs_context` 输出策略
  - v3 评估持久化 `context_bundles` / `context_bundle_evidence`
  - v4 在隐私、成本、可重复测试都可接受时，再评估 LLM 辅助 bundle 标题和摘要生成

### 决策

下一阶段先强化不规范文档的上下文发现流程，而不是设置输出数量阈值或把 `needs_context` 渲染进 `status.md`。

- Why:
  - 文档开头和结尾可能讨论同一事件，只靠相邻 chunk 会漏掉远距离上下文
  - 上下文不足的 state 应先使用当前可用的本地上下文，而不是直接进入正式输出
  - `待澄清` 章节会把内部诊断噪音暴露给最终读者
  - 尚未观察真实 bundle 分布前，提前设置 max bundle / max item 阈值会过早优化
- Decision:
  - 新增 `docs/specs/contextual_bundle_discovery.md` 和 `docs/plans/contextual_bundle_discovery.md` 作为下一阶段计划，不覆盖已实现的 `contextual_output_bundles` v1 文档
  - `status.md` 只输出已形成可靠上下文的 bundle
  - `needs_context` 保持为内部诊断 / 补全流程，不作为正式 Markdown 章节
  - bundle 归组分为局部归组和同文档远距离强锚点回收
  - 对上下文不足的 state，本阶段先使用 source evidence chunk、邻近 chunk、同文档其他 chunk
  - 白名单补充材料只在显式可用时接入；完整补全链路记录为后续版本方向
  - 暂不设置输出数量阈值，先记录 bundle 数量、state 分布、合并依据、未归组数量和原因
- Implemented:
  - `layers/output_layer.py` 将 `needs_context` 从正式 Markdown 渲染中移除，只保留为返回值和诊断数据
  - bundle 构造先做局部相邻 / shared section 归组，再用同文档强锚点回收远距离候选组
  - 单条 state 可通过邻近 chunk 或同文档强锚点 chunk 补足本地上下文形成可靠 bundle
  - 诊断返回 bundle 数、每个 bundle 的 state 数、合并依据、未归组数量和原因，以及疑似过大 bundle
  - `tests/test_output_layer.py` 覆盖远距离强锚点合并、远距离无锚点不误合并、邻近 chunk 补全和 `needs_context` 不渲染
- Alternatives rejected:
  - 继续只依赖相邻 chunk 归组
  - 在 `status.md` 中正式渲染 `待澄清`
  - 未观察真实分布前先设置输出数量阈值
  - 要求本阶段一次走完整补全链路
  - 在本阶段引入 retrieval / MCP / 联网搜索作为默认补全路径
- Risk / debt accepted:
  - 远距离强锚点回收仍可能出现误合并，需要诊断信息辅助观察
  - 当前可用本地路径可能仍无法解决所有碎片状态，失败项会暂不输出
  - 白名单补充材料和外部补全的目录、准入、隐私与可靠性策略留到后续版本评估
- Follow-up:
  - 实现后先观察真实 bundle 分布，再决定 max bundle、max item、bundle 拆分或 needs_context 持久化策略
  - 后续版本再评估完整补全链路：白名单补充材料、retrieval、MCP、联网搜索

### 决策

`docs/specs/` 与 `docs/plans/` 只保留当前活跃任务和模板；已被取代的 spec/plan 移入 `docs/archive/specs/` 与 `docs/archive/plans/`。

- Why:
  - 多个阶段 spec/plan 同时留在活跃目录，会让实现对话难以判断当前任务边界
  - `contextual_bundle_discovery` 当时成为唯一活跃 spec/plan，旧阶段文档应保留历史价值但退出活跃事实源
  - 归档机制能避免“已实现 v1”“下一阶段计划”和历史阶段设计互相覆盖
- Decision:
  - 当时活跃 spec/plan 为 `docs/specs/contextual_bundle_discovery.md` 与 `docs/plans/contextual_bundle_discovery.md`；当前已由 `contextual_bundle_narrative` 取代
  - `docs/specs/_template.md` 与 `docs/plans/_template.md` 继续保留为模板
  - 其他 spec/plan 迁移到 `docs/archive/specs/` 与 `docs/archive/plans/`
  - 新阶段若取代当前活跃 spec/plan，应在同一变更中归档旧 pair，并在本文件记录 supersession
- Alternatives rejected:
  - 继续让所有历史 spec/plan 留在活跃目录
  - 删除历史 spec/plan
  - 只靠文件名或提交历史判断当前任务
- Risk / debt accepted:
  - 历史 `docs/changes.md` 条目可能仍引用当时的旧路径；新决策应优先引用 archive 路径或当前活跃路径
- Follow-up:
  - 后续新增 spec/plan 时同步更新 `AGENTS.md`、`docs/architecture.md` 和必要的入口文档

## 2026-05-03

### 决策

第五阶段先只落地 `retrieval_candidates` 的 pending 持久化命运；`relation_candidates` 继续保留在 extraction JSON 中，不直接写入正式 `relations`。

- Why:
  - `retrieval_candidates` 已有数据库候选池，适合先作为 pending 裁决对象持久化
  - `RelationCandidate` 的 source/target 仍是自然语言文本，缺少稳定 id，直接写入 `relations` 会制造不可靠正式关系
  - 本阶段目标是“持久化命运”的最小切片，不扩展成关系图谱、检索系统、embedding、联网搜索或外部知识库
- Implemented:
  - `layers/aggregator.py` 在聚合 extraction 时会把 `retrieval_candidates` 写入 `retrieval_candidates` 表
  - 候选按 `surface_form` 与 source chunk 维持幂等，重复聚合不会重复增加同一 chunk 证据
  - 空白 `surface_form` 会被跳过，`priority` 被限制在 0 到 10
  - 聚合结果统计新增 retrieval candidate 处理计数
  - `tests/test_aggregator.py` 覆盖 pending 写入、跳过空白项与重复聚合幂等
- Alternatives rejected:
  - 继续完全忽略 `retrieval_candidates`
  - 直接把 `relation_candidates` 写入正式 `relations`
  - 在当前阶段引入实体 registry、关系图谱、搜索或 embedding
- Risk / debt accepted:
  - `retrieval_candidates` 仍只是 pending 候选池，不代表已确认实体或检索结果
  - `relation_candidates` 仍未进入 pending 持久化链路，也不会直接升格为正式关系
- Follow-up:
  - 后续若要处理 `relation_candidates`，应先定义 pending 关系候选层或等价裁决记录，再评估正式 relation 晋升规则

### 决策

第六阶段先落地 `default` 输出 profile 兼容壳层，而不是同时实现 CLI profile 入口、真实场景筛选或多文件 profile 矩阵。

- Why:
  - `state_output_profiles` 计划要求先让输出层入口 profile-aware，同时保持现有 `output/status.md` 兼容输出
  - 当前统一状态底座仍处于渐进阶段，真实 personal/team/project profile 还不应抢跑筛选策略
  - 先用唯一 `default` profile 包装现有 `OUTPUT_CONFIG`，可以把输出层从硬编码入口迁移到可扩展结构而不改变用户可见结果
- Implemented:
  - 在 `layers/output_layer.py` 新增 `OutputProfile`、`DEFAULT_PROFILE_NAME` 与 profile registry，目前只注册 `default`
  - `generate_output()` 保持无参兼容，同时支持 `generate_output(profile_name="default")`
  - `select_states_for_output()` 与 `generate_status_document()` 改为消费当前 profile 的配置
  - 新增 `tests/test_output_layer.py` 验证无参 default、显式 default 与未知 profile 错误
  - `docs/architecture.md` 和 `docs/testing.md` 已同步输出层职责与测试命令
- Alternatives rejected:
  - 立刻加入 `--profile` CLI 参数
  - 一次性实现 personal/team/project 等真实 profile 策略
  - 一次运行生成多套 profile 输出文件
- Risk / debt accepted:
  - 当前只有 `default` profile，profile 机制短期主要是结构迁移，用户可见输出基本不变
  - profile 级显著性、完整性提示和真实场景筛选仍依赖后续主体归属与统一状态底座继续成熟
- Follow-up:
  - 下一步再按计划评估单 profile 选择入口，例如 `--profile default`
  - 在有可靠完成度信号后，再补 profile 级完整性提示和显著性策略

## 2026-05-02

### 决策

`relation_candidates` / `retrieval_candidates` 后续采用“候选暂存 + 裁决层”方案，而不是默认直接升格为正式关系或检索结果。

- Why:
  - 抽取 schema 与数据库已经存在关系/检索候选相关结构，但主链路尚未消费这些字段
  - `RelationCandidate` 的 source/target 仍是自然语言文本，不能可靠满足正式 `relations` 所需的 source/target id
  - 检索候选可以先进入 pending 候选池，但必须保证重复聚合幂等
- Alternatives rejected:
  - 继续完全忽略 relation/retrieval candidates，让它们只留在 `extraction_json` 中
  - 直接把自由文本 relation candidates 写入正式 `relations`
  - 在当前阶段引入完整关系图谱、外部检索或实体 registry
- Risk / debt accepted:
  - relation candidates 需要新增 pending 持久化层或等价候选观察记录
  - 正式 relation 晋升仍依赖后续主体归属与统一状态底座成熟
- Follow-up:
  - 历史设计见 `docs/archive/specs/relation_retrieval_candidates.md` 与 `docs/archive/plans/relation_retrieval_candidates.md`

### 决策

场景化输出采用“单 profile 选择机制 + profile-aware 输出策略”，并先以 `default` profile 兼容现有 `output/status.md`。

- Why:
  - 当前输出层仍是固定 `status.md`、固定分组和固定 Markdown 骨架
  - profile 机制应支持个人复盘、团队同步、项目推进等场景，但不应一次性生成多文件矩阵
  - 在主体归属和统一状态底座成熟前，真实场景化策略只能渐进实现
- Alternatives rejected:
  - 继续把 `output/status.md` 当作唯一正式目标
  - 一次运行生成个人、团队、项目等多套并行输出文件
  - 在缺少 subject/canonical 底座时抢跑完整场景筛选
- Risk / debt accepted:
  - 初始 default profile 壳层短期内主要是结构迁移，用户可见差异有限
  - personal/team/project profile 的真实筛选依赖后续主体归属与统一状态底座
- Follow-up:
  - 历史设计见 `docs/archive/specs/state_output_profiles.md` 与 `docs/archive/plans/state_output_profiles.md`

### 决策

`documents.status = 'processed'` 只表示该文档当前所有 chunk 都已有对应 extraction；pending 队列以 chunk 是否缺少 extraction 为准，而不是完全信任文档级 status。

- Why:
  - 旧逻辑只要同一文档中任一 chunk 抽取成功，就会把整个文档标为 `processed`
  - 这会让同文档中抽取失败的 chunk 在后续运行中被文档级 status 排除出 pending 队列
- Alternatives rejected:
  - 立刻设计完整 chunk 状态机、失败表、重试次数和错误持久化
  - 要求用户通过 `python main.py --init` 重建数据库来恢复队列
- Risk / debt accepted:
  - 失败原因、重试次数和最终放弃策略仍只存在于日志/运行行为中，没有正式持久化状态机
  - `documents.status` 仍是粗粒度完成提示，不是完整任务调度状态
- Follow-up:
  - 后续若需要完整失败恢复，应补独立 spec，并评估 chunk 级状态、错误持久化和重试上限

### 决策

front matter 与元数据表格继续不进入正文 chunk；当前只从这些非正文块中提炼标题、作者和文档时间，作为 LLM 抽取的轻量文档上下文。

- Why:
  - 第一阶段需要把非正文块从 state extraction 正文中分离，同时保留少量有价值的文档级解释线索
  - 现有 extraction schema 已支持 `document_title` 与 `document_time`，prompt 也已有文档上下文区
- Alternatives rejected:
  - 把完整 front matter / 元数据表格作为普通 chunk 送入抽取
  - 立即新增 context-only 块表或完整上下文持久化通道
- Risk / debt accepted:
  - 作者字段目前只是抽取上下文提示，不是正式主体归属
  - 非正文 context-only 块仍没有完整存储、检索或证据模型
- Follow-up:
  - 若后续需要消费更多非正文上下文，应先定义最小字段与持久化命运，再扩展输入层

### 决策

extraction JSON 开始支持 `document_mode` 以及 state candidate 级 `subject_type` / `subject_key`；aggregator 对显式 `unknown` 主体或声明了主体类型但缺少 `subject_key` 的候选做最小保守拒绝。

- Why:
  - 第二阶段需要让 prompt 提供主体线索，同时让 aggregator 保留最终准入裁决
  - 旧数据没有主体字段，仍需兼容已有聚合链路
- Alternatives rejected:
  - 立刻扩展 `states` schema 或新增主体 registry
  - 把文档作者机械写成所有候选的状态主体
- Risk / debt accepted:
  - 主体信息暂不持久化到 `states`，因此还不是完整 subject-aware state identity
  - `document_mode` 只是 extraction context 中的 prior，不替代候选级主体归属
- Follow-up:
  - 后续统一状态底座阶段应评估 subject-aware state identity 与 schema 迁移边界

### 决策

`states` 表以 additive 字段保存 `subject_type` / `subject_key` / `canonical_summary` / `display_summary`；aggregator 按 `subject_type` / `subject_key` / category / subtype / `canonical_summary` 合并 state，`summary` 暂时保留为输出兼容字段。

- Why:
  - 第三阶段统一状态底座需要把语义身份和展示文案拆开，避免 raw summary 改写直接制造新 state
  - 主体归属已经进入候选准入，下一步需要把主体维度纳入 state identity，而不是只停留在 extraction JSON
- Alternatives rejected:
  - 继续只用 category / subtype / summary 做去重键
  - 立刻引入主体 registry、层级 state、关系图谱或完整迁移框架
- Risk / debt accepted:
  - 这是 additive schema 升级，启动时只补缺失列，不重建 `data/state.db`
  - 历史 state 没有主体和 canonical 信息；旧行通过 `COALESCE(canonical_summary, summary)` 保持兼容，但不会自动反推主体
  - `summary` 仍作为当前输出兼容字段存在，后续 profile 阶段再收敛输出消费方式
- Follow-up:
  - 后续输出 profile 阶段应优先消费 `display_summary`，并评估是否需要把 `summary` 降级为兼容字段


## 2026-04-17

### 决策

输入层正式改为显式样本纳入规则，而不是扫描 `input_docs/` 下全部 `*.md`。

- Why:
  - 第一阶段输出质量要求需要把规则文档、测试夹具和正式样本拆开
  - 仅靠“文件恰好没有被抽取”不足以防止污染主链路
- Alternatives rejected:
  - 继续扫描全部 `*.md`，把过滤责任留给后续抽取或聚合
  - 仅靠人工约定，不在代码里落下显式规则
- Risk / debt accepted:
  - 当前规则仍是最小集合，主要覆盖 `AGENTS.md`、`test_*.md` 和夹具目录
  - 未来若出现新的控制文件命名约定，仍需补充规则
- Follow-up:
  - 若 `input_docs/` 的样本组织方式发生变化，同步更新 `layers/input_layer.py`、`docs/architecture.md` 和相关 spec

### 决策

输入层 chunking 只把作者正文叙述块送入抽取链路；front matter、元数据表格、引用块、结构化转储、媒体占位与明显教程说明默认不进入正文抽取。

- Why:
  - 现有抽取层仍把 chunk 视为正文来源，若不在输入层先分流，非作者内容会继续污染 `state_candidates`
  - 这与 `state_output_quality` 第一阶段 spec 的边界一致
- Alternatives rejected:
  - 保留所有块为普通 chunk，再指望抽取 prompt 或聚合层兜底
  - 为此引入更重的 schema 或新服务
- Risk / debt accepted:
  - 外部资料/教程说明的识别目前仍是轻量启发式，不是完整语义判别
  - “仅作为上下文”的块还没有单独持久化通道
- Follow-up:
  - 若后续需要把上下文块正式接入抽取上下文，优先评估在现有 schema 下的最小扩展

### 决策

`documents.content_hash` 的计算现在包含输入处理版本，用于在扫描/切块规则变化时强制重处理既有文档，而不依赖 `--init`。

- Why:
  - 输入边界和切块语义变化后，仅比较原始内容 hash 无法触发老文档重切分
  - 破坏性重建数据库不应成为默认升级路径
- Alternatives rejected:
  - 要求用户手动运行 `python main.py --init`
  - 在现有 schema 上额外引入单独的 chunking 版本字段
- Risk / debt accepted:
  - `content_hash` 现在更接近“输入处理指纹”，不再是纯内容 hash
- Follow-up:
  - 后续若再次调整输入边界或 chunk 语义，需要显式更新输入处理版本并记录到本文件


## 2026-04-15

### 决策

建立最小 `docs/` 文档层：架构事实、spec 模板、plan 模板、决策日志。

- Why:
  - 旧文档体系更偏 onboarding，缺少短小、可维护、可持续更新的工程文档层
- Alternatives rejected:
  - 继续只靠 `README.md`、`CLAUDE.md`、`PLAN.md`
  - 一次性引入更重的流程框架
- Risk / debt accepted:
  - 新文档层是在旧文档之上叠加出来的，后续仍需要收敛
- Follow-up:
  - 只在长期规则、结构、命令、决策变更时更新这些文档

### 决策

活跃文档体系收敛为：`AGENTS.md`、`README.md`、`docs/architecture.md`、`docs/testing.md`、`docs/specs/_template.md`、`docs/plans/_template.md`、`docs/changes.md`、`.github/CONTRIBUTING.md`、`.github/EXTRACTION_JSON_SCHEMA.md`。

- Why:
  - 仓库原先存在多个入口、多个快速开始、多个架构说明、多个历史说明，职责重叠严重
- Alternatives rejected:
  - 同时保留多个 quickstart/setup/navigation 文档
  - 同时保留 `AGENTS.md` 与 `CLAUDE.md` 作为活跃长期规则/架构入口
- Risk / debt accepted:
  - 一部分历史上下文会被压缩成更短的决策记录
- Follow-up:
  - 历史计划和旧说明移入 `docs/archive/`

### 决策

保留文档主线默认按 Conda 路径说明。

- Why:
  - 当前仓库的脚本、旧文档和既有使用路径都主要围绕 `conda activate markdown_tracker`
- Alternatives rejected:
  - 在活跃入口文档里同时维护多套等重环境说明
- Risk / debt accepted:
  - 代码本身并不强依赖 Conda，但主文档会优先推荐 Conda
- Follow-up:
  - 如未来正式支持其他环境路径，再补充到 README 而不是重新膨胀 quickstart 文档

### 决策

活跃文档暂不把多 LLM 提供商作为主线能力说明。

- Why:
  - 当前用户决策是不把多 LLM 作为近期主线
  - 继续把 provider 指南放在活跃文档里会扩大维护面
- Alternatives rejected:
  - 保留多份 provider 专属说明作为活跃文档
- Risk / debt accepted:
  - 代码层仍保留 OpenAI-compatible 配置能力，但活跃文档不会展开说明
- Follow-up:
  - 相关历史文档归档；如未来重新主推，再从归档中恢复或重写

### 决策

根目录 `PLAN.md` 退出活跃入口，归档为历史参考；后续任务计划使用 `docs/plans/*.md`。

- Why:
  - 仓库不应同时保留两个长期“计划入口”
  - 现有 `PLAN.md` 仍有历史背景价值，但不适合作为当前正式流程入口
- Alternatives rejected:
  - 同时保留根目录 `PLAN.md` 和 `docs/plans/` 作为活跃计划体系
- Risk / debt accepted:
  - 仍可能需要偶尔参考旧计划中的背景信息
- Follow-up:
  - 将 `PLAN.md` 迁移到 `docs/archive/`，仅作历史上下文使用

### 决策

`chunks` 只保存正文 chunk；文档级 metadata 保留在 `documents`。

- Why:
  - 这与当前 schema 和输入层实现一致
- Alternatives rejected:
  - 在 `chunks` 中重复存放文档级 metadata
- Risk / debt accepted:
  - offset 和 section 仍然是轻量启发式实现
- Follow-up:
  - 如果 chunk 语义变化，需要同步更新 schema、代码和架构文档

### 决策

`extractions` 通过 `extractor_type`、`model_name`、`prompt_version` 记录来源元数据。

- Why:
  - 单一版本字段无法清楚表达抽取来源
- Alternatives rejected:
  - 继续使用语义模糊的单字段版本号
- Risk / debt accepted:
  - prompt/schema 的权威来源仍分散在代码和文档中
- Follow-up:
  - 保持 `.github/EXTRACTION_JSON_SCHEMA.md` 与代码同步

### 决策

`state_evidence` 是当前 state 与 chunk/extraction 关系的表达方式。

- Why:
  - 多对多关系更适合关联表，而不是把多个 id 塞进 `states`
- Alternatives rejected:
  - 在 `states` 里保存 `source_chunk_ids` JSON
- Risk / debt accepted:
  - 证据模型先于完整聚合链路落地，当前还没有被主流程完全利用
- Follow-up:
  - 聚合逻辑接入后，应补充 state/evidence 的实际写入规则

### 决策

`state_candidates -> states` 的基础聚合责任放在 `layers/aggregator.py`，而不是回填到 `main.py`、`middle_layer.py` 或 `output_layer.py`。

- Why:
  - 聚合是主流程中的独立步骤，但仍应保持在当前三层结构约束内
  - 单独模块能把“候选规范化 + state/evidence 写入”与输入、存储、输出职责分开
- Alternatives rejected:
  - 直接把聚合逻辑堆回 `main.py`
  - 把聚合逻辑塞进 `output_layer.py`
  - 在 `middle_layer.py` 中继续堆叠更多 orchestration 代码
- Risk / debt accepted:
  - `layers/aggregator.py` 仍依赖 `layers.middle_layer` 提供的数据读写接口，层间耦合没有完全消失
  - subtype 规范化规则当前仍是最小启发式实现
- Follow-up:
  - 后续若修复失败 chunk 状态流转，应与聚合模块一起评估幂等性和孤儿 state 清理策略

### 决策

快速启动脚本保持 ASCII 输出。

- Why:
  - 历史上 Windows 控制台与 PowerShell 的编码/解析问题确实出现过
- Alternatives rejected:
  - 在活跃脚本里继续使用本地化非 ASCII 输出
- Risk / debt accepted:
  - 脚本输出不再本地化
- Follow-up:
  - 后续改脚本时优先保留 ASCII 安全性

### 决策

在高风险目录增加局部 `AGENTS.md`：`input_docs/`、`db/`、`layers/`、`layers/extractors/`、`data/`。

- Why:
  - 这些目录分别承载敏感输入、schema 与破坏性操作、层级边界、LLM 抽取耦合点、运行时数据，误操作成本明显高于普通目录
- Alternatives rejected:
  - 只依赖根目录 `AGENTS.md` 处理所有局部风险
- Risk / debt accepted:
  - 规则文件数量增加，但只放在高风险目录，且每份都保持短小
- Follow-up:
  - 仅在这些目录的长期约束变化时更新对应局部 `AGENTS.md`

### 决策

根目录长期文档入口保持为 `README.md` 和 `AGENTS.md`；贡献说明移到 `.github/CONTRIBUTING.md`，测试命令正典移到 `docs/testing.md`。

- Why:
  - 根目录只保留仓库入口和 agent 规则更清晰
  - `.github/CONTRIBUTING.md` 仍可被 GitHub 识别为贡献指南
  - 测试命令集中在一处，避免 `AGENTS.md`、贡献文档、架构文档各自维护一份命令清单
- Alternatives rejected:
  - 继续在多个活跃文档中重复维护测试命令
  - 继续把 `CONTRIBUTING.md` 和 `TESTING.md` 放在根目录
- Risk / debt accepted:
  - 某些历史归档文档仍会保留旧路径引用，只作为历史上下文
- Follow-up:
  - 后续若测试命令变化，优先更新 `docs/testing.md`，其余活跃文档只做链接或简短说明
