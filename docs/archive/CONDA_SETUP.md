# Conda 虚拟环境 + 全流程测试指南

## 📋 完整步骤流程

```
步骤 1: 创建 Conda 环境
    ↓
步骤 2: 激活环境
    ↓
步骤 3: 安装依赖
    ↓
步骤 4: 验证导入
    ↓
步骤 5: 配置 API Key
    ↓
步骤 6: 快速测试（跳过 LLM）
    ↓
步骤 7: 完整测试（含 LLM）
    ↓
步骤 8: 验证所有层级
    ↓
完成！✅
```

---

## 🔧 详细步骤

### 步骤 1: 创建 Conda 虚拟环境

#### 检查 Conda 是否已安装
```bash
conda --version
```

**预期输出**:
```
conda 24.1.2  (或其他版本号)
```

如果未安装，请先安装 Miniconda 或 Anaconda。

#### 创建环境（Python 3.9+）
```bash
# 创建名为 markdown_tracker 的环境
conda create -n markdown_tracker python=3.11 -y

# 或指定具体 Python 版本（推荐 3.9+）
# conda create -n markdown_tracker python=3.9 -y
```

**预期输出**:
```
Collecting package metadata (current_repodata.json)
Solving environment: done
...
Preparing transaction: done
Verifying transaction: done
Executing transaction: done

To activate this environment, use
     conda activate markdown_tracker
```

---

### 步骤 2: 激活虚拟环境

```bash
conda activate markdown_tracker
```

**验证激活成功**:
```bash
# 命令行前面应该显示 (markdown_tracker)
# 例如: (markdown_tracker) C:\Users\YourName> 

# 验证 Python 版本
python --version

# 验证 pip 位置
pip --version
```

**预期输出**:
```
(markdown_tracker) C:\Users\YourName>python --version
Python 3.11.x

(markdown_tracker) C:\Users\YourName>pip --version
pip 24.x from C:\Users\...\markdown_tracker\lib\site-packages\pip (python 3.11)
```

---

### 步骤 3: 安装依赖

#### 方法 A: 使用 requirements.txt（推荐）

```bash
# 进入项目目录
cd d:\Apps\Python\lab\personal_prompt

# 安装所有依赖
pip install -r requirements.txt
```

**预期输出**:
```
Collecting openai==1.x.x
  Downloading openai-1.x.x-py3-none-any.whl
  ...
Collecting python-dotenv==1.0.0
  Downloading python_dotenv-1.0.0-py2.py3-none-any.whl
  ...
Successfully installed openai-1.x.x python-dotenv-1.0.0
```

#### 方法 B: 逐个安装（如果需要）

```bash
pip install openai
pip install python-dotenv
```

---

### 步骤 4: 验证导入

运行验证脚本检查所有模块是否正确导入：

```bash
python -c "
import sys
print('Python 信息:')
print(f'  版本: {sys.version}')
print(f'  路径: {sys.executable}')
print()

print('验证导入:')
try:
    import openai
    print(f'  ✓ OpenAI 版本: {openai.__version__}')
except ImportError as e:
    print(f'  ✗ OpenAI 错误: {e}')

try:
    from dotenv import load_dotenv
    print('  ✓ python-dotenv OK')
except ImportError as e:
    print(f'  ✗ python-dotenv 错误: {e}')

try:
    import sqlite3
    print('  ✓ SQLite3 OK')
except ImportError as e:
    print(f'  ✗ SQLite3 错误: {e}')

print()
print('项目模块验证:')
sys.path.insert(0, 'd:/Apps/Python/lab/personal_prompt')
try:
    from db import get_connection
    print('  ✓ db 模块 OK')
except ImportError as e:
    print(f'  ✗ db 模块错误: {e}')

try:
    from layers.input_layer import process_input
    print('  ✓ input_layer OK')
except ImportError as e:
    print(f'  ✗ input_layer 错误: {e}')

try:
    from layers.extractors import LLMExtractor
    print('  ✓ extractors OK')
except ImportError as e:
    print(f'  ✗ extractors 错误: {e}')

print()
print('✅ 所有模块检查完成')
"
```

**预期输出**:
```
Python 信息:
  版本: 3.11.x | ...
  路径: C:\Users\...\markdown_tracker\python.exe

验证导入:
  ✓ OpenAI 版本: 1.x.x
  ✓ python-dotenv OK
  ✓ SQLite3 OK

项目模块验证:
  ✓ db 模块 OK
  ✓ input_layer OK
  ✓ extractors OK

✅ 所有模块检查完成
```

如果有 ✗ 错误，说明依赖安装不完整。

---

### 步骤 5: 配置 API Key

#### 5.1 创建 .env 文件

```bash
# 进入项目目录
cd d:\Apps\Python\lab\personal_prompt

# 复制模板
cp .env.example .env
# 或者在 Windows 上使用
# copy .env.example .env
```

#### 5.2 编辑 .env 文件

```bash
# 用文本编辑器打开 .env
# 例如: code .env 或 notepad .env

# 或用 echo 命令添加（不覆盖现有内容）
echo OPENAI_API_KEY=sk-your-actual-key-here >> .env
```

**验证 .env 内容**:
```bash
cat .env
# 或 Windows:
# type .env
```

**预期输出**:
```
# Environment Variables
# Copy this file to .env and fill in your values

# OpenAI API Key (required for LLM extraction)
OPENAI_API_KEY=sk-proj-xxx...
```

#### 5.3 验证 API Key 配置

```bash
python -c "
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')

if api_key:
    print(f'✓ API Key 已配置: {api_key[:10]}...')
else:
    print('✗ API Key 未配置')
"
```

**预期输出**:
```
✓ API Key 已配置: sk-proj-xxx...
```

---

### 步骤 6: 快速测试（跳过 LLM）

**时间**: ~3 秒  
**无需 API Key**: ✓

#### 6.1 初始化数据库

```bash
python main.py --init
```

**预期输出**:
```
强制重新初始化数据库...
完成。
```

**验证**:
```bash
# 检查数据库是否已创建
ls data/state.db
# 或 Windows: dir data\state.db
```

**预期输出**:
```
data/state.db
```

#### 6.2 运行快速测试

```bash
python main.py --skip-extraction
```

**预期输出**:
```
==================================================
初始化数据库...

[输入层] 扫描文档...
  - 扫描到 2 个文档
  - 新增: 2, 修改: 0
    [✓] test_extraction.md -> 1 chunks
    [✓] test_note.md -> 1 chunks

[抽取层] 处理 chunks...
  - 跳过抽取（--skip-extraction）

[中间层] 当前状态:
  - 文档数: 2
  - Chunk 数: 2
  - 已抽取: 0
  - 待抽取 chunks: 2
  - 活跃状态项: 0

[输出层] 生成状态文档...
  - 输出文件: d:\Apps\Python\lab\personal_prompt\output\status.md
  - 状态项数: 0
  - 快照 ID: 1

==================================================
处理完成!
```

#### 6.3 验证快速测试结果

检查各个环节：

```bash
# 1. 检查输出文件
cat output/status.md

# 2. 查看数据库统计
python main.py --stats

# 3. 查看具体表内容
sqlite3 data/state.db "SELECT COUNT(*) as documents FROM documents;"
sqlite3 data/state.db "SELECT COUNT(*) as chunks FROM chunks;"
```

**预期输出**:

```
# output/status.md - Markdown 格式的状态文档
# 当前没有状态项（因为还未聚合），所以只有骨架

# --stats 输出
当前状态:
  documents: 2
  chunks: 2
  extractions: 0
  active_states: 0
  archived_states: 0
  
# 数据库查询
documents: 2
chunks: 2
```

✅ **快速测试通过！** 所有基础流程都工作正常。

---

### 步骤 7: 完整测试（含 LLM 抽取）

**时间**: 15-30 秒  
**需要 API Key**: ✓

#### 7.1 重新初始化数据库

```bash
python main.py --init
```

#### 7.2 运行完整流程

```bash
python main.py
```

**预期输出**（首次 ~20-30 秒）:

```
==================================================
初始化数据库...

[输入层] 扫描文档...
  - 扫描到 2 个文档
  - 新增: 2, 修改: 0
    [✓] test_extraction.md -> 1 chunks
    [✓] test_note.md -> 1 chunks

[抽取层] 处理 chunks...
  - 开始处理 2 个 chunks...
    [1/2] chunk xxx: 5 实体, 3 状态候选
    [2/2] chunk yyy: 4 实体, 2 状态候选

[中间层] 当前状态:
  - 文档数: 2
  - Chunk 数: 2
  - 已抽取: 2
  - 待抽取 chunks: 0
  - 活跃状态项: 0

[输出层] 生成状态文档...
  - 输出文件: d:\Apps\Python\lab\personal_prompt\output\status.md
  - 状态项数: 0
  - 快照 ID: 1

==================================================
处理完成!
```

#### 7.3 验证 LLM 抽取结果

检查数据库中的抽取结果：

```bash
# 查看抽取表统计
sqlite3 data/state.db "SELECT COUNT(*) as extractions FROM extractions;"

# 查看某个抽取的详细内容
sqlite3 data/state.db "SELECT extraction_json FROM extractions WHERE id=1;" | python -m json.tool
```

**预期输出**:
```
extractions: 2

# JSON 格式的抽取结果
{
  "context": {
    "document_title": "2024年3月学习笔记",
    ...
  },
  "entities": [
    {
      "text": "Rust",
      "type": "technology",
      "confidence": 0.95
    },
    {
      "text": "FastAPI",
      "type": "technology",
      "confidence": 0.92
    },
    ...
  ],
  "events": [
    {
      "description": "学习 Rust",
      "time": {
        "normalized": "2024-03-xx",
        "source": "document_context"
      },
      "confidence": 0.88
    }
  ],
  "state_candidates": [
    {
      "summary": "正在学习 Rust",
      "category": "learning",
      "confidence": 0.90
    },
    ...
  ],
  ...
}
```

✅ **完整测试通过！** LLM 抽取工作正常。

---

### 步骤 8: 验证所有层级

创建一个综合验证脚本，检查每一层的输出：

```bash
python -c "
import sqlite3
import json
from pathlib import Path

print('=' * 50)
print('完整系统验证')
print('=' * 50)

# 连接数据库
conn = sqlite3.connect('data/state.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 1. 输入层验证
print('\n[1️⃣ 输入层验证]')
cursor.execute('SELECT COUNT(*) as cnt FROM documents')
doc_count = cursor.fetchone()['cnt']
print(f'  ✓ 文档数: {doc_count}')

cursor.execute('SELECT COUNT(*) as cnt FROM chunks')
chunk_count = cursor.fetchone()['cnt']
print(f'  ✓ Chunks 数: {chunk_count}')

cursor.execute('SELECT id, path FROM documents LIMIT 3')
print('  📄 文档列表:')
for row in cursor.fetchall():
    print(f'    - {row[\"path\"]}')

# 2. 中间层验证
print('\n[2️⃣ 中间层验证]')
cursor.execute('SELECT COUNT(*) as cnt FROM extractions')
ext_count = cursor.fetchone()['cnt']
print(f'  ✓ Extractions 数: {ext_count}')

if ext_count > 0:
    cursor.execute('SELECT extractor_type, COUNT(*) as cnt FROM extractions GROUP BY extractor_type')
    print('  📊 抽取器分布:')
    for row in cursor.fetchall():
        print(f'    - {row[\"extractor_type\"]}: {row[\"cnt\"]}')
    
    # 显示某个抽取的摘要
    cursor.execute('SELECT extraction_json FROM extractions LIMIT 1')
    first_ext = cursor.fetchone()['extraction_json']
    ext_json = json.loads(first_ext)
    entity_cnt = len(ext_json.get('entities', []))
    state_cnt = len(ext_json.get('state_candidates', []))
    event_cnt = len(ext_json.get('events', []))
    print(f'  📈 首个抽取摘要:')
    print(f'    - 实体数: {entity_cnt}')
    print(f'    - 事件数: {event_cnt}')
    print(f'    - 状态候选: {state_cnt}')

# 3. 状态层验证
print('\n[3️⃣ 状态层验证]')
cursor.execute('SELECT COUNT(*) as cnt FROM states')
state_count = cursor.fetchone()['cnt']
print(f'  ✓ 状态项数: {state_count}')
if state_count > 0:
    cursor.execute('SELECT category, COUNT(*) as cnt FROM states GROUP BY category')
    print('  📂 状态分类:')
    for row in cursor.fetchall():
        print(f'    - {row[\"category\"]}: {row[\"cnt\"]}')

# 4. 输出层验证
print('\n[4️⃣ 输出层验证]')
if Path('output/status.md').exists():
    size = Path('output/status.md').stat().st_size
    print(f'  ✓ 输出文件存在')
    print(f'    大小: {size} 字节')
    with open('output/status.md') as f:
        lines = len(f.readlines())
    print(f'    行数: {lines}')
else:
    print('  ✗ 输出文件不存在')

cursor.execute('SELECT COUNT(*) as cnt FROM output_snapshots')
snapshot_cnt = cursor.fetchone()['cnt']
print(f'  ✓ 输出快照数: {snapshot_cnt}')

print('\n' + '=' * 50)
print('✅ 验证完成')
print('=' * 50)

conn.close()
"
```

**预期输出**:
```
==================================================
完整系统验证
==================================================

[1️⃣ 输入层验证]
  ✓ 文档数: 2
  ✓ Chunks 数: 2
  📄 文档列表:
    - input_docs/test_extraction.md
    - input_docs/test_note.md

[2️⃣ 中间层验证]
  ✓ Extractions 数: 2
  📊 抽取器分布:
    - llm: 2
  📈 首个抽取摘要:
    - 实体数: 5
    - 事件数: 3
    - 状态候选: 2

[3️⃣ 状态层验证]
  ✓ 状态项数: 0
  (注: 因为还未实现聚合逻辑，所以为 0)

[4️⃣ 输出层验证]
  ✓ 输出文件存在
    大小: 1234 字节
    行数: 45
  ✓ 输出快照数: 1

==================================================
✅ 验证完成
==================================================
```

---

## 🎯 常见问题与解决

### 问题 1: Conda 环境激活后 pip 找不到

**症状**:
```
'pip' 不是内部或外部命令
```

**解决**:
```bash
# 重新激活环境
conda deactivate
conda activate markdown_tracker

# 或在 Windows 上使用完整路径
C:\Users\...\markdown_tracker\Scripts\pip install -r requirements.txt
```

---

### 问题 2: Python 版本不兼容

**症状**:
```
ERROR: Package X requires Python <3.9 but you have 3.8
```

**解决**:
```bash
# 创建新环境使用 Python 3.11
conda create -n markdown_tracker python=3.11 -y
conda activate markdown_tracker
pip install -r requirements.txt
```

---

### 问题 3: OpenAI 导入失败

**症状**:
```
ModuleNotFoundError: No module named 'openai'
```

**解决**:
```bash
# 确保在正确的环境中
conda activate markdown_tracker

# 重新安装
pip install --upgrade openai

# 验证
python -c "import openai; print(openai.__version__)"
```

---

### 问题 4: API Key 识别不了

**症状**:
```
OpenAI API Error: 401 Unauthorized
```

**解决**:
```bash
# 检查 .env 文件
cat .env

# 检查 API Key 格式
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv('OPENAI_API_KEY')
print(f'Key type: {type(key)}')
print(f'Key starts with sk-: {str(key).startswith(\"sk-\") if key else False}')
"

# 确保 .env 文件在项目根目录
cd d:\Apps\Python\lab\personal_prompt
python main.py
```

---

### 问题 5: SQLite 数据库锁定

**症状**:
```
sqlite3.OperationalError: database is locked
```

**解决**:
```bash
# 等待 1-2 秒后重试
sleep 2
python main.py

# 或删除旧数据库重新开始
rm data/state.db
python main.py --init
python main.py
```

---

## 📊 性能基准

运行以下命令收集性能数据：

```bash
# 时间测量脚本
python -c "
import time
import subprocess

print('性能基准测试')
print('=' * 50)

# 测试 1: 快速模式
print('\n[测试 1] 快速模式（--skip-extraction）')
subprocess.run(['python', 'main.py', '--init'], capture_output=True)
start = time.time()
result = subprocess.run(['python', 'main.py', '--skip-extraction'], capture_output=True, text=True)
elapsed = time.time() - start
print(f'  耗时: {elapsed:.2f} 秒')
print(f'  返回码: {result.returncode}')

# 测试 2: 完整模式
print('\n[测试 2] 完整模式（含 LLM）')
subprocess.run(['python', 'main.py', '--init'], capture_output=True)
start = time.time()
result = subprocess.run(['python', 'main.py'], capture_output=True, text=True)
elapsed = time.time() - start
print(f'  耗时: {elapsed:.2f} 秒')
print(f'  返回码: {result.returncode}')

print('\n' + '=' * 50)
"
```

---

## ✅ 完整测试清单

运行此清单确保所有功能正常：

```bash
# 创建新文件 test_checklist.sh
cat > test_checklist.sh << 'EOF'
#!/bin/bash

echo "Markdown State Tracker - 完整测试清单"
echo "========================================"

# 1. 环境检查
echo ""
echo "[ ] 1. 环境激活检查"
if [[ $CONDA_DEFAULT_ENV == "markdown_tracker" ]]; then
    echo "  ✓ Conda 环境已激活: $CONDA_DEFAULT_ENV"
else
    echo "  ✗ Conda 环境未激活。请运行: conda activate markdown_tracker"
    exit 1
fi

# 2. 依赖检查
echo ""
echo "[ ] 2. 依赖安装检查"
python -c "import openai" && echo "  ✓ OpenAI 已安装" || echo "  ✗ OpenAI 未安装"
python -c "from dotenv import load_dotenv" && echo "  ✓ python-dotenv 已安装" || echo "  ✗ python-dotenv 未安装"

# 3. 配置检查
echo ""
echo "[ ] 3. 配置文件检查"
if [ -f ".env" ]; then
    echo "  ✓ .env 文件存在"
    if grep -q "OPENAI_API_KEY" .env; then
        echo "  ✓ API Key 已配置"
    else
        echo "  ⚠ API Key 未配置（可选）"
    fi
else
    echo "  ⚠ .env 文件不存在（快速测试可跳过）"
fi

# 4. 快速测试
echo ""
echo "[ ] 4. 快速测试运行"
python main.py --init > /tmp/init.log 2>&1
python main.py --skip-extraction > /tmp/fast_test.log 2>&1
if grep -q "处理完成" /tmp/fast_test.log; then
    echo "  ✓ 快速测试通过"
else
    echo "  ✗ 快速测试失败"
    echo "  输出:"
    cat /tmp/fast_test.log
    exit 1
fi

# 5. 统计检查
echo ""
echo "[ ] 5. 统计信息检查"
python main.py --stats > /tmp/stats.log 2>&1
if grep -q "documents:" /tmp/stats.log; then
    echo "  ✓ 统计信息正常"
    cat /tmp/stats.log | grep -E "^\s*(documents|chunks|extractions):" | sed 's/^/    /'
else
    echo "  ✗ 统计信息错误"
fi

# 6. 数据库检查
echo ""
echo "[ ] 6. 数据库检查"
doc_count=$(sqlite3 data/state.db "SELECT COUNT(*) FROM documents;" 2>/dev/null || echo "0")
chunk_count=$(sqlite3 data/state.db "SELECT COUNT(*) FROM chunks;" 2>/dev/null || echo "0")
echo "  ✓ 数据库连接正常"
echo "    - 文档数: $doc_count"
echo "    - Chunks 数: $chunk_count"

# 7. 输出文件检查
echo ""
echo "[ ] 7. 输出文件检查"
if [ -f "output/status.md" ]; then
    lines=$(wc -l < output/status.md)
    echo "  ✓ 输出文件存在 ($lines 行)"
else
    echo "  ✗ 输出文件不存在"
fi

echo ""
echo "========================================"
echo "✅ 所有检查完成！"
echo "========================================"
EOF

# 运行测试清单
bash test_checklist.sh
```

---

## 🚀 下一步

完整测试通过后，你可以：

1. **添加更多输入文档**
   ```bash
   # 在 input_docs/ 中添加更多 .md 文件
   # 再运行 python main.py
   ```

2. **查看聚合逻辑实现**（下一个任务）
   ```bash
   # 见 PLAN.md 任务 2
   ```

3. **添加单元测试**（任务 3）
   ```bash
   # 见 PLAN.md 任务 3
   ```

---

## 📞 获取帮助

如果遇到问题：

1. 查看 `TESTING.md` 的详细故障排查
2. 查看 `GETTING_STARTED.md` 的快速开始
3. 查看 `CLAUDE.md` 了解项目架构

---

**祝你测试顺利！** 🎉
