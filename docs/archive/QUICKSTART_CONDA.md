# ⚡ 5分钟快速启动（Conda）

## 简化版流程

### 步骤 1-3: 环境设置（一次性）

```bash
# 1. 创建 Conda 环境
conda create -n markdown_tracker python=3.11 -y

# 2. 激活环境
conda activate markdown_tracker

# 3. 安装依赖
pip install -r requirements.txt
```

**验证**:
```bash
python --version          # 应该显示 Python 3.11.x
pip list | grep openai    # 应该显示 openai 1.x.x
```

---

### 步骤 4: 一键快速启动

#### 方式 A: 自动化脚本（推荐）

**Windows (PowerShell)**:
```bash
.\quick_start.ps1
```

**Windows (CMD)**:
```bash
quick_start.bat
```

**Linux/Mac**:
```bash
bash test.sh
```

#### 方式 B: 手动快速启动

```bash
# 1. 激活环境
conda activate markdown_tracker

# 2. 配置 API Key（一次性）
cp .env.example .env
# 编辑 .env，填入你的 OPENAI_API_KEY

# 3. 初始化数据库
python main.py --init

# 4. 快速测试（跳过 LLM，~3秒）
python main.py --skip-extraction

# 预期看到:
#   - 扫描到 2 个文档
#   - 生成 2 个 chunks
#   - 输出文件已创建

# 5. 查看结果
cat output/status.md
```

---

## 阶段性测试

### 测试 A: 快速测试（~3 秒，无需 API Key）

```bash
conda activate markdown_tracker
python main.py --skip-extraction
```

**验证项**:
- [ ] 输出 "处理完成!"
- [ ] output/status.md 已创建
- [ ] data/state.db 已创建

---

### 测试 B: 完整测试（~20 秒，需要 API Key）

```bash
conda activate markdown_tracker

# 确保 .env 已配置
python main.py --init
python main.py

# 监听输出，应该看到:
# [1/2] chunk xxx: 5 实体, 3 状态候选
# [2/2] chunk yyy: 4 实体, 2 状态候选
```

**验证项**:
- [ ] LLM 成功调用（看到实体和状态候选数量）
- [ ] 没有 API 错误
- [ ] 抽取结果保存到数据库

---

### 测试 C: 数据验证

```bash
# 查看统计
python main.py --stats

# 查看数据库内容
sqlite3 data/state.db "SELECT COUNT(*) as docs FROM documents;"
sqlite3 data/state.db "SELECT COUNT(*) as chunks FROM chunks;"
sqlite3 data/state.db "SELECT COUNT(*) as extracts FROM extractions;"
```

---

## 👉 立即开始（复制粘贴）

### Windows PowerShell

```powershell
# 1. 创建环境
conda create -n markdown_tracker python=3.11 -y

# 2. 激活
conda activate markdown_tracker

# 3. 安装依赖
pip install -r requirements.txt

# 4. 快速启动脚本
.\quick_start.ps1
```

### Windows CMD

```cmd
REM 1. 创建环境
conda create -n markdown_tracker python=3.11 -y

REM 2. 激活
conda activate markdown_tracker

REM 3. 安装依赖
pip install -r requirements.txt

REM 4. 快速启动脚本
quick_start.bat
```

### Linux/Mac

```bash
# 1. 创建环境
conda create -n markdown_tracker python=3.11 -y

# 2. 激活
conda activate markdown_tracker

# 3. 安装依赖
pip install -r requirements.txt

# 4. 快速启动脚本
bash test.sh
```

---

## 📊 测试进度跟踪

| 阶段 | 命令 | 耗时 | API Key | 
|------|------|------|---------|
| **1️⃣ 环境** | `conda create ...` | 2-5 分钟 | ❌ | 
| **2️⃣ 激活** | `conda activate ...` | 1 秒 | ❌ | 
| **3️⃣ 依赖** | `pip install ...` | 30 秒 | ❌ | 
| **4️⃣ 快速测试** | `python main.py --skip-extraction` | 3 秒 | ❌ | 
| **5️⃣ 配置 API** | 编辑 `.env` | 1 分钟 | ✅ | 
| **6️⃣ 完整测试** | `python main.py` | 20 秒 | ✅ | 
| **7️⃣ 验证** | `python main.py --stats` | 1 秒 | ❌ | 

---

## 🆘 快速故障排查

### 环境问题

```bash
# 检查 Conda 版本
conda --version

# 查看所有环境
conda info --envs

# 删除并重建环境
conda remove -n markdown_tracker --all -y
conda create -n markdown_tracker python=3.11 -y
conda activate markdown_tracker
pip install -r requirements.txt
```

### 依赖问题

```bash
# 重新安装依赖
pip install --upgrade -r requirements.txt

# 清除缓存
pip cache purge
pip install -r requirements.txt
```

### 测试运行失败

```bash
# 检查 Python 版本
python --version

# 检查模块
python -c "import openai; print('OK')"
python -c "from dotenv import load_dotenv; print('OK')"

# 重新初始化数据库
python main.py --init

# 查看错误详情
python main.py 2>&1 | tee debug.log
```

### API Key 问题

```bash
# 检查 .env 是否存在
ls .env

# 检查 API Key 格式
python -c "import os; from dotenv import load_dotenv; load_dotenv(); k=os.getenv('OPENAI_API_KEY'); print(f'Key: {k[:10]}...' if k else 'NOT SET')"
```

---

## 📈 预期结果

### 快速测试（--skip-extraction）

```
✓ 文档数: 2
✓ Chunks 数: 2
✓ 输出文件: output/status.md
✓ 运行时间: 2-3 秒
```

### 完整测试（含 LLM）

```
✓ 文档数: 2
✓ Chunks 数: 2
✓ Extractions 数: 2
✓ 实体总数: 9+
✓ 状态候选: 5+
✓ 运行时间: 15-30 秒
✓ 成本: ~$0.005
```

---

## ✨ 完成标记

- [ ] 环境创建成功
- [ ] 依赖安装成功
- [ ] 快速测试通过 ✅
- [ ] API Key 已配置 ⭐
- [ ] 完整测试通过 ✨
- [ ] 数据验证成功 📊

---

## 🎓 后续学习

完整测试通过后，阅读以下文档：

1. **架构理解**: `CLAUDE.md` (中文) 或 `README.md` (英文)
2. **详细测试**: `TESTING.md` - 全面的故障排查
3. **完整指南**: `CONDA_SETUP.md` - 详细的逐步说明
4. **改进计划**: `PLAN.md` - 了解后续任务

---

## 💬 常见问题

**Q: 快速启动脚本不工作？**
A: 使用手动步骤，看看具体是哪一步失败了。

**Q: 需要 API Key 吗？**
A: 快速测试不需要，完整测试需要。

**Q: 为什么状态项为 0？**
A: 因为聚合逻辑还未实现（PLAN.md 任务 2）。

**Q: 能增加输入文件吗？**
A: 可以，在 `input_docs/` 中添加 .md 文件，再运行 `python main.py`。

---

**现在就开始吧！** 🚀

选择你的平台上面的快速启动方式，然后跟着步骤走。

预期耗时: **5-10 分钟**（取决于网络）
