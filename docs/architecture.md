# 架构事实

## 仓库用途

`Markdown State Tracker` 是一个本地原型：把 `input_docs/` 中的 Markdown 扫描、切分、存储到 SQLite，并生成 `output/status.md`。

当前主流程：

1. 扫描 Markdown 文档
2. 基于带输入处理版本的内容 hash 识别新增或修改
3. chunk 切分并落库
4. 按需执行 LLM 抽取
5. 聚合 `state_candidates -> states/state_evidence`
6. 从数据库生成输出 Markdown

注意：基础聚合链路现已接入主流程，但相关状态管理仍不完整；尤其是失败 chunk 的恢复、关系落库、检索候选落库仍未打通。

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
  - 变更检测
  - 来源类型感知的 chunk 切分
  - documents/chunks 落库
- [layers/middle_layer.py](/D:/Apps/Python/lab/personal_prompt/layers/middle_layer.py)
  - `ExtractionResult` 相关 dataclass
  - extractions / states / state_evidence / retrieval_candidates / stats
  - chunk 级 pending 查询与文档完成标记
- [layers/aggregator.py](/D:/Apps/Python/lab/personal_prompt/layers/aggregator.py)
  - 读取 `extractions`
  - 规范化 `state_candidates`
  - 写入 `states` 与 `state_evidence`
- [layers/output_layer.py](/D:/Apps/Python/lab/personal_prompt/layers/output_layer.py)
  - 选择活跃状态
  - 生成 Markdown
  - 保存输出快照
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
- `main.py` 与 `documents.status`
  - `processed` 只表示该文档当前所有 chunk 都已有 extraction
  - pending 队列以“chunk 是否缺少 extraction”为恢复依据，会重新纳入旧的过早 processed 文档中的未抽取 chunk
  - 更完整的失败状态、重试次数和错误持久化仍未设计
- `input_docs/`
  - 当前包含样例，也可能包含接近真实的个人/项目内容
  - 正式扫描链路不会默认纳入控制文档和测试夹具
  - 应按潜在敏感数据处理
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
- [test_logging.py](/D:/Apps/Python/lab/personal_prompt/test_logging.py)

## 未解决的结构性问题 / 信息缺口

- `documents.status` 只有最小完成语义：所有 chunk 都有 extraction 后才能变为 `processed`
- 失败 chunk 可通过 pending 队列重新进入抽取，但完整失败状态机、错误持久化与重试策略仍未设计
- `relation_candidates` / `retrieval_candidates` 仍未接入正式持久化链路
- 抽取词表和 subtype 词表的权威来源分散在代码和文档里
- 仓库没有配置 lint/typecheck/CI 事实源
- `input_docs/` 的隐私和提交策略需要人类确认
- 保留文档之间若出现冲突，当前默认以代码和本文件为准；更正式的权威顺序仍需要人类确认
