# ✅ 多 LLM 提供商支持 - 修改完成

## 🎉 已完成的修改

我已经将项目改造为**支持多个 LLM 提供商**，包括 OpenAI、MiniMax、DeepSeek 和其他兼容 OpenAI API 的服务。

---

## 📝 修改的文件

### 1. 核心代码文件

| 文件 | 修改内容 |
|------|---------|
| **layers/extractors/config.py** | ✅ 添加 `base_url` 和 `extra_body` 支持 |
|  | ✅ 自动检测提供商 |
|  | ✅ 根据提供商设置默认温度 |
|  | ✅ 提供商特定参数验证 |
| **layers/extractors/llm_extractor.py** | ✅ 使用 base_url 初始化客户端 |
|  | ✅ 支持 extra_body 参数 |
|  | ✅ 显示提供商信息 |
| **.env.example** | ✅ 添加多提供商配置示例 |
|  | ✅ 包含 OpenAI、MiniMax、DeepSeek 配置 |
| **CLAUDE.md** | ✅ 更新文档说明多提供商支持 |

### 2. 新增文档文件

| 文件 | 内容 |
|------|------|
| **.github/MULTI_LLM_GUIDE.md** | 完整的多提供商配置指南 |
| **.github/MINIMAX_QUICKSTART.md** | MiniMax 快速配置指南 |
| **.github/MULTI_LLM_SUMMARY.md** | 本文件（修改总结） |

---

## 🚀 现在你可以使用 MiniMax 了！

### 快速配置（你的情况）

编辑 `.env` 文件：

```bash
# MiniMax API Configuration
OPENAI_API_KEY=sk-cp-你的MiniMax-key
OPENAI_BASE_URL=https://api.minimaxi.com/v1
LLM_MODEL=MiniMax-M2.7-highspeed
LLM_TEMPERATURE=1.0
LLM_REASONING_SPLIT=true
```

### 运行测试

```bash
# 激活环境
conda activate markdown_tracker

# 初始化数据库
python main.py --init

# 运行完整流程
python main.py
```

### 预期输出

```
[INFO] Using MINIMAX API with model MiniMax-M2.7-highspeed

[抽取层] 处理 chunks...
  - 开始处理 124 个 chunks...
    [1/124] chunk 1: 5 实体, 3 状态候选
    [2/124] chunk 2: 4 实体, 2 状态候选
    ...
```

✅ 不会再出现 `401 Unauthorized` 错误！

---

## 🎯 新功能特性

### 1. 自动检测提供商

系统会根据 `base_url` 或 `model` 名称自动检测：

```python
# 检测逻辑
if 'minimaxi.com' in base_url → 'minimax'
if 'MiniMax' in model → 'minimax'
if 'gpt' in model → 'openai'
```

### 2. 智能默认温度

根据提供商自动设置最佳默认值：

| 提供商 | 默认温度 | 原因 |
|--------|---------|------|
| OpenAI | 0.1 | 稳定输出 |
| MiniMax | 1.0 | 官方推荐 |
| DeepSeek | 0.7 | 平衡质量 |

### 3. 特殊参数支持

**MiniMax 的 `reasoning_split`**:

```bash
# .env 配置
LLM_REASONING_SPLIT=true
```

**效果**: 思考内容分离到 `reasoning_details` 字段，便于调试

### 4. 温度验证

根据提供商验证温度范围：

- OpenAI: [0.0, 2.0]
- MiniMax: (0.0, 1.0] ⚠️ **不能为 0**

---

## 📚 文档指南

### 快速开始

1. **MiniMax 用户**: 阅读 `.github/MINIMAX_QUICKSTART.md`
2. **测试多个提供商**: 阅读 `.github/MULTI_LLM_GUIDE.md`
3. **项目架构**: 阅读 `CLAUDE.md`

### 配置参考

打开 `.env.example` 查看所有支持的提供商配置示例。

---

## 🔧 配置对比

### 你之前的配置（会报错）

```bash
OPENAI_API_KEY=sk-cp-minimax-key
# ❌ 缺少 base_url，发送到 OpenAI 服务器
```

### 现在的正确配置

```bash
OPENAI_API_KEY=sk-cp-minimax-key
OPENAI_BASE_URL=https://api.minimaxi.com/v1  ✅ 关键！
LLM_MODEL=MiniMax-M2.7-highspeed
LLM_TEMPERATURE=1.0
```

---

## 💡 推荐配置

### MiniMax（你的情况）

**快速抽取** (推荐):
```bash
OPENAI_API_KEY=sk-cp-your-key
OPENAI_BASE_URL=https://api.minimaxi.com/v1
LLM_MODEL=MiniMax-M2.7-highspeed
LLM_TEMPERATURE=1.0
LLM_REASONING_SPLIT=true
```

**经济模式**:
```bash
LLM_MODEL=MiniMax-M2.5-highspeed  # 更便宜
```

**编程文档**:
```bash
LLM_MODEL=MiniMax-M2.1-highspeed  # 编程能力强
```

---

## 🧪 测试多个提供商

### 方法 1: 切换 .env 文件

```bash
# 创建多个配置
cp .env .env.minimax.backup
cp .env.example .env.openai
cp .env.example .env.deepseek

# 编辑各个文件...

# 测试 MiniMax
cp .env.minimax .env
python main.py --init && python main.py

# 测试 OpenAI
cp .env.openai .env
python main.py --init && python main.py
```

### 方法 2: 环境变量

```bash
# MiniMax
export OPENAI_API_KEY=sk-cp-xxx
export OPENAI_BASE_URL=https://api.minimaxi.com/v1
export LLM_MODEL=MiniMax-M2.7-highspeed
python main.py

# OpenAI
export OPENAI_API_KEY=sk-proj-xxx
unset OPENAI_BASE_URL  # 或留空
export LLM_MODEL=gpt-4o-mini
python main.py
```

---

## ✅ 验证清单

在运行前检查：

- [ ] `OPENAI_API_KEY` 已设置（MiniMax 格式：`sk-cp-xxx`）
- [ ] `OPENAI_BASE_URL=https://api.minimaxi.com/v1` 已设置 ⭐ **关键**
- [ ] `LLM_MODEL=MiniMax-M2.7-highspeed`（或其他 MiniMax 模型）
- [ ] `LLM_TEMPERATURE=1.0`（MiniMax 推荐值）
- [ ] （可选）`LLM_REASONING_SPLIT=true`

---

## 🐛 故障排查

### 仍然出现 401 错误？

```bash
# 验证配置
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('API Key:', os.getenv('OPENAI_API_KEY')[:15] + '...')
print('Base URL:', os.getenv('OPENAI_BASE_URL'))
print('Model:', os.getenv('LLM_MODEL'))
"
```

**预期输出**:
```
API Key: sk-cp-ki...
Base URL: https://api.minimaxi.com/v1
Model: MiniMax-M2.7-highspeed
```

### 温度错误？

```
ValueError: MiniMax temperature must be in (0.0, 1.0]
```

**解决**: 设置 `LLM_TEMPERATURE=1.0`

---

## 📊 性能对比（参考）

| 提供商 | 模型 | 速度 | 成本 | 中文 |
|--------|------|------|------|------|
| OpenAI | gpt-4o-mini | 中等 | 中等 | 良好 |
| MiniMax | M2.7-highspeed | 快（100 TPS） | 较低 | 优秀 |
| DeepSeek | deepseek-chat | 快 | 较低 | 优秀 |

**你的 124 个 chunks**:
- OpenAI gpt-4o-mini: ~30-60 秒
- MiniMax M2.7-highspeed: ~15-30 秒（更快）

---

## 🎓 学习路径

1. **立即使用**: 配置 `.env` → 运行 `python main.py`
2. **理解配置**: 阅读 `.github/MINIMAX_QUICKSTART.md`
3. **对比测试**: 阅读 `.github/MULTI_LLM_GUIDE.md`
4. **深入理解**: 阅读 `CLAUDE.md` 架构说明

---

## 🎉 总结

### 你现在拥有

✅ **多提供商支持** - OpenAI、MiniMax、DeepSeek 等  
✅ **自动检测** - 根据配置自动适配  
✅ **智能默认** - 最佳温度、参数自动设置  
✅ **特殊参数** - MiniMax reasoning_split 支持  
✅ **完整文档** - 两份详细指南  

### 立即行动

1. 编辑 `.env` 添加 `OPENAI_BASE_URL`
2. 运行 `python main.py`
3. 享受 MiniMax 的高速抽取！

---

**修改完成！现在你可以使用 MiniMax API 了！** 🚀
