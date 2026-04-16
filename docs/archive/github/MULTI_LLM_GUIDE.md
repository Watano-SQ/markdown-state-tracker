# 多 LLM 提供商配置指南

本项目支持多个 LLM 提供商，包括 OpenAI、MiniMax、DeepSeek 和其他兼容 OpenAI API 的服务。

---

## 🎯 快速配置

### 步骤 1: 选择你的提供商

从下面选择一个提供商，复制对应的配置到 `.env` 文件。

### 步骤 2: 填入 API Key

将 `your-key-here` 替换为你的实际 API Key。

### 步骤 3: 测试

```bash
python main.py --init
python main.py
```

---

## 📋 提供商配置

### 1️⃣ OpenAI（默认）

**特点**: 稳定、文档完善、生态丰富

**配置** (`.env`):
```bash
OPENAI_API_KEY=sk-your-openai-key-here
# OPENAI_BASE_URL 不需要设置（使用默认）
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.1
```

**推荐模型**:
- `gpt-4o-mini` - 快速且便宜（推荐用于开发）
- `gpt-4o` - 强大的性能
- `gpt-4-turbo` - 平衡性能和成本

**成本**:
- gpt-4o-mini: ~$0.15/1M input tokens

**温度范围**: 0.0 - 2.0（推荐 0.1-0.7）

---

### 2️⃣ MiniMax（国产）⭐

**特点**: 高速、支持中文、性价比高

**配置** (`.env`):
```bash
OPENAI_API_KEY=sk-cp-your-minimax-key-here
OPENAI_BASE_URL=https://api.minimaxi.com/v1
LLM_MODEL=MiniMax-M2.7-highspeed
LLM_TEMPERATURE=1.0
LLM_REASONING_SPLIT=true
```

**推荐模型**:
- `MiniMax-M2.7-highspeed` - 极速版（100 TPS，推荐）
- `MiniMax-M2.7` - 标准版（60 TPS）
- `MiniMax-M2.5-highspeed` - 性价比高（100 TPS）
- `MiniMax-M2.5` - 经济版（60 TPS）

**成本**: 参考 MiniMax 官网定价

**温度范围**: (0.0, 1.0]（**推荐 1.0**）

**特殊参数**:
- `LLM_REASONING_SPLIT=true` - 分离思考内容到 `reasoning_details` 字段（推荐启用）

**注意事项**:
1. 温度必须 > 0.0 且 <= 1.0
2. `n` 参数仅支持 1
3. 部分 OpenAI 参数会被忽略（如 `presence_penalty`）

**获取 API Key**: https://platform.minimaxi.com/

---

### 3️⃣ DeepSeek（国产）

**特点**: 编程能力强、推理能力强

**配置** (`.env`):
```bash
OPENAI_API_KEY=sk-your-deepseek-key-here
OPENAI_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_TEMPERATURE=0.7
```

**推荐模型**:
- `deepseek-chat` - 通用对话
- `deepseek-coder` - 代码生成和理解

**温度范围**: 0.0 - 2.0（推荐 0.7）

**获取 API Key**: https://platform.deepseek.com/

---

### 4️⃣ 其他兼容 OpenAI 的服务

**支持的服务**:
- 阿里云百炼
- 腾讯混元
- 智谱 AI (GLM)
- 本地部署的 vLLM/Ollama（通过 OpenAI 兼容接口）

**通用配置**:
```bash
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://your-provider.com/v1
LLM_MODEL=your-model-name
LLM_TEMPERATURE=0.5
```

**注意**: 确认提供商支持 `response_format={"type": "json_object"}`

---

## 🔧 高级配置

### 环境变量完整列表

| 环境变量 | 说明 | 默认值 | 示例 |
|---------|------|--------|------|
| `OPENAI_API_KEY` | API Key（必需） | 无 | `sk-xxx` |
| `OPENAI_BASE_URL` | API Base URL | OpenAI 默认 | `https://api.minimaxi.com/v1` |
| `LLM_MODEL` | 模型名称 | `gpt-4o-mini` | `MiniMax-M2.7-highspeed` |
| `LLM_TEMPERATURE` | 温度参数 | 自动检测 | `1.0` |
| `LLM_REASONING_SPLIT` | MiniMax 思考分离 | `true` | `true/false` |

### 自动检测机制

系统会根据 `LLM_MODEL` 或 `OPENAI_BASE_URL` 自动检测提供商，并设置最佳默认值：

| 提供商 | 自动检测依据 | 默认温度 |
|--------|-------------|---------|
| OpenAI | `gpt` 在模型名中 | 0.1 |
| MiniMax | `MiniMax` 在模型名或 URL 中 | 1.0 |
| DeepSeek | `deepseek` 在模型名或 URL 中 | 0.7 |

---

## 📊 提供商对比

| 特性 | OpenAI | MiniMax | DeepSeek |
|------|--------|---------|----------|
| **速度** | 中等 | 快（100 TPS） | 快 |
| **中文支持** | 良好 | 优秀 | 优秀 |
| **成本** | 中等 | 较低 | 较低 |
| **稳定性** | 极高 | 高 | 高 |
| **特色** | 生态丰富 | 高速、reasoning | 编程强 |
| **推荐场景** | 通用 | 中文、快速抽取 | 代码分析 |

---

## 🧪 测试不同提供商

### 方法 1: 环境变量切换

```bash
# 测试 OpenAI
export OPENAI_API_KEY=sk-openai-key
export OPENAI_BASE_URL=  # 留空或不设置
export LLM_MODEL=gpt-4o-mini
python main.py

# 测试 MiniMax
export OPENAI_API_KEY=sk-cp-minimax-key
export OPENAI_BASE_URL=https://api.minimaxi.com/v1
export LLM_MODEL=MiniMax-M2.7-highspeed
python main.py
```

### 方法 2: 多个 .env 文件

```bash
# 创建多个配置文件
.env.openai
.env.minimax
.env.deepseek

# 切换使用
cp .env.minimax .env
python main.py
```

### 方法 3: 代码级配置（高级）

```python
from layers.extractors import LLMExtractor
from layers.extractors.config import ExtractorConfig

# OpenAI 配置
openai_config = ExtractorConfig(
    api_key="sk-openai-key",
    model="gpt-4o-mini",
    temperature=0.1
)
openai_extractor = LLMExtractor(openai_config)

# MiniMax 配置
minimax_config = ExtractorConfig(
    api_key="sk-cp-minimax-key",
    base_url="https://api.minimaxi.com/v1",
    model="MiniMax-M2.7-highspeed",
    temperature=1.0,
    extra_body={"reasoning_split": True}
)
minimax_extractor = LLMExtractor(minimax_config)

# 对比测试
result_openai = openai_extractor.extract(text, context)
result_minimax = minimax_extractor.extract(text, context)
```

---

## 🐛 故障排查

### 错误 1: `401 Unauthorized`

**原因**: API Key 不正确或发送到错误的服务器

**解决**:
1. 检查 `OPENAI_API_KEY` 是否正确
2. 检查 `OPENAI_BASE_URL` 是否匹配提供商
3. 确认 API Key 没有过期

```bash
# 验证配置
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('API Key:', os.getenv('OPENAI_API_KEY')[:20] + '...')
print('Base URL:', os.getenv('OPENAI_BASE_URL'))
print('Model:', os.getenv('LLM_MODEL'))
"
```

### 错误 2: `Temperature out of range`

**原因**: 不同提供商的温度范围不同

**解决**:
- OpenAI: 0.0 - 2.0
- MiniMax: (0.0, 1.0]
- 设置 `LLM_TEMPERATURE` 在有效范围内

### 错误 3: `Model not found`

**原因**: 模型名称错误或不可用

**解决**:
1. 检查模型名称拼写
2. 确认模型在你的 API 计划中可用
3. 参考上面的"推荐模型"列表

---

## 💡 最佳实践

### 1. 开发阶段

使用快速且便宜的模型：
- OpenAI: `gpt-4o-mini`
- MiniMax: `MiniMax-M2.7-highspeed`

### 2. 生产阶段

根据需求选择：
- **需要稳定**: OpenAI `gpt-4o`
- **需要速度**: MiniMax `MiniMax-M2.7-highspeed`
- **需要成本优化**: MiniMax `MiniMax-M2.5-highspeed`

### 3. 质量对比

运行相同的输入，对比不同提供商的抽取质量：

```bash
# 1. 用 OpenAI 抽取
cp .env.openai .env
python main.py --init
python main.py
sqlite3 data/state.db "SELECT extraction_json FROM extractions LIMIT 1" > openai_result.json

# 2. 用 MiniMax 抽取
cp .env.minimax .env
python main.py --init
python main.py
sqlite3 data/state.db "SELECT extraction_json FROM extractions LIMIT 1" > minimax_result.json

# 3. 对比结果
diff openai_result.json minimax_result.json
```

---

## 📞 获取帮助

### 提供商文档

- **OpenAI**: https://platform.openai.com/docs
- **MiniMax**: https://platform.minimaxi.com/docs
- **DeepSeek**: https://platform.deepseek.com/docs

### 项目文档

- `CLAUDE.md` - 项目架构说明
- `TESTING.md` - 测试指南
- `README.md` - 项目概览

---

**祝你测试顺利！** 🚀

根据测试结果选择最适合你需求的提供商和模型。
