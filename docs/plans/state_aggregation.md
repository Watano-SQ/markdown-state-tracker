# State Aggregation Plan

## Step 1

- Goal:
  明确聚合输入输出边界，并实现独立的聚合模块骨架。输入是 `extractions.extraction_json`，输出是 `states` 与 `state_evidence` 的最小写入结果；如果 `subtype` 词表存在歧义，先记录最小 fallback 规则，并把扩展部分标为 `需要人类确认`。
- Files likely touched:
  `docs/specs/state_aggregation.md`
  `layers/aggregator.py`
  `layers/middle_layer.py`
- Validation:
  聚合模块可以读取 extraction 记录并成功解析 `ExtractionResult`；对空 `state_candidates` 安全跳过。
- Stop condition:
  已有可导入的聚合入口，且完成“读取 -> 解析 -> 规范化候选”的链路。

## Step 2

- Goal:
  将聚合模块接入主流程，并确保 evidence 写入具备基本幂等性，不因重复运行导致状态或证据爆炸；同时在聚合结束后清理失去全部证据的孤儿 state。
- Files likely touched:
  `layers/aggregator.py`
  `main.py`
  `layers/middle_layer.py`
- Validation:
  `python main.py --stats`
  观察 `active_states > 0`
  观察 `state_evidence` 非 0
  观察孤儿 state 不会继续参与输出
  观察 `output/status.md` 不再只有空骨架
- Stop condition:
  主流程中已在输出前执行聚合，且重复执行时结果稳定。

## Step 3

- Goal:
  补最小验证与文档同步，确保该任务被后续实现者接手时无需重新做需求澄清。
- Files likely touched:
  `test_*.py` 或 `tests/test_aggregator.py`
  `docs/changes.md`（仅在仓库长期决策发生变化时）
  `docs/architecture.md`（仅在模块边界发生变化时）
- Validation:
  `python main.py --stats`
  `python test_extraction_schema.py`
  必要时补充聚合链路的最小自动化测试
- Stop condition:
  任务边界、验证方式、未解决问题都已在 spec/plan 中明确记录，且无需虚构仓库当前能力。
