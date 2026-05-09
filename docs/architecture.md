# 架构事实

## 仓库用途

`Markdown State Tracker` 是一个本地原型：把 `input_docs/` 中的 Markdown 扫描、切分、存储到 SQLite，并生成 `output/status.md`。

当前主流程：

1. 扫描 Markdown 文档
2. 基于带输入处理版本的内容 hash 识别新增或修改
3. 结构分块、chunk 切分、来源映射并落库
4. 按需执行 LLM 抽取
5. 记录 `state_candidates -> state_candidate_supports` 准入结果，并将 accepted candidate 聚合进 `states/state_evidence`
6. 从数据库生成输出 Markdown

注意：基础聚合链路现已接入主流程，失败 chunk 可通过 pending 队列重新纳入，`retrieval_candidates` 也已进入 pending 候选池；但完整失败状态机、关系持久化、retrieval 裁决/完整生命周期仍未完成。

## 主要模块与职责

- [main.py](/D:/Apps/Python/lab/personal_prompt/main.py)
  - CLI 入口
  - 主流程编排
- [config.py](/D:/Apps/Python/lab/personal_prompt/config.py)
  - 路径常量
  - 导入时创建数据目录
- [app_logging.py](/D:/Apps/Python/lab/personal_prompt/app_logging.py)
  - 文件日志
  - `run_id`
  - 事件格式化
- [db/schema.py](/D:/Apps/Python/lab/personal_prompt/db/schema.py)
  - SQLite schema 和索引
- [db/connection.py](/D:/Apps/Python/lab/personal_prompt/db/connection.py)
  - 全局连接
  - 初始化和关闭
- [layers/input_layer.py](/D:/Apps/Python/lab/personal_prompt/layers/input_layer.py)
  - 扫描
  - 显式样本纳入规则（当前至少排除 `AGENTS.md`、`test_*.md` 与夹具目录）
  - 标题提取
  - 只从文档开头 front matter 提炼轻量文档上下文
  - 变更检测
  - 结构优先的 `SourceBlock` 分类：`front_matter`、`table_block`、`quote_material`、`structured_dump`、`media_placeholder`、`author_narrative`
  - `source_blocks`、`chunks`、`chunk_source_blocks` 落库
  - 从 `source_blocks.include_decision = context_only` 构造 chunk 级 `source_context_blocks`，写入 `extraction_json.context`
  - 普通正文默认 `author_narrative -> extract`；不再用 `external_material` 语义启发式按“你/建议/步骤/配置”等词排除正文
- [layers/middle_layer.py](/D:/Apps/Python/lab/personal_prompt/layers/middle_layer.py)
  - `ExtractionResult` 相关 dataclass
  - extractions / states / state_evidence / state_candidate_supports / retrieval_candidates / stats
  - chunk 级 pending 查询与文档完成标记
  - extraction JSON 可携带 `document_mode` 与候选级 `subject_type` / `subject_key`
  - `states` 以 additive 字段保存 `subject_type` / `subject_key` / `canonical_summary` / `display_summary`
- [layers/aggregator.py](/D:/Apps/Python/lab/personal_prompt/layers/aggregator.py)
  - 读取 `extractions`
  - 规范化 `state_candidates`
  - 对每个 `state_candidate` 写入 `state_candidate_supports` 准入记录
  - 对无效 candidate、显式 unknown 主体或缺少 subject_key 的主体候选做最小保守拒绝
  - 只接受在 `chunks.text` 中有基本正文支撑的候选；只被 `context_only` 材料支撑的候选记录为 `context_only_only` reject
  - 优先按 `subject_type` / `subject_key` / category / subtype / `canonical_summary` 归并 state
  - 将 `retrieval_candidates` 写入 pending 候选池，并按 source chunk 保持重复聚合幂等
  - accepted candidate 写入 `states` 与 `state_evidence`；rejected candidate 不写 state/evidence
- [layers/output_layer.py](/D:/Apps/Python/lab/personal_prompt/layers/output_layer.py)
  - 选择活跃状态
  - 通过当前唯一的 `default` 输出 profile 包装现有输出配置
  - 对每条 state 做 output-only `ReadingDecision` 审查，决定其在阅读视图中是 `standalone`、`supporting` 还是 `defer`
  - 在同文档内形成 output-only `ReadingCluster`，用相邻 chunk、共享章节、共享对象/事件线索、强锚点和主体—对象连接组织读者上下文
  - 多主体阅读簇保留全部 subject identities，但不改变任何 state 的 `subject_type` / `subject_key`
  - 通过 `state_evidence -> chunks -> documents` 构造只读 `ContextBundle` 输出投影
  - 使用局部相邻证据和同文档远距离强锚点回收发现上下文 bundle
  - 在 `ContextBundle` 之上构造只读 `CandidateTopicBundle` 与 `BundleNarrative` narrative 投影
  - 默认用规则回退生成主体 / 主题报告；显式设置 `OUTPUT_NARRATIVE_MODE=llm|auto` 时可尝试 LLM 叙事分类，失败后回退
  - 生成按主体和主题组织的 reading-view Markdown，不显示置信度、固定语义小节或旧式 `summary：detail` 事实句
  - 将缺少足够证据或上下文的状态保留为内部诊断，不渲染进正式 Markdown
  - 保存 `output/status.md` 兼容输出和输出快照
- 当前活跃 spec/plan：
  - [docs/specs/contextual_bundle_reading_view.md](/D:/Apps/Python/lab/personal_prompt/docs/specs/contextual_bundle_reading_view.md)
  - [docs/plans/contextual_bundle_reading_view.md](/D:/Apps/Python/lab/personal_prompt/docs/plans/contextual_bundle_reading_view.md)
- 归档规则：
  - `docs/specs/` 与 `docs/plans/` 只保留当前活跃任务和 `_template.md`
  - 已被取代的 spec/plan 移入 `docs/archive/specs/` 与 `docs/archive/plans/`
- [layers/extractors/config.py](/D:/Apps/Python/lab/personal_prompt/layers/extractors/config.py)
  - `.env` 读取
  - 抽取器配置
- [layers/extractors/prompts.py](/D:/Apps/Python/lab/personal_prompt/layers/extractors/prompts.py)
  - prompt 文本
  - JSON schema prompt contract
- [layers/extractors/rule_helper.py](/D:/Apps/Python/lab/personal_prompt/layers/extractors/rule_helper.py)
  - 预处理/后处理
- [layers/extractors/llm_extractor.py](/D:/Apps/Python/lab/personal_prompt/layers/extractors/llm_extractor.py)
  - LLM 调用
  - 重试
  - JSON 解析

## 入口

- CLI：
  - `python main.py`
  - `python main.py --skip-extraction`
  - `python main.py --stats`
  - `python main.py --init`
- 便捷脚本：
  - [quick_start.ps1](/D:/Apps/Python/lab/personal_prompt/quick_start.ps1)
  - [quick_start.bat](/D:/Apps/Python/lab/personal_prompt/quick_start.bat)
  - [test.sh](/D:/Apps/Python/lab/personal_prompt/test.sh)
- 测试命令事实源：
  - [docs/testing.md](/D:/Apps/Python/lab/personal_prompt/docs/testing.md)
- 最低质量门禁：
  - `ruff check .`
  - GitHub Actions workflow: `.github/workflows/ci.yml`
  - 当前没有默认 typecheck 命令

## 依赖方向

当前代码大体按这个方向组织：

`config -> app_logging -> db -> layers -> main`

具体耦合点：

- `main.py` 直接导入 `db`、`layers.input_layer`、`layers.middle_layer`、`layers.output_layer`
- `main.py` 直接导入 `layers.aggregator`
- 输入层/中间层/输出层都直接依赖 `db` 和 `app_logging`
- 聚合层直接依赖 `layers.middle_layer` 提供的读写接口
- 抽取器直接依赖 `layers.middle_layer.ExtractionResult`

## 高风险区域

- `layers/middle_layer.py`
  - schema dataclass 和持久化逻辑混在一个文件里
  - 改动会同时影响 extractor、测试、存储格式
- `layers/aggregator.py`
  - subtype 规范化规则决定了哪些 state 能被输出层看见
  - 幂等性依赖 `state_evidence` 去重逻辑
- `layers/extractors/`
  - 外部 API 行为
  - prompt/schema/provider 耦合
  - JSON 解析和重试失败
- `db/schema.py` 与分散 SQL
  - schema 改动波及面大
  - `python main.py --init` 有破坏性
  - `source_blocks` 持久化输入结构分块和 include decision；`chunk_source_blocks` 记录 chunk provenance
  - `state_candidate_supports` 是 candidate 级准入记录，不保存 excerpt、matched text 或 support score，也不替代 `state_evidence`
- `main.py` 与 `documents.status`
  - `processed` 只表示该文档当前所有 chunk 都已有 extraction
  - pending 队列以“chunk 是否缺少 extraction”为恢复依据，会重新纳入旧的过早 processed 文档中的未抽取 chunk
  - 更完整的失败状态、重试次数和错误持久化仍未设计
- `input_docs/`
  - 当前包含样例，也可能包含接近真实的个人/项目内容
  - 正式扫描链路不会默认纳入控制文档和测试夹具
  - 应按潜在敏感数据处理
- 文档上下文
  - front matter 不进入正文 chunk，但会作为 `source_blocks.include_decision = context_only` 持久化
  - 普通正文和普通表格中的“作者/标题”等词不再被当作文档 metadata
  - 当前只从真正 front matter 提炼标题、作者、文档时间作为抽取上下文
  - table block 与 quote block 当前 `context_only`；structured dump 与 media placeholder 当前 `exclude`
  - `context_only` 块不会拼入 `chunks.text`，而是以最多 8 个、单项最多 240 字符、总预览约 1200 字符的 `source_context_blocks` 进入 `ExtractionContext`
  - `LLMExtractor` 会用代码侧 canonical context 覆盖模型返回的 context，确保 `source_context_blocks` 稳定写入 `extraction_json.context`
- `config.py`
  - 导入即创建目录，存在副作用

## 参考文件

- [README.md](/D:/Apps/Python/lab/personal_prompt/README.md)
- [docs/testing.md](/D:/Apps/Python/lab/personal_prompt/docs/testing.md)
- [.github/EXTRACTION_JSON_SCHEMA.md](/D:/Apps/Python/lab/personal_prompt/.github/EXTRACTION_JSON_SCHEMA.md)
- [db/schema.py](/D:/Apps/Python/lab/personal_prompt/db/schema.py)
- [db/connection.py](/D:/Apps/Python/lab/personal_prompt/db/connection.py)
- [layers/input_layer.py](/D:/Apps/Python/lab/personal_prompt/layers/input_layer.py)
- [layers/aggregator.py](/D:/Apps/Python/lab/personal_prompt/layers/aggregator.py)
- [layers/middle_layer.py](/D:/Apps/Python/lab/personal_prompt/layers/middle_layer.py)
- [layers/output_layer.py](/D:/Apps/Python/lab/personal_prompt/layers/output_layer.py)
- [layers/extractors/llm_extractor.py](/D:/Apps/Python/lab/personal_prompt/layers/extractors/llm_extractor.py)
- [tests/test_logging.py](/D:/Apps/Python/lab/personal_prompt/tests/test_logging.py)

## 未解决的结构性问题 / 信息缺口

- `documents.status` 只有最小完成语义：所有 chunk 都有 extraction 后才能变为 `processed`
- 失败 chunk 可通过 pending 队列重新进入抽取，但完整失败状态机、错误持久化与重试策略仍未设计
- `retrieval_candidates` 已接入 pending 候选池；`relation_candidates` 仍未接入 pending 持久化链路，也不会直接写入正式 `relations`
- 非正文 context-only 块已有 `source_blocks` 持久化，并会作为 bounded preview 进入 extraction context；抽取层不得仅根据这些上下文材料生成 observation
- `table_block` 当前默认不进入 `chunks.text`，只作为 `context_only` 辅助当前 chunk 解释；后续仍需观察是否需要更细的 table 准入策略
- 查询视图已分开正文证据链和上下文链：`v_chunk_source_trace` / `v_extraction_source_trace` / `v_state_source_trace` 追踪 extract blocks，`v_extraction_context_trace` 追踪 context_only blocks
- `v_state_candidate_support_trace` 可查询 accepted/rejected candidate 的准入决策；它解释 candidate 是否进入 state，不解释 state 的正式证据链
- 抽取词表和 subtype 词表的权威来源分散在代码和文档里
- 主体字段与 canonical/display 摘要已进入 `states` schema；仍没有主体 registry、层级 state 或跨主体关系图谱
- 当前 Markdown 输出仍存在表述过泛、主题标题弱、上下文报告不够像最终文章等质量问题；这些属于后续 output layer / `BundleNarrative` 阶段，本轮未修改输出层
- `ContextBundle` / `CandidateTopicBundle` / `BundleNarrative` 当前都只是输出层只读投影，不是持久化状态；归组依赖同文档、相邻 chunk、section、主体线索、强锚点和邻近 chunk 补全等保守启发式
- LLM narrative 分类只是可选输出整理器，不是新的 extractor 或 aggregator；默认 rule 模式不需要真实 API
- 未归组 state 当前只进入输出层返回值和日志诊断，不作为 `status.md` 的正式 `待澄清` 章节展示
- active reading-view 实现已将短句/评价句修订为“短语用状态 + 输出角色审查”；短句不会仅因短小或评价语气被降级，是否输出取决于主体、对象、关系、证据链和上下文
- 仓库只有最低可用 Ruff lint 与 GitHub Actions CI；当前没有完整 typecheck 事实源
- `input_docs/` 的隐私和提交策略需要人类确认
- 保留文档之间若出现冲突，当前默认以代码和本文件为准；更正式的权威顺序仍需要人类确认
