# State Output Quality Plan

## Step 1

- Goal:
  盘点当前样本文档中的输入边界问题，并把“文件级边界”和“文档内来源类型边界”拆开记录清楚。输出应能说明当前样本里哪些内容属于作者正文，哪些内容属于 front matter、元数据表格、引用问答、外部资料、结构化转储或媒体占位。
- Files likely touched:
  `docs/specs/state_output_quality.md`
  必要时只补充最小背景引用，不进入实现代码
- Validation:
  对当前样本做人工核对时，至少能稳定点名以下对象：
  `input_docs/李申亮.md`
  `input_docs/邹少乾.md`
  `input_docs/汪翰元.md`
  并说明其中各类边界问题的代表场景
- Stop condition:
  后续实现者无需再重新澄清“问题来自扫描范围过宽，还是来自单篇文档内部来源混杂”。

## Step 2

- Goal:
  冻结第一阶段的最小来源类型分类法与默认处理策略。核心是明确每类块默认应“进入抽取正文 / 仅作为上下文 / 直接跳过”中的哪一种，并规定哪些结构边界禁止跨越。
- Files likely touched:
  `docs/specs/state_output_quality.md`
  后续实现阶段预计影响：
  `layers/input_layer.py`
  `layers/extractors/rule_helper.py`
- Validation:
  spec 中至少明确以下内容：
  - 来源类型清单
  - 每类的默认处理方式
  - 不可跨越的结构边界
  - `文档切片探索.md` 可借鉴与不可借鉴的范围
- Stop condition:
  后续实现者无需再重新发明来源类型词表，也无需再争论 blockquote、元数据表格、HTML/JSON 转储是否应与正文混切。

## Step 3

- Goal:
  冻结第一阶段的验证面、最小测试方向与未决边界。重点是给后续实现留出可验证入口，并把不能由仓库现状单独决定的策略问题显式标成 `需要人类确认`。
- Files likely touched:
  `docs/plans/state_output_quality.md`
  `docs/specs/state_output_quality.md`
  后续实现阶段可能新增最小测试文件，例如针对 source typing 或 chunk 边界的测试
- Validation:
  计划文档应明确后续实现至少需要验证：
  - front matter 与元数据表格不进入普通正文抽取
  - 长段 blockquote 独立成块
  - 结构化转储与自然语言叙述分离
  - 非样本文档不会默认进入正式状态扫描
  若测试命令正典发生变化，再同步到 `docs/testing.md`
- Stop condition:
  第一阶段的实现入口、验证入口和人工决策缺口都已明确，后续可以直接进入实现，不必把第二、三阶段问题混进当前任务。
