# 📚 完整文档导航

## 🎯 开始使用

根据你的需求选择合适的文档：

### 👶 第一次使用？

1. **快速开始**: 阅读 `QUICKSTART_CONDA.md` ⭐⭐⭐
   - 5分钟内完成从虚拟环境到运行的全过程
   - 包含复制粘贴命令
   - 自动化脚本选项
   
2. **详细设置**: 阅读 `CONDA_SETUP.md`
   - 逐步详细的 Conda 环境设置
   - 每个步骤的验证方法
   - 完整的故障排查指南

### 🔧 已设置好环境？

**立即运行**:
```bash
conda activate markdown_tracker
python main.py --skip-extraction    # 快速测试
python main.py                       # 完整测试
```

### 📖 学习项目架构？

1. **中文版**: `CLAUDE.md` - 项目设计文档
2. **英文版**: `README.md` - 项目 README

### 🧪 详细测试？

- `TESTING.md` - 完整测试流程和故障排查

---

## 📋 文档快速参考

| 文档名 | 用途 | 读者 | 耗时 |
|--------|------|------|------|
| **QUICKSTART_CONDA.md** | 从 Conda 到运行 | 新手 | 5 分钟 |
| **CONDA_SETUP.md** | 详细 Conda 设置 | 需要详细步骤 | 15 分钟 |
| **TESTING.md** | 完整测试指南 | 测试工程师 | 20 分钟 |
| **GETTING_STARTED.md** | 快速开始指南 | 所有人 | 10 分钟 |
| **CLAUDE.md** | 架构设计文档（中文） | 开发者 | 30 分钟 |
| **README.md** | 项目介绍（英文） | 所有人 | 10 分钟 |
| **PLAN.md** | 改进计划 | 贡献者 | 20 分钟 |

---

## 🚀 快速命令参考

### 环境管理

```bash
# 创建环境
conda create -n markdown_tracker python=3.11 -y

# 激活环境
conda activate markdown_tracker

# 查看所有环境
conda info --envs

# 删除环境
conda remove -n markdown_tracker --all -y
```

### 依赖管理

```bash
# 安装依赖
pip install -r requirements.txt

# 检查依赖
pip list | grep openai

# 升级依赖
pip install --upgrade openai python-dotenv
```

### 项目命令

```bash
# 初始化数据库
python main.py --init

# 快速测试（跳过 LLM）
python main.py --skip-extraction

# 完整运行
python main.py

# 查看统计
python main.py --stats

# 查看帮助
python main.py --help
```

### 数据库操作

```bash
# 查看统计
python main.py --stats

# 查询文档
sqlite3 data/state.db "SELECT * FROM documents;"

# 查询 chunks
sqlite3 data/state.db "SELECT COUNT(*) FROM chunks;"

# 查询抽取结果
sqlite3 data/state.db "SELECT COUNT(*) FROM extractions;"
```

---

## ⚙️ 配置管理

### 环境变量 (.env)

```bash
# 复制模板
cp .env.example .env

# 编辑 .env
OPENAI_API_KEY=sk-your-key-here    # 必需（如果使用 LLM）
LLM_MODEL=gpt-4o-mini               # 可选，默认值
LLM_TEMPERATURE=0.1                 # 可选，默认值
```

### 项目配置 (config.py)

```python
# 修改输入/输出路径
INPUT_DIR = PROJECT_ROOT / "your_docs"
OUTPUT_FILE = OUTPUT_DIR / "your_output.md"
```

### 输出格式 (layers/output_layer.py)

```python
# 修改输出分类
OUTPUT_CONFIG = {
    'dynamic': {
        'title': '动态状态',
        'subtypes': {
            'your_type': '你的分类',
        },
        'max_items_per_subtype': 10,  # 上限
    },
}
```

---

## 📊 测试流程

### Level 1: 快速验证 (~3 秒)

```bash
python main.py --skip-extraction
```

**验证**:
- ✓ 文档扫描
- ✓ Chunk 切分
- ✓ 输出文件生成

### Level 2: 完整流程 (~20 秒)

```bash
python main.py
```

**验证**:
- ✓ LLM 抽取
- ✓ 实体提取
- ✓ 状态候选识别
- ✓ 数据存储

### Level 3: 数据验证

```bash
python main.py --stats
sqlite3 data/state.db "SELECT * FROM extractions LIMIT 1;"
```

**验证**:
- ✓ 数据库内容
- ✓ 抽取结果质量

---

## 🆘 常见问题

### 环境相关

**Q: Conda 命令找不到？**
```bash
# 添加 Conda 到 PATH（Windows）
# 或重新启动终端（Linux/Mac）
conda --version
```

**Q: Python 版本不对？**
```bash
# 检查版本
python --version

# 指定版本创建环境
conda create -n markdown_tracker python=3.11 -y
```

### 依赖相关

**Q: 模块导入失败？**
```bash
pip install --upgrade -r requirements.txt
```

**Q: OpenAI API 错误？**
```bash
# 检查 API Key
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('OPENAI_API_KEY'))"
```

### 运行相关

**Q: 数据库损坏？**
```bash
python main.py --init
```

**Q: 文件权限错误？**
```bash
# 检查目录权限
ls -la data/
ls -la output/

# 重新创建目录
mkdir -p data output
```

### 性能相关

**Q: 运行很慢？**
- 快速测试用 `--skip-extraction`
- 完整测试首次会调用 LLM（15-30 秒正常）
- 检查网络连接

---

## 📈 项目状态

### 已完成 ✅

- [x] 三层架构框架
- [x] SQLite 数据库 Schema
- [x] 文档扫描和变更检测
- [x] 智能 chunk 切分
- [x] LLM 抽取器实现
- [x] 配置管理和 .env 支持
- [x] 输出文件生成
- [x] 版本快照控制

### 计划中 ⏳

- [ ] 聚合逻辑（state_candidates → states）
- [ ] 单元测试
- [ ] 日志系统
- [ ] 异常处理增强

详见 `PLAN.md`。

---

## 🎓 学习路径

### 新手路径

1. 读 `QUICKSTART_CONDA.md` (5 分钟)
2. 运行快速测试 (3 分钟)
3. 读 `GETTING_STARTED.md` (10 分钟)
4. 尝试完整流程 (20 分钟)

**总耗时**: ~40 分钟

### 开发者路径

1. 读 `CLAUDE.md` 理解架构 (30 分钟)
2. 读 `PLAN.md` 了解改进任务 (20 分钟)
3. 阅读源代码 (30 分钟)
4. 运行 `TESTING.md` 中的所有测试 (30 分钟)

**总耗时**: ~2 小时

### 贡献者路径

1. 完成开发者路径
2. 选择 `PLAN.md` 中的一个任务
3. 创建新分支
4. 实现改进
5. 提交 PR

---

## 📞 获取帮助

### 遇到问题？

1. **查看文档**: 从上面的表格选择相关文档
2. **搜索错误信息**: 在 `TESTING.md` 中查找错误信息
3. **检查 PLAN.md**: 了解已知的限制和进行中的任务
4. **查看源代码**: 查看 `CLAUDE.md` 中的代码架构说明

### 提出建议

- 编辑 `PLAN.md` 中的笔记
- 提交 Issue
- 创建 Pull Request

---

## 🎉 欢迎使用！

你已经拥有：
- ✅ 完整的项目框架
- ✅ 工作的 LLM 抽取器
- ✅ 可扩展的数据库设计
- ✅ 详细的文档和指南

现在就开始吧！

**推荐第一步**: 打开 `QUICKSTART_CONDA.md`，跟着步骤走。

预期耗时: **5-10 分钟**

---

## 📝 快速参考卡

### 最常用的 3 个命令

```bash
# 1. 快速测试（无需 API Key）
conda activate markdown_tracker && python main.py --skip-extraction

# 2. 完整运行（需要 API Key）
conda activate markdown_tracker && python main.py

# 3. 查看统计
conda activate markdown_tracker && python main.py --stats
```

### 最重要的 3 个文件

1. `QUICKSTART_CONDA.md` - 开始使用
2. `CLAUDE.md` - 理解设计
3. `PLAN.md` - 了解未来

### 最常用的 3 个目录

```
input_docs/       ← 放你的 Markdown 文件
output/           ← 输出目录
data/state.db     ← SQLite 数据库
```

---

**祝你使用愉快！** 🚀
