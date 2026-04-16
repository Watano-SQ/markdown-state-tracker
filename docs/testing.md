# 测试与验证

这份文档是当前仓库测试命令与验证路径的事实源。

## 前置条件

推荐环境：

```bash
conda create -n markdown_tracker python=3.11 -y
conda activate markdown_tracker
pip install -r requirements.txt
```

如需跑 LLM 抽取，再配置：

```bash
cp .env.example .env
```

## 快速验证

以下命令不要求真实 API 调用：

```bash
python main.py --help
python test_extraction_schema.py
python -m unittest test_aggregator.py
python -m unittest test_logging.py
python test_font_filtering.py
python main.py --skip-extraction
python main.py --stats
```

## 可选：完整抽取验证

如果 `.env` 已配置：

```bash
python main.py
```

重点验证：

- chunk 被处理
- 抽取日志写入成功
- `extractions` 表中出现记录
- `states` 表中出现聚合结果
- `output/status.md` 不再只有空骨架

不要把“完整状态管理”理解成“已经全部完成”。  
当前主链路里，基础聚合已接通，但失败 chunk 的恢复、关系落库、检索候选落库仍未全部完成。

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
```

## 当前合理预期

- `--skip-extraction` 会创建或更新数据库与输出文件
- 现有测试不依赖真实 API
- 在已有 `extractions` 的情况下，主流程会尝试聚合并生成 `states`
- 日志中应能看到 pipeline 和 extraction 事件

## 可选诊断脚本

`test_config.py` 可以辅助排查环境配置，但它不是常规验证路径的一部分。
