# Relation And Retrieval Candidate Fate Plan

## Step 1

- Goal:
  接入 `retrieval_candidates` 的最小持久化路径。聚合层读取 extraction JSON 中的 retrieval candidates，调用中间层接口写入候选池，并保证重复聚合同一 chunk/extraction 不会让 evidence 计数虚增。
- Files likely touched:
  `layers/aggregator.py`
  `layers/middle_layer.py`
  `test_aggregator.py` 或新增最小候选持久化测试
  必要时 `docs/testing.md`
- Validation:
  至少验证：
  - 有 retrieval candidate 的 extraction 会生成数据库候选记录
  - `surface_form` 为空的候选会被跳过
  - 重复运行聚合保持幂等
  - `priority` 被限制在 0-10
- Stop condition:
  检索候选不再只停留在 `extractions.extraction_json` 内，并且重复聚合不会污染统计。

## Step 2

- Goal:
  为 `relation_candidates` 增加 pending 持久化命运，但不直接写入正式 `relations`。如果现有 schema 无法表达 pending candidate，新增最小 `relation_candidates` 表及中间层写入接口。
- Files likely touched:
  `db/schema.py`
  `layers/middle_layer.py`
  `layers/aggregator.py`
  `test_aggregator.py` 或新增 relation candidate 测试
  `.github/EXTRACTION_JSON_SCHEMA.md`（仅当候选字段语义变化）
- Validation:
  至少验证：
  - 有 relation candidate 的 extraction 会生成 pending 候选记录
  - pending 候选保留 source/target 原文、relation_type、confidence、chunk_id、extraction_id
  - 重复运行聚合保持幂等
  - 无法映射 source/target id 的候选不会进入正式 `relations`
- Stop condition:
  关系候选具备可追踪 pending 记录，而正式 `relations` 仍只保留已裁决、可定位的关系。

## Step 3

- Goal:
  补齐候选裁决边界、统计与文档同步。明确 pending/confirmed/rejected 的最小语义，并让 stats 或诊断路径能观察候选数量，但不要求输出层展示这些候选。
- Files likely touched:
  `layers/middle_layer.py`
  `main.py`（仅当 stats 输出需要扩展）
  `docs/architecture.md`
  `docs/testing.md`（仅当验证命令或诊断路径变化）
  `docs/changes.md`（若 schema 或长期边界被正式接受）
- Validation:
  至少验证：
  - `python -m unittest test_aggregator.py`
  - `python test_extraction_schema.py`
  - 如 stats 变更，运行 `python main.py --stats`
- Stop condition:
  后续实现者能清楚区分：
  - retrieval candidate 的 pending 候选池
  - relation candidate 的 pending 观察记录
  - 正式 `relations`
  - 输出层暂不消费候选的边界
