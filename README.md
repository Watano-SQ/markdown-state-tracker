# Markdown State Tracker

本仓库是一个本地 Markdown 状态追踪原型：扫描 `input_docs/` 中的 Markdown，写入 SQLite，并生成 `output/status.md`。

## 当前真实状态

目前已经实现：

- 文档扫描与基于 hash 的增量检测
- chunk 切分与 SQLite 存储
- 可选的 LLM 抽取
- `state_candidates -> states` 的基础聚合链路
- 文件日志
- 固定骨架的输出文档生成

目前仍未完全解决：

- 部分 chunk 抽取失败后的完整状态流转
- `relation_candidates` / `retrieval_candidates` 的正式落库
- 更强的 LLM 脏响应健壮性

因此，当前仓库已经可以基于已有 `extractions` 生成非空状态输出；但增量恢复和关系类数据仍不是完整实现。

## 推荐环境

推荐使用 `Conda + Python 3.11`。  
仓库代码本身只依赖 Python、SQLite 和 `requirements.txt` 中的依赖，但现有脚本和历史使用路径都默认按 Conda 编写。

## 快速开始

### 1. 创建并激活环境

```bash
conda create -n markdown_tracker python=3.11 -y
conda activate markdown_tracker
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 先跑无 API 的主流程

```bash
python main.py --skip-extraction
python main.py --stats
```

### 4. 如需抽取，再配置 `.env`

```bash
cp .env.example .env
```

当前保留文档默认只按 OpenAI 路径说明。  
如果你只是想按文档跑通，配置 `OPENAI_API_KEY` 即可。

### 5. 运行完整流程

```bash
python main.py
```

## 常用命令

```bash
python main.py --help
python main.py --skip-extraction
python main.py --stats
python main.py --quiet
python main.py --log-level INFO --log-file data/logs/pipeline.log
```

破坏性命令：

```bash
python main.py --init
```

`--init` 会删除并重建本地 SQLite 数据库。

## 核心路径

- `main.py`：CLI 入口
- `db/`：Schema 和连接管理
- `layers/`：输入层、中间层、输出层、抽取器
- `input_docs/`：输入文档
- `data/state.db`：数据库
- `data/logs/pipeline.log`：日志
- `output/status.md`：输出文档

## 继续阅读

- [docs/architecture.md](/D:/Apps/Python/lab/personal_prompt/docs/architecture.md)：当前架构事实、依赖方向、高风险区域
- [TESTING.md](/D:/Apps/Python/lab/personal_prompt/TESTING.md)：验证方式与预期结果
- [CONTRIBUTING.md](/D:/Apps/Python/lab/personal_prompt/CONTRIBUTING.md)：协作与提交流程
- [.github/EXTRACTION_JSON_SCHEMA.md](/D:/Apps/Python/lab/personal_prompt/.github/EXTRACTION_JSON_SCHEMA.md)：抽取 schema 参考

## 项目边界

这个仓库不是：

- Web 服务
- 通用聊天助手
- 平台级长期记忆系统
- 联网搜索系统
- 重型数据库应用
