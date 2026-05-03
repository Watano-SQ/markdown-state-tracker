# State Output Profiles Plan

## Step 1

- Goal:
  先落地兼容壳层：新增最小 `OutputProfile` 模型与 profile registry，只启用 `default` profile，并保持当前 `output/status.md` 输出基本不变。
- Files likely touched:
  `layers/output_layer.py`
  可能新增 `test_output_layer.py` 或补充现有输出层测试
- Validation:
  至少验证：
  - `generate_output()` 仍可不传 profile 正常运行
  - `generate_output(profile_name="default")` 生成兼容的 `status.md`
  - default profile 仍按现有 dynamic/static 与 subtype 输出
  - 不新增多文件输出矩阵
- Stop condition:
  输出层入口已经 profile-aware，但用户可见默认输出未被破坏。

## Step 2

- Goal:
  增加单 profile 选择入口。优先采用 CLI 参数或等价轻量入口，让 `main.py` 能选择一个 profile 运行；未知 profile 应明确失败。
- Files likely touched:
  `main.py`
  `layers/output_layer.py`
  相关 CLI 或输出层测试
- Validation:
  至少验证：
  - `python main.py --help` 显示 profile 入口（如果采用 CLI）
  - 默认不传 profile 时仍使用 `default`
  - 传入未知 profile 时给出清晰错误
  - 单次运行只生成一个主输出
- Stop condition:
  项目具备“单次运行选择一个 profile”的执行模型，但仍不并行生成个人/团队/项目多套文件。

## Step 3

- Goal:
  在统一状态底座成熟后，逐步实现 profile-aware 筛选、排序、细节密度和完整性提示。先从默认 profile 的显著性和阶段性结果提示开始，再评估 `personal_review`、`team_sync`、`project_push` 是否值得逐个落地。
- Files likely touched:
  `layers/output_layer.py`
  `layers/middle_layer.py`（仅当需要读取 pending/完成度统计）
  `docs/architecture.md`
  `docs/testing.md`（仅当验证路径变化）
  `docs/changes.md`（若冻结新的长期输出契约）
  profile 级渲染测试
- Validation:
  至少验证：
  - profile 输出不能忽略 pending chunks
  - detail_level 能影响展示密度
  - salience_policy 能影响排序或纳入策略
  - profile 策略不重新定义主体归属或 canonical identity
- Stop condition:
  profile 层真正消费统一状态底座，输出呈现能随场景策略变化，同时不反向污染状态层。
