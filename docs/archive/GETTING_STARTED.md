# 快速开始指南

## 🎯 项目状态

✅ **项目可以运作** - LLM 抽取器已完成，核心流程已集成。

**当前运作流程**:
```
输入文档 (Markdown)
    ↓ [输入层]
扫描、切分、变更检测
    ↓ [中间层]
LLM 抽取（可选）→ 结构化存储 (SQLite)
    ↓ [输出层]
生成状态文档 (Markdown)
```

---

## 🚀 3 分钟快速开始

### 步骤 1: 安装依赖

```bash
pip install -r requirements.txt
```

或手动安装：
```bash
pip install openai python-dotenv
```

### 步骤 2: 配置 API Key

```bash
# 复制模板
cp .env.example .env

# 编辑 .env，填入你的 OpenAI API Key
# 文本编辑器打开 .env，修改这一行：
# OPENAI_API_KEY=sk-your-key-here
```

### 步骤 3: 运行

**选项 A - 完整运行（包括 LLM 抽取）**:
```bash
python main.py
```
文件日志采用多行块状格式，适合直接在 IDE 中顺序查看每个 `event`、`chunk`、重试和耗时。
默认会输出控制台摘要，并把详细事件写入 `data/logs/pipeline.log`。

**选项 B - 快速测试（跳过 LLM，快）**:
```bash
python main.py --skip-extraction
```
 
**选项 C - 静默运行（只保留文件日志）**:
```bash
python main.py --quiet
```

### 步骤 4: 查看结果

```bash
# 查看生成的状态文档
cat output/status.md
```

---

## 📊 项目运作状态详解

### 已完成的部分 ✅

| 组件 | 状态 | 说明 |
|------|------|------|
| **输入层** | ✅ 完成 | 文档扫描、智能切分、变更检测 |
| **中间层（数据存储）** | ✅ 完成 | SQLite 8 表 Schema，所有 CRUD 接口 |
| **抽取器** | ✅ 完成 | LLM 抽取 + 规则预/后处理 |
| **输出层** | ✅ 完成 | 固定骨架 Markdown 生成，快照版本控制 |
| **配置管理** | ✅ 完成 | .env 支持，CLI 参数 |
| **日志系统** | ✅ 完成 | 控制台摘要 + 轮转文件日志 |

### 缺失的部分 ⏳

| 功能 | 优先级 | 说明 |
|------|--------|------|
| **聚合逻辑** | P1 | state_candidates → states 的合并 |
| **单元测试** | P1 | 已有 extraction schema 和 logging 测试，分层覆盖仍不足 |
| **异常处理** | P2 | 部分错误处理缺失 |

---

## 💡 使用场景

### 场景 1: 个人知识管理

```
input_docs/
  ├── 2024年3月学习.md      ← 学习笔记
  ├── 项目进展.md            ← 项目状态
  └── 读书笔记.md            ← 阅读记录

运行后生成 output/status.md，包含：
  - 当前学习项目
  - 最近完成的任务
  - 进行中的工作
  - 个人关注点
```

### 场景 2: 团队状态跟踪

```
input_docs/
  ├── 张三_周报.md
  ├── 李四_周报.md
  └── 王五_周报.md

运行后生成 output/status.md，包含所有人的：
  - 本周完成事项
  - 进行中的项目
  - 下周计划
```

---

## 🔧 常见操作

### 重新处理所有文档

```bash
python main.py --init       # 清空数据库
python main.py              # 重新处理
```

### 查看统计信息

```bash
python main.py --stats
```

### 查看详细运行日志

```bash
cat data/logs/pipeline.log
```

日志示例：

```text
2026-04-15 21:08:42 [WARNING] extractor event=llm_request_retry
  context: run_id: 9f2a1c0d7b41, stage: extraction
  source: chunk: 99, path: retry.md
  retry: attempt: 2/2, sleep: 2s
  error: RuntimeError: boom
  note: Retrying after LLM request failure
```

输出：
```
当前状态:
  documents: 2
  chunks: 2
  extractions: 2
  active_states: 0
  archived_states: 0
```

### 查看数据库

```bash
sqlite3 data/state.db
> .mode column
> .headers on
> SELECT * FROM documents;
```

---

## 📈 性能表现

| 指标 | 数值 |
|------|------|
| 文档扫描 | < 1s |
| 智能切分 | 取决于文档大小 |
| LLM 抽取（2 chunks） | 15-30s |
| 输出生成 | < 1s |
| **总耗时** | **20-35s** |
| **成本**（100 chunks） | **~$0.01** |

---

## 🐛 故障排查

### 错误 1: `ModuleNotFoundError: No module named 'openai'`

```bash
pip install openai
```

### 错误 2: `OpenAI API Error: 401 Unauthorized`

- 检查 API Key 是否正确
- 确认 `.env` 文件已创建且 API Key 已填入
- 验证 API 余额充足

### 错误 3: `No such file or directory: 'input_docs'`

```bash
mkdir -p input_docs
# 添加 .md 文件到 input_docs 目录
```

### 错误 4: 没有权限写入 output 目录

```bash
chmod 755 output
# 或手动创建目录
mkdir -p output
```

---

## 📚 后续学习

### 了解更多

- **项目架构**: 读 `CLAUDE.md`（中文）或 `README.md`（英文）
- **技术细节**: 读 `PLAN.md` 中的任务说明
- **测试方法**: 读 `TESTING.md`

### 下一步改进

1. **任务 2**: 实现聚合逻辑（PLAN.md）
2. **任务 3**: 添加单元测试（PLAN.md）

详见项目根目录 `PLAN.md`。

---

## 🎓 架构快速说明

```
main.py（主入口）
  │
  ├─→ [输入层] layers/input_layer.py
  │   └─ 扫描文档 → 检测变更 → 智能切分 → chunks 表
  │
  ├─→ [中间层] layers/middle_layer.py
  │   ├─ 保存 chunks 到数据库
  │   ├─ [新增] LLM 抽取
  │   └─ 存储 extractions（JSON 格式）
  │
  ├─→ [抽取器] layers/extractors/llm_extractor.py（新增）
  │   ├─ 规则预处理 → Markdown 实体、日期提取
  │   ├─ LLM 调用 → 结构化 JSON 输出
  │   └─ 规则后处理 → Schema 校验、去重
  │
  ├─→ [日志] app_logging.py
  │   └─ 控制台摘要 + 文件日志（run_id、事件、耗时）
  │
  └─→ [输出层] layers/output_layer.py
      └─ 从数据库选取 → 生成 status.md
```

**数据库 Schema** (8 表):
- `documents` - 文档元信息
- `chunks` - 文档片段
- `extractions` - 抽取结果（JSON）
- `states` - 聚合后的状态项 ⚠️ 当前还未聚合
- `state_evidence` - 状态证据关联
- `relations` - 状态间关系
- `retrieval_candidates` - 待确认对象
- `output_snapshots` - 输出版本历史

---

## ❓ 常见问题

**Q: 为什么输出里没有任何状态项？**
A: 因为聚合逻辑还没实现。现在 extractions 表有数据，但没有被合并到 states 表。参见 PLAN.md 任务 2。

**Q: 能离线使用吗？**
A: 做完整抽取时不能离线，因为需要 LLM API；但可以用 `--skip-extraction` 离线测试扫描、存储、输出和日志流程。

**Q: 怎样修改输出格式？**
A: 编辑 `layers/output_layer.py` 中的 `OUTPUT_CONFIG` 和 `generate_status_document()`。

**Q: 支持其他 LLM 吗？**
A: 支持 OpenAI 兼容接口。除了 OpenAI，也可以通过 `OPENAI_BASE_URL` 和 `LLM_MODEL` 配置兼容的其他提供商。

---

**祝你使用愉快！** 🚀
