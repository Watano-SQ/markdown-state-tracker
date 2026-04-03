# 贡献指南

感谢你对 Markdown State Tracker 的关注！

## 项目原则

在贡献之前，请理解项目的核心原则：

1. **最小可行** - 优先简单实现，不过度工程化
2. **边界明确** - 这是原型，不是平台级产品
3. **易于理解** - 代码清晰优先于技巧炫耀
4. **可替换性** - 模块间松耦合，便于替换实现

## 适合贡献的方向

### 🎯 高优先级

- [ ] 实现基于 LLM 的抽取器（从 chunks 提取结构化信息）
- [ ] 实现基于规则的抽取器（正则表达式、关键词匹配）
- [ ] 抽取结果的聚合与去重逻辑
- [ ] 状态项的语义相似度匹配
- [ ] retrieval_candidates 的处理规则

### 🔧 中等优先级

- [ ] 更智能的 chunk 切分策略
- [ ] 时间衰减算法实现
- [ ] 归档策略优化
- [ ] 输出模板的可配置性增强
- [ ] 性能优化（大量文档场景）

### 📚 文档与示例

- [ ] 更多示例文档
- [ ] 抽取器实现教程
- [ ] 常见使用场景文档
- [ ] API 文档

### 🚫 不适合的方向（超出项目范围）

- ❌ 引入重型数据库（PostgreSQL、MongoDB 等）
- ❌ 构建 Web 界面或 API 服务器
- ❌ 集成联网搜索
- ❌ 构建完整的知识图谱系统
- ❌ 添加用户系统和权限管理

如果你想做这些，建议 fork 后独立发展。

## 如何贡献

### 1. Fork 项目

点击右上角的 "Fork" 按钮

### 2. 克隆到本地

```bash
git clone https://github.com/yourusername/markdown-state-tracker.git
cd markdown-state-tracker
```

### 3. 创建分支

```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/your-bug-fix
```

分支命名规范：
- `feature/xxx` - 新功能
- `fix/xxx` - Bug 修复
- `docs/xxx` - 文档更新
- `refactor/xxx` - 重构

### 4. 进行修改

遵循代码风格：
- 使用清晰的变量名
- 添加必要的注释（特别是复杂逻辑）
- 保持函数单一职责
- 避免过度抽象

### 5. 测试修改

```bash
# 运行基本测试
python main.py --init
python main.py

# 确保没有错误
python main.py --stats
```

### 6. 提交

```bash
git add .
git commit -m "feat: add your feature description

Detailed explanation of what this commit does.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

提交信息规范：
- `feat: xxx` - 新功能
- `fix: xxx` - Bug 修复
- `docs: xxx` - 文档更新
- `refactor: xxx` - 重构
- `test: xxx` - 测试相关

### 7. 推送并创建 PR

```bash
git push origin feature/your-feature-name
```

然后在 GitHub 上创建 Pull Request。

## PR 审查标准

你的 PR 将根据以下标准审查：

### ✅ 必须满足

- [ ] 代码可以正常运行
- [ ] 没有引入新的依赖（或有充分理由）
- [ ] 符合项目边界和原则
- [ ] 有清晰的提交信息

### 👍 最好有

- [ ] 添加了注释说明
- [ ] 更新了相关文档
- [ ] 提供了使用示例
- [ ] 考虑了边界情况

### ⚠️ 需要讨论

- [ ] 修改了核心架构
- [ ] 引入了新的设计模式
- [ ] 改变了数据库 schema
- [ ] 影响了现有功能

## 代码风格

### Python 风格

```python
# ✅ 好的风格
def process_document(doc: DocumentInfo) -> List[Chunk]:
    """处理文档并返回 chunks
    
    Args:
        doc: 文档信息对象
    
    Returns:
        切分后的 chunk 列表
    """
    chunks = []
    # 实现逻辑
    return chunks

# ❌ 避免
def f(x):  # 不清晰的函数名
    return [y for y in x if len(y) > 0]  # 缺少说明
```

### 数据库操作

```python
# ✅ 使用参数化查询
cursor.execute("SELECT * FROM documents WHERE path = ?", (path,))

# ❌ 避免字符串拼接
cursor.execute(f"SELECT * FROM documents WHERE path = '{path}'")
```

### 导入顺序

```python
# 1. 标准库
import json
from pathlib import Path

# 2. 第三方库（如果有）
# import numpy as np

# 3. 项目内模块
from config import DB_PATH
from db import get_connection
```

## 报告 Bug

提交 Issue 时请包含：

1. **问题描述** - 发生了什么？
2. **复现步骤** - 如何触发这个问题？
3. **期望行为** - 应该发生什么？
4. **环境信息** - Python 版本、操作系统
5. **相关日志** - 错误信息、堆栈跟踪

## 提出功能建议

提交 Issue 时请说明：

1. **使用场景** - 什么情况下需要这个功能？
2. **预期效果** - 这个功能应该如何工作？
3. **替代方案** - 目前如何解决这个问题？
4. **项目契合度** - 这个功能是否符合项目边界？

## 问题讨论

- 使用 GitHub Issues 进行异步讨论
- 复杂设计决策可以先开 Issue 讨论再实现
- 尊重不同意见，保持建设性

## 许可证

贡献的代码将采用与项目相同的 MIT 许可证。

---

感谢你的贡献！ 🎉
