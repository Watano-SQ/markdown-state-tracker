# MiniMax 快速配置指南

## ⚡ 5 分钟配置 MiniMax

### 步骤 1: 获取 API Key

1. 访问 https://platform.minimaxi.com/
2. 注册/登录账号
3. 进入"API 密钥"页面
4. 创建新的 API Key（格式：`sk-cp-xxx...`）

### 步骤 2: 配置 .env 文件

编辑项目根目录的 `.env` 文件：

```bash
# MiniMax API Configuration
OPENAI_API_KEY=sk-cp-your-minimax-key-here
OPENAI_BASE_URL=https://api.minimaxi.com/v1
LLM_MODEL=MiniMax-M2.7-highspeed
LLM_TEMPERATURE=1.0
LLM_REASONING_SPLIT=true
```

### 步骤 3: 运行测试

```bash
# 激活环境
conda activate markdown_tracker

# 初始化数据库
python main.py --init

# 运行完整测试
python main.py
```

**预期输出**:
```
[INFO] Using MINIMAX API with model MiniMax-M2.7-highspeed

[抽取层] 处理 chunks...
  - 开始处理 2 个 chunks...
    [1/2] chunk xxx: 5 实体, 3 状态候选
    [2/2] chunk yyy: 4 实体, 2 状态候选

✓ 处理完成!
```

---

## 🎯 推荐配置

### 快速抽取（推荐）

```bash
LLM_MODEL=MiniMax-M2.7-highspeed
LLM_TEMPERATURE=1.0
LLM_REASONING_SPLIT=true
```

- **速度**: 100 TPS（每秒 100 tokens）
- **质量**: 与标准版相同
- **成本**: 性价比高

### 平衡模式

```bash
LLM_MODEL=MiniMax-M2.5-highspeed
LLM_TEMPERATURE=1.0
```

- **速度**: 100 TPS
- **质量**: 高性价比
- **成本**: 更经济

### 编程优化

```bash
LLM_MODEL=MiniMax-M2.1-highspeed
LLM_TEMPERATURE=1.0
```

- **适用**: 代码分析、技术文档
- **速度**: 100 TPS

---

## 📊 模型对比

| 模型 | 速度 | 特点 | 推荐场景 |
|------|------|------|---------|
| **MiniMax-M2.7-highspeed** ⭐ | 100 TPS | 最新、最快 | 通用抽取（推荐） |
| MiniMax-M2.7 | 60 TPS | 标准版 | 质量优先 |
| MiniMax-M2.5-highspeed | 100 TPS | 性价比高 | 大量文档 |
| MiniMax-M2.5 | 60 TPS | 经济版 | 预算有限 |
| MiniMax-M2.1-highspeed | 100 TPS | 编程能力强 | 代码文档 |

---

## 🔧 特殊参数说明

### reasoning_split（思考分离）

**作用**: 将模型的思考过程分离到 `reasoning_details` 字段

**配置**:
```bash
LLM_REASONING_SPLIT=true
```

**效果**:
```json
{
  "reasoning_details": [
    {"text": "用户在询问关于 Rust 的学习进度..."}
  ],
  "content": {
    "entities": [...],
    "events": [...]
  }
}
```

**优点**:
- 便于调试和分析模型思考
- 可以过滤掉思考内容，只保留结果
- 提高 JSON 解析成功率

**推荐**: **启用**（`true`）

---

## ⚠️ 注意事项

### 1. 温度参数

MiniMax 温度范围: **(0.0, 1.0]**

- ❌ 不能设置为 `0.0`（会报错）
- ✅ 推荐设置为 `1.0`
- ⚠️ 不要使用 OpenAI 的默认值 `0.1`（虽然有效，但不是最佳值）

### 2. API Key 格式

MiniMax API Key 格式: `sk-cp-xxx...`

与 OpenAI 的 `sk-proj-xxx...` 不同

### 3. 不支持的参数

以下 OpenAI 参数会被**忽略**:
- `presence_penalty`
- `frequency_penalty`
- `logit_bias`
- `n` > 1（只支持 n=1）

### 4. JSON 模式

确保使用 `response_format={"type": "json_object"}`（项目已配置）

---

## 🐛 常见问题

### 问题 1: 401 Unauthorized

**症状**:
```
Error code: 401 - 'Incorrect API key provided'
```

**原因**: API Key 发送到了 OpenAI 服务器

**解决**:
```bash
# 检查 .env 配置
cat .env | grep BASE_URL

# 应该显示:
# OPENAI_BASE_URL=https://api.minimaxi.com/v1

# 如果没有，添加这一行
echo "OPENAI_BASE_URL=https://api.minimaxi.com/v1" >> .env
```

### 问题 2: Temperature out of range

**症状**:
```
ValueError: MiniMax temperature must be in (0.0, 1.0], got 0.1
```

**解决**:
```bash
# 修改 .env
LLM_TEMPERATURE=1.0
```

### 问题 3: 模型名称错误

**症状**:
```
Model not found: minimax-m2.7
```

**原因**: 模型名称大小写敏感

**解决**:
```bash
# 正确写法（注意大小写）
LLM_MODEL=MiniMax-M2.7-highspeed

# 错误写法
# LLM_MODEL=minimax-m2.7-highspeed  ❌
```

---

## 📈 性能优化

### 批量处理大量文档

```bash
# 使用极速版
LLM_MODEL=MiniMax-M2.7-highspeed

# 或使用经济版
LLM_MODEL=MiniMax-M2.5-highspeed
```

### 提高质量

```bash
# 使用标准版（更多思考时间）
LLM_MODEL=MiniMax-M2.7

# 温度设置为 1.0（MiniMax 推荐值）
LLM_TEMPERATURE=1.0
```

### 调试模式

```bash
# 启用思考分离，便于查看模型推理过程
LLM_REASONING_SPLIT=true
```

---

## 🔄 从 OpenAI 迁移

### 步骤 1: 修改 .env

```diff
- OPENAI_API_KEY=sk-proj-openai-key
+ OPENAI_API_KEY=sk-cp-minimax-key
+ OPENAI_BASE_URL=https://api.minimaxi.com/v1

- LLM_MODEL=gpt-4o-mini
+ LLM_MODEL=MiniMax-M2.7-highspeed

- LLM_TEMPERATURE=0.1
+ LLM_TEMPERATURE=1.0

+ LLM_REASONING_SPLIT=true
```

### 步骤 2: 重新运行

```bash
python main.py --init
python main.py
```

### 步骤 3: 对比结果

```bash
# 查看抽取结果
python main.py --stats

# 查看具体抽取内容
sqlite3 data/state.db "SELECT extraction_json FROM extractions LIMIT 1;" | python -m json.tool
```

---

## 💰 成本估算

假设:
- 100 个文档
- 平均每个文档 2 个 chunks
- 每个 chunk ~500 tokens

**总 tokens**: 约 100k tokens

**成本**: 参考 MiniMax 官网定价（通常比 OpenAI 便宜）

---

## 📞 获取支持

### 官方资源

- **官网**: https://platform.minimaxi.com/
- **文档**: https://platform.minimaxi.com/docs
- **GitHub**: https://github.com/MiniMax-AI/MiniMax-M2
- **邮箱**: Model@minimaxi.com

### 项目文档

- `.github/MULTI_LLM_GUIDE.md` - 多提供商配置
- `TESTING.md` - 测试指南
- `CLAUDE.md` - 项目架构

---

## ✅ 配置检查清单

完成配置后，检查以下项目：

- [ ] API Key 已设置（`sk-cp-` 开头）
- [ ] Base URL 已设置（`https://api.minimaxi.com/v1`）
- [ ] 模型名称正确（`MiniMax-M2.7-highspeed` 等）
- [ ] 温度设置为 1.0
- [ ] reasoning_split 已启用（可选）
- [ ] 运行 `python main.py` 成功
- [ ] 查看抽取结果正常

---

**配置完成！开始使用 MiniMax 进行文档抽取吧！** 🚀
