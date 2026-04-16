# 变更与决策

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

活跃文档体系收敛为：`AGENTS.md`、`README.md`、`docs/architecture.md`、`docs/specs/_template.md`、`docs/plans/_template.md`、`docs/changes.md`、`CONTRIBUTING.md`、`TESTING.md`、`.github/EXTRACTION_JSON_SCHEMA.md`。

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
