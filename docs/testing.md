# 测试与验证

这份文档是当前仓库测试命令与验证路径的事实源。

## 前置条件

推荐环境：

```bash
conda create -n markdown_tracker python=3.11 -y
conda activate markdown_tracker
pip install -r requirements.txt
```

如需运行 lint / CI 同款本地检查，再安装开发依赖：

```bash
pip install -r requirements-dev.txt
```

如需跑 LLM 抽取，再配置：

```bash
cp .env.example .env
```

## Lint

当前仓库的最低可用 lint 门禁是 Ruff：

```bash
ruff check .
```

Ruff 配置保持低摩擦，主要拦截语法级失败和未定义名称等基础问题；它不是格式化迁移，也不是完整业务正确性证明。

## 快速验证

以下命令不要求真实 API 调用：

```bash
python main.py --help
ruff check .
python -m unittest tests.test_input_layer
python -m tests.test_extraction_schema
python -m unittest tests.test_aggregator
python -m unittest tests.test_middle_layer
python -m unittest tests.test_output_layer
python -m unittest tests.test_logging
python -m tests.test_font_filtering
python main.py --skip-extraction
python main.py --stats
```

输出 narrative 默认使用规则模式，不需要真实 API。
如需显式验证默认模式：

```bash
$env:OUTPUT_NARRATIVE_MODE="rule"
python main.py --skip-extraction
```

## CI 默认验证

GitHub Actions 默认运行以下无 API 检查：

```bash
ruff check .
python main.py --help
python -m unittest tests.test_input_layer
python -m tests.test_extraction_schema
python -m unittest tests.test_aggregator
python -m unittest tests.test_middle_layer
python -m unittest tests.test_output_layer
python -m unittest tests.test_logging
python -m tests.test_font_filtering
```

CI 默认不运行：

- `python main.py`
- `python main.py --init`
- `python main.py --skip-extraction`
- `python main.py --stats`

`--skip-extraction` 和 `--stats` 不要求真实 API，适合本地快速验证；但它们会创建或读取运行时数据库、日志和输出文件。为保持最低 CI 门禁稳定、无运行产物依赖，暂不放入默认 CI。

## 可选：完整抽取验证

如果 `.env` 已配置：

```bash
python main.py
```

重点验证：

- chunk 被处理
- `source_blocks` 与 `chunk_source_blocks` 已生成，可追溯 chunk 来源
- 抽取日志写入成功
- `extractions` 表中出现记录
- `states` 表中出现聚合结果
- `output/status.md` 不再只有空骨架，并按主体 / 主题 narrative 展示

可选验证 LLM narrative 分类器：

```bash
$env:OUTPUT_NARRATIVE_MODE="llm"
python main.py --skip-extraction
```

如果 LLM narrative 请求失败，输出层应回退到规则 narrative，而不是让主流程失败。

不要把“完整状态管理”理解成“已经全部完成”。  
当前主链路里，基础聚合已接通，失败 chunk 有最小 pending 恢复，`retrieval_candidates` 有 pending 候选池；但完整失败状态机、关系落库、检索候选裁决/完整生命周期仍未完成。

## 破坏性验证

只有在你明确要重建数据库时才运行：

```bash
python main.py --init
```

## 建议检查的产物

- `output/status.md`
- `data/state.db`
- `data/logs/pipeline.log`

可用命令：

```bash
python main.py --stats
sqlite3 data/state.db "SELECT COUNT(*) FROM documents;"
sqlite3 data/state.db "SELECT COUNT(*) FROM chunks;"
sqlite3 data/state.db "SELECT COUNT(*) FROM extractions;"
sqlite3 data/state.db "SELECT COUNT(*) FROM v_source_block_inventory;"
sqlite3 data/state.db "SELECT COUNT(*) FROM v_extraction_context_trace;"
sqlite3 data/state.db "SELECT decision, reason, COUNT(*) FROM v_state_candidate_support_trace GROUP BY decision, reason;"
sqlite3 data/state.db "SELECT * FROM v_state_candidate_support_trace WHERE decision='reject';"
```

## 当前合理预期

- `--skip-extraction` 会创建或更新数据库与输出文件
- 现有测试不依赖真实 API
- 输入边界与来源类型改动应至少跑 `python -m unittest tests.test_input_layer`
- 输入层应持久化 `source_blocks` / `chunk_source_blocks`；`--skip-extraction` 也应完成这一步
- source/context trace 视图应可查询；重点看 `v_chunk_source_trace`、`v_state_source_trace` 与 `v_extraction_context_trace`
- candidate 准入 trace 视图应可查询；重点看 `v_state_candidate_support_trace` 中的 accepted/rejected 分布，以及 rejected candidate 的 `reason`
- 在已有 `extractions` 的情况下，主流程会尝试聚合并生成 `states`
- 只有 accepted `state_candidates` 会写入 `states/state_evidence`；`context_only_only`、`no_text_support`、`missing_subject`、`invalid_candidate` 都只写入 `state_candidate_supports`
- `output/status.md` 正式内容不应显示 `置信度:`、固定语义小节标题或 `summary：detail` 式事实句
- 日志中应能看到 pipeline 和 extraction 事件

## 可选诊断脚本

`tests/test_config.py` 可以通过 `python -m tests.test_config` 辅助排查环境配置，但它不是常规验证路径的一部分。
