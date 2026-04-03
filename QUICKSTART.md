# 快速入门指南

## 第一步：创建 GitHub 仓库

1. 访问 GitHub 并创建新仓库
   - 仓库名：`markdown-state-tracker`
   - 描述：`A local Markdown document state tracking and incremental update system`
   - 选择 Public 或 Private
   - **不要**初始化 README（我们已经有了）

2. 记下仓库 URL，例如：
   ```
   https://github.com/yourusername/markdown-state-tracker.git
   ```

## 第二步：推送到 GitHub

在项目目录中执行：

```bash
# 添加远程仓库（替换为你的仓库 URL）
git remote add origin https://github.com/yourusername/markdown-state-tracker.git

# 推送到 GitHub
git push -u origin master
```

或使用 SSH：

```bash
git remote add origin git@github.com:yourusername/markdown-state-tracker.git
git push -u origin master
```

## 第三步：使用系统

### 基本使用流程

1. **准备文档**
   ```bash
   # 将你的 .md 文件放到 input_docs/ 目录
   cp /path/to/your/notes/*.md input_docs/
   ```

2. **运行处理**
   ```bash
   python main.py
   ```

3. **查看结果**
   ```bash
   # 查看生成的状态文档
   cat output/status.md
   
   # 或在编辑器中打开
   code output/status.md
   ```

### 增量更新

当你添加新文档或修改现有文档后：

```bash
# 直接再次运行即可
python main.py
```

系统会自动：
- 检测新增的文档
- 检测内容有变化的文档（基于 hash）
- 只处理变更过的文档
- 更新状态文档

### 查看统计

```bash
# 查看当前系统状态
python main.py --stats
```

输出示例：
```
当前状态:
  documents: 5
  chunks: 12
  extractions: 12
  active_states: 8
  archived_states: 2
  pending_candidates: 3
```

### 重置系统

如果需要重新开始：

```bash
# 强制重新初始化数据库（会删除所有数据）
python main.py --init

# 然后重新运行
python main.py
```

## 第四步：自定义配置

### 修改输入输出路径

编辑 `config.py`：

```python
INPUT_DIR = PROJECT_ROOT / "your_custom_input_folder"
OUTPUT_FILE = OUTPUT_DIR / "custom_status.md"
```

### 调整输出分类

编辑 `layers/output_layer.py` 中的 `OUTPUT_CONFIG`：

```python
OUTPUT_CONFIG = {
    'dynamic': {
        'title': '动态状态',
        'subtypes': {
            'ongoing_project': '进行中的项目',
            # 添加你的自定义子类型
            'your_custom_type': '你的自定义分类',
        },
        'max_items_per_subtype': 10,  # 调整上限
    },
    # ...
}
```

### 调整 chunk 大小

编辑 `layers/input_layer.py` 中的 `chunk_document` 函数调用：

```python
chunks = chunk_document(doc.content, max_tokens=1000)  # 默认 500
```

## 常见问题

### Q: 如何查看数据库内容？

```bash
# 使用 SQLite 命令行工具
sqlite3 data/state.db

# 或使用 Python
python -c "from db import get_connection; print(get_connection().execute('SELECT * FROM documents').fetchall())"
```

### Q: 如何删除某个文档的处理结果？

```bash
python -c "
from db import get_connection
conn = get_connection()
conn.execute('DELETE FROM documents WHERE path = ?', ('your_file.md',))
conn.commit()
"
```

### Q: 输出文档为什么是空的？

当前版本的抽取器部分尚未实现。系统已经：
- ✅ 扫描并切分了文档
- ✅ 存储到数据库
- ❌ 但还没有从 chunks 中提取状态项

这是设计上的预留接口，需要你根据实际需求实现抽取逻辑。

## 下一步

- 查看 [README.md](README.md) 了解系统架构
- 实现自定义抽取器（`layers/middle_layer.py` 中的抽取逻辑）
- 扩展输出模板
- 集成 LLM 进行语义理解

## 技术支持

遇到问题？
- 查看 [Issues](https://github.com/yourusername/markdown-state-tracker/issues)
- 提交新 Issue
- 查看源代码注释
