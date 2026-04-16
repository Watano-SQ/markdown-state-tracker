# 任务一执行计划：实现 LLM 抽取器（修订版）

**任务编号**: Task-001  
**任务名称**: 实现 LLM 抽取器（LLM-based Extractor）  
**优先级**: P0（最高）  
**计划制定时间**: 2026-04-07  
**最后修订**: 2026-04-07 18:53（引入 LLM 方案）  
**预估工作量**: 3-5 小时

---

## 📋 目标陈述

实现一个**基于 LLM 的抽取器**，能够：
1. 从 Markdown chunk 文本中提取高质量的结构化信息
2. 准确填充 `ExtractionResult` 数据结构
3. 理解语义上下文，而非简单模式匹配
4. 集成到主流程中，让整个系统能端到端运行

**边界约束**：
- ✅ 使用 LLM API（如 OpenAI / Anthropic）进行语义理解
- ✅ 设计结构化 prompt，确保输出符合 schema
- ✅ 支持配置不同的 LLM 提供商
- ⚠️ 控制 token 消耗（只对 chunk 抽取，不重复调用）
- ❌ 不做复杂的 prompt 工程（优先简单有效）

---

## 🔄 方案变更说明

**原方案**: 纯规则抽取（正则 + 关键词）  
**问题**: 精度不足，无法理解语义，漏提取多

**新方案**: LLM 抽取 + 规则辅助  
**优势**: 
- ✅ 理解复杂语义
- ✅ 处理自然语言变化
- ✅ 提取质量高
- ✅ 易于调整（改 prompt 即可）

**权衡**:
- ⚠️ 需要 API key（成本）
- ⚠️ 调用延迟（可接受）
- ⚠️ 依赖外部服务（可配置本地模型）

---

## 🎯 验收标准（6 项）

- [ ] 1. 创建 `layers/extractors/` 目录和 `rule_extractor.py` 文件
- [ ] 2. 实现 `extract_from_chunk(text: str, context: dict) -> ExtractionResult`
- [ ] 3. 能提取基本实体（人名、工具名、时间）
- [ ] 4. 能提取状态候选（关键动词短语）
- [ ] 5. 在 `main.py` 中集成抽取流程
- [ ] 6. 端到端测试通过（输入文档 → 抽取 → 存储 → 输出）

---

## 🛠️ 技术方案设计

### 方案概览

采用 **LLM 语义理解 + 规则辅助**的混合方法：

```
Chunk Text + Context
    ↓
[1] 规则预处理（提取显式信息：日期、标题等）
    ↓
[2] 构建结构化 Prompt
    ↓
[3] LLM API 调用（一次性提取所有信息）
    ↓
[4] JSON 响应解析 & 验证
    ↓
[5] 规则后处理（补全、校验）
    ↓
[6] 构建 ExtractionResult
    ↓
ExtractionResult
```

### 核心设计：结构化 Prompt

使用 **JSON Schema Prompt**，让 LLM 直接输出符合 `ExtractionResult` 的 JSON。

---

## 💡 LLM Prompt 设计

### Prompt 结构

```
系统角色（System）:
你是一个信息抽取专家，从 Markdown 文本中提取结构化信息。

用户输入（User）:
请从以下文本中提取信息，以 JSON 格式返回。

【文本】
{chunk_text}

【文档上下文】
- 文档标题: {document_title}
- 默认时间: {document_time}

【输出格式】
严格按照以下 JSON Schema 返回，不要添加任何解释：
{json_schema}
```

### JSON Schema 示例

```json
{
  "context": {
    "chunk_position": "start|middle|end",
    "section": "所属章节（如有）"
  },
  "entities": [
    {
      "text": "实体文本",
      "type": "person|organization|tool|concept|location|product",
      "context": "上下文说明（可选）",
      "confidence": 0.0-1.0
    }
  ],
  "events": [
    {
      "description": "事件描述",
      "time": {
        "normalized": "YYYY-MM-DD 或 YYYY-MM",
        "source": "explicit|document_context|inferred|unknown",
        "raw": "原始时间文本（可选）"
      },
      "participants": ["参与者列表"],
      "location": "地点（可选）",
      "confidence": 0.0-1.0
    }
  ],
  "state_candidates": [
    {
      "summary": "状态摘要",
      "category": "dynamic|static",
      "subtype": "ongoing_project|recent_event|pending_task|active_interest|preference|background|skill|relationship",
      "detail": "详细信息（可选）",
      "time": { /* 同 events.time */ },
      "confidence": 0.0-1.0
    }
  ],
  "relation_candidates": [
    {
      "source": "源对象",
      "target": "目标对象",
      "relation_type": "uses|works_with|learning|belongs_to|related_to",
      "context": "关系上下文（可选）",
      "confidence": 0.0-1.0
    }
  ],
  "retrieval_candidates": [
    {
      "surface_form": "原始文本",
      "type_guess": "类型猜测",
      "context": "上下文",
      "priority": 0-10
    }
  ]
}
```

### Prompt 优化要点

1. **明确指令**: "严格按照 JSON Schema 返回"
2. **示例驱动**: 提供 1-2 个示例（few-shot）
3. **类型约束**: 明确 enum 值（如 type, category）
4. **置信度指导**: 说明何时使用低置信度
5. **时间来源**: 明确区分 explicit/inferred/document_context

---

### 模块 1: LLM 抽取器核心

**文件**: `layers/extractors/llm_extractor.py`

```python
import os
import json
from typing import Optional, Dict, Any
from openai import OpenAI  # 或 anthropic

from ..middle_layer import ExtractionResult


class LLMExtractor:
    """基于 LLM 的抽取器"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Args:
            api_key: API 密钥（默认从环境变量读取）
            model: 模型名称（gpt-4o-mini, gpt-4, claude-3-haiku 等）
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model
        self.client = OpenAI(api_key=self.api_key)
    
    def extract(self, text: str, context: Optional[Dict[str, Any]] = None) -> ExtractionResult:
        """
        从文本中提取信息
        
        Args:
            text: chunk 文本
            context: 文档上下文
        
        Returns:
            ExtractionResult 对象
        """
        # 1. 构建 prompt
        prompt = self._build_prompt(text, context or {})
        
        # 2. 调用 LLM
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # 低温度，确保稳定输出
            response_format={"type": "json_object"}  # 强制 JSON 输出
        )
        
        # 3. 解析响应
        result_json = json.loads(response.choices[0].message.content)
        
        # 4. 转换为 ExtractionResult
        return ExtractionResult.from_dict(result_json)
    
    def _build_prompt(self, text: str, context: Dict[str, Any]) -> str:
        """构建结构化 prompt"""
        return f"""请从以下文本中提取信息，以 JSON 格式返回。

【文本】
{text}

【文档上下文】
- 文档标题: {context.get('document_title', '未知')}
- 默认时间: {context.get('document_time', '未知')}

【输出格式】
严格按照以下 JSON Schema 返回，不要添加任何解释：

{JSON_SCHEMA}

【抽取要求】
1. 实体类型: person, organization, tool, concept, location, product
2. 状态类型: 
   - dynamic: ongoing_project, recent_event, pending_task, active_interest
   - static: preference, background, skill, relationship
3. 时间来源: 
   - explicit: 文本明确提到（如"2024年3月15日"）
   - document_context: 从文档标题/元信息推断
   - inferred: 从上下文推断（如"上周"）
   - unknown: 无法确定
4. 置信度: 明确信息用 0.9-1.0，推断信息用 0.6-0.8，不确定用 0.3-0.5
5. 检索候选: 缩写、代称、模糊指代等需要进一步明确的对象
"""


# Prompt 常量
SYSTEM_PROMPT = """你是一个专业的信息抽取助手，擅长从 Markdown 文本中提取结构化信息。
你的任务是准确识别实体、事件、状态、关系等信息，并以 JSON 格式返回。

重要原则:
1. 严格遵循 JSON Schema，不要遗漏必需字段
2. 时间信息必须包含来源标注（explicit/document_context/inferred/unknown）
3. 对不确定的信息降低置信度，不要捏造
4. 检索候选用于标记需要进一步明确的对象（如缩写、代称）
"""

JSON_SCHEMA = """
{
  "context": {
    "chunk_position": "start|middle|end （可选）",
    "section": "所属章节 （可选）"
  },
  "entities": [
    {
      "text": "实体文本",
      "type": "person|organization|tool|concept|location|product",
      "context": "上下文说明 （可选）",
      "confidence": 0.0-1.0
    }
  ],
  "events": [
    {
      "description": "事件描述",
      "time": {
        "normalized": "YYYY-MM-DD 或 YYYY-MM",
        "source": "explicit|document_context|inferred|unknown",
        "raw": "原始时间文本 （可选）"
      },
      "participants": ["参与者"],
      "location": "地点 （可选）",
      "context": "上下文 （可选）",
      "confidence": 0.0-1.0
    }
  ],
  "state_candidates": [
    {
      "summary": "状态摘要",
      "category": "dynamic|static",
      "subtype": "见上方说明",
      "detail": "详细信息 （可选）",
      "time": { /* 同 events.time */ },
      "confidence": 0.0-1.0
    }
  ],
  "relation_candidates": [
    {
      "source": "源对象",
      "target": "目标对象",
      "relation_type": "uses|works_with|learning|belongs_to|related_to|depends_on",
      "context": "关系上下文 （可选）",
      "confidence": 0.0-1.0
    }
  ],
  "retrieval_candidates": [
    {
      "surface_form": "原始出现形式",
      "type_guess": "类型猜测 （可选）",
      "context": "上下文 （可选）",
      "priority": 0-10
    }
  ]
}
"""
```

---

### 模块 2: 规则辅助处理

**文件**: `layers/extractors/rule_helper.py`

**目标**: 规则预处理和后处理，辅助 LLM

**规则预处理**（提取显式信息）:

1. **提取显式日期**
   ```python
   # 加粗文本 → 可能是重要实体
   **Python** → Entity(text="Python", type="tool")
   
   # 代码块 → 可能是工具
   `VSCode` → Entity(text="VSCode", type="tool")
   
   # 标题 → 可能是概念
   ### 项目管理 → Entity(text="项目管理", type="concept")
   ```

2. **工具/技术关键词匹配**
   ```python
   TECH_KEYWORDS = {
       'tool': ['Python', 'Java', 'Git', 'Docker', 'VSCode', 'ChatGPT', ...],
       'framework': ['React', 'Django', 'Spring', 'Vue', ...],
       'language': ['中文', '英文', 'JavaScript', 'TypeScript', ...]
   }
   ```

3. **人名模式识别**（简单规则）
   ```python
   # 中文人名：姓氏（1字）+ 名（1-2字）
   pattern = r'(张|李|王|刘|陈|...)([\u4e00-\u9fa5]{1,2})'
   
   # 英文人名：大写开头
   pattern = r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b'
   
   # 称呼模式："老X"、"小X"
   pattern = r'(老|小)([\u4e00-\u9fa5])'
   ```

4. **地点识别**
   ```python
   LOCATION_KEYWORDS = ['北京', '上海', '深圳', '线上', '会议室', ...]
   LOCATION_PATTERNS = [r'在(.{2,6})(举行|进行|开会)']
   ```

**输出示例**:
```python
entities = [
    Entity(text="Python", type="tool", confidence=1.0),
    Entity(text="张三", type="person", confidence=0.8),
    Entity(text="深圳", type="location", confidence=0.9),
]
```

---

### 模块 2: 时间提取（Time Extraction）

**目标**: 提取文本中的时间信息，标注来源

**策略**:

1. **显式时间表达**
   ```python
   # 绝对时间
   "2024年3月15日" → TimeInfo(normalized="2024-03-15", source="explicit")
   "3月15日" → TimeInfo(normalized="2024-03-15", source="explicit")
   
   # ISO 格式
   "2024-03-15" → TimeInfo(normalized="2024-03-15", source="explicit")
   ```

2. **相对时间表达**
   ```python
   # 相对时间（需要基准时间）
   "昨天" → TimeInfo(normalized="2024-04-06", source="inferred")
   "上周" → TimeInfo(normalized="2024-W13", source="inferred")
   "本月" → TimeInfo(normalized="2024-04", source="inferred")
   ```

3. **文档上下文时间**
   ```python
   # 从文档标题提取
   "2024年3月工作日志" → document_time
   
   # 传递给抽取器
   context = {
       'document_time': TimeInfo(normalized="2024-03", source="document_context")
   }
   ```

**实现方案**:
```python
# 方案 A: 使用 dateutil（推荐，处理复杂）
from dateutil import parser
try:
    dt = parser.parse(time_str, fuzzy=True)
    return TimeInfo(normalized=dt.strftime('%Y-%m-%d'), source="explicit")
except:
    pass

# 方案 B: 正则匹配（轻量，处理简单）
patterns = [
    (r'(\d{4})[年-](\d{1,2})[月-](\d{1,2})[日]?', '%Y-%m-%d'),
    (r'(\d{1,2})[月-](\d{1,2})[日]?', 'MM-DD'),
]
```

**选择**: 先用方案 B（无依赖），后续可升级到方案 A

---

### 模块 3: 事件提取（Event Extraction）

**目标**: 识别文本中描述的事件

**策略**:

1. **动作动词模式**
   ```python
   ACTION_VERBS = [
       '完成', '开始', '学习', '参加', '讨论', '实现',
       '发布', '部署', '修复', '优化', '阅读', '写',
   ]
   
   # 模式：主语 + 动词 + 宾语
   pattern = r'(.{1,10})(完成|开始|学习)(.{1,20})'
   ```

2. **事件上下文**
   ```python
   # 提取参与者（"和XX"、"与XX"）
   "我和张三一起完成了项目" 
   → Event(
       description="完成了项目",
       participants=["我", "张三"]
     )
   
   # 提取地点（"在XX"）
   "在深圳参加会议"
   → Event(
       description="参加会议",
       location="深圳"
     )
   ```

**输出示例**:
```python
events = [
    Event(
        description="完成了数据库设计",
        time=TimeInfo(normalized="2024-03-15", source="explicit"),
        participants=["我", "张三"],
        confidence=0.85
    )
]
```

---

### 模块 4: 状态候选提取（State Candidate Extraction）

**目标**: 识别表示状态的短语

**策略**:

1. **状态关键词模式**
   ```python
   STATE_PATTERNS = {
       'ongoing': [
           r'正在(.{2,20})',      # 正在学习Python
           r'在(.{2,20})',        # 在进行项目
           r'持续(.{2,20})',      # 持续关注
       ],
       'completed': [
           r'已(.{2,20})',        # 已完成
           r'完成了(.{2,20})',    # 完成了学习
       ],
       'planned': [
           r'计划(.{2,20})',      # 计划学习
           r'打算(.{2,20})',      # 打算研究
       ],
       'interest': [
           r'对(.{2,20})感兴趣',  # 对AI感兴趣
           r'喜欢(.{2,20})',      # 喜欢编程
       ]
   }
   ```

2. **分类推断**
   ```python
   # 基于关键词推断 category 和 subtype
   "正在学习 Rust" 
   → StateCandidate(
       summary="正在学习 Rust",
       category="dynamic",
       subtype="ongoing_learning",
       confidence=0.8
     )
   
   "喜欢编程"
   → StateCandidate(
       summary="喜欢编程",
       category="static",
       subtype="preference",
       confidence=0.7
     )
   ```

**输出示例**:
```python
state_candidates = [
    StateCandidate(
        summary="正在学习 Rust 编程语言",
        category="dynamic",
        subtype="ongoing_learning",
        detail="通过《Rust 权威指南》进行系统学习",
        confidence=0.85
    )
]
```

---

### 模块 5: 关系候选提取（Relation Candidate Extraction）

**目标**: 识别实体间的关系

**策略**:

1. **简单关系模式**
   ```python
   RELATION_PATTERNS = {
       'uses': [r'使用(.{2,10})', r'用(.{2,10})'],
       'works_with': [r'和(.{2,10})一起', r'与(.{2,10})合作'],
       'learning': [r'学习(.{2,10})', r'研究(.{2,10})'],
   }
   
   # 示例
   "我使用 Python 开发"
   → RelationCandidate(
       source="我",
       target="Python",
       relation_type="uses"
     )
   ```

**输出示例**:
```python
relation_candidates = [
    RelationCandidate(
        source="我",
        target="Python",
        relation_type="uses",
        context="日常开发",
        confidence=0.9
    )
]
```

---

### 模块 6: 检索候选识别（Retrieval Candidate Identification）

**目标**: 识别语义不确定但可能重要的对象

**触发条件**:
1. 简称/缩写（"GPT"、"TS"）
2. 代称（"老李"、"小王"）
3. 模糊指代（"那个项目"、"之前的工具"）

**策略**:
```python
AMBIGUOUS_PATTERNS = [
    r'[A-Z]{2,}',           # 全大写缩写
    r'(老|小)([\u4e00-\u9fa5])',  # 老X、小X
    r'(那个|这个)(.{2,6})',       # 那个XX
]

# 示例
"老李负责后端"
→ RetrievalCandidate(
    surface_form="老李",
    type_guess="person",
    context="负责后端",
    priority=5
  )
```

---

## 📁 代码结构设计

```
layers/
├── extractors/
│   ├── __init__.py
│   ├── llm_extractor.py           # LLM 抽取器（主）
│   ├── rule_helper.py             # 规则辅助处理
│   ├── prompts.py                 # Prompt 模板定义
│   ├── config.py                  # 配置（API key, model 等）
│   └── utils.py                   # 辅助函数
```

### 主文件：`llm_extractor.py`

```python
"""
基于 LLM 的抽取器
"""
import os
import json
from typing import Optional, Dict, Any
from openai import OpenAI

from ..middle_layer import ExtractionResult
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .rule_helper import preprocess_text, postprocess_result


class LLMExtractor:
    """LLM 抽取器"""
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1
    ):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        self.model = model
        self.temperature = temperature
        self.client = OpenAI(api_key=self.api_key)
    
    def extract(
        self, 
        text: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> ExtractionResult:
        """抽取信息"""
        context = context or {}
        
        # 1. 规则预处理
        preprocessed = preprocess_text(text, context)
        
        # 2. 构建 prompt
        user_prompt = build_user_prompt(
            text=preprocessed['text'],
            context=context,
            hints=preprocessed.get('hints', {})
        )
        
        # 3. LLM 调用
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=self.temperature,
            response_format={"type": "json_object"}
        )
        
        # 4. 解析结果
        result_json = json.loads(response.choices[0].message.content)
        
        # 5. 后处理
        result_json = postprocess_result(result_json, preprocessed)
        
        # 6. 转换为 ExtractionResult
        return ExtractionResult.from_dict(result_json)


# 便捷函数
def extract_from_chunk(
    text: str,
    context: Optional[Dict[str, Any]] = None,
    extractor: Optional[LLMExtractor] = None
) -> ExtractionResult:
    """
    从 chunk 提取信息（便捷接口）
    
    Args:
        text: chunk 文本
        context: 上下文信息
        extractor: 复用的 extractor 实例（可选）
    
    Returns:
        ExtractionResult
    """
    if extractor is None:
        extractor = LLMExtractor()
    
    return extractor.extract(text, context)
```

---

## 🔧 实施步骤（修订版）

### 步骤 1: 环境准备（10分钟）

```bash
# 1. 安装依赖
pip install openai  # 或 anthropic, 如果用 Claude

# 2. 设置 API Key
export OPENAI_API_KEY="sk-..."  # 或写入 .env 文件

# 3. 创建目录结构
mkdir -p layers/extractors
touch layers/extractors/__init__.py
touch layers/extractors/llm_extractor.py
touch layers/extractors/prompts.py
touch layers/extractors/rule_helper.py
touch layers/extractors/config.py
touch layers/extractors/utils.py
```

### 步骤 2: 实现 Prompt 模板（30分钟）

**文件**: `layers/extractors/prompts.py`

定义：
- `SYSTEM_PROMPT` - 系统角色提示词
- `JSON_SCHEMA` - 输出格式定义
- `build_user_prompt()` - 动态构建用户 prompt

### 步骤 3: 实现规则辅助（20分钟）

**文件**: `layers/extractors/rule_helper.py`

- `preprocess_text()` - 提取显式日期、标题等
- `postprocess_result()` - 验证、补全、校正

### 步骤 4: 实现 LLM 抽取器（40分钟）

**文件**: `layers/extractors/llm_extractor.py`

- `LLMExtractor` 类
- `extract()` 方法
- `extract_from_chunk()` 便捷函数

### 步骤 5: 集成到主流程（15分钟）

修改 `main.py`，在输入层和中间层之间添加抽取步骤：

```python
# main.py 新增
from layers.extractors.llm_extractor import extract_from_chunk, LLMExtractor

def run_pipeline(verbose: bool = True):
    # ... 输入层处理 ...
    
    # 新增：抽取步骤
    if verbose:
        print("\n[抽取层] 处理 chunks...")
    
    pending = get_pending_chunks()
    
    # 创建 extractor 实例（复用连接）
    extractor = LLMExtractor(model="gpt-4o-mini")  # 或从配置读取
    
    for chunk in pending:
        # 准备上下文
        context = {
            'document_title': chunk['title'],
            'document_time': None,  # 可以从标题提取
            'chunk_position': 'middle',  # 简化处理
        }
        
        # 抽取
        result = extractor.extract(chunk['text'], context)
        
        # 保存
        save_extraction(
            chunk_id=chunk['id'],
            result=result,
            extractor_type='llm',
            model_name=extractor.model,  # 如 'gpt-4o-mini'
            prompt_version='v1.0'
        )
        
        if verbose:
            print(f"    处理 chunk {chunk['id']}: "
                  f"{len(result.entities)} 实体, "
                  f"{len(result.state_candidates)} 状态候选")
    
    # 标记文档为已处理
    for doc_id in set(c['document_id'] for c in pending):
        mark_document_processed(doc_id)
    
    # ... 输出层处理 ...
```

### 步骤 6: 端到端测试（30分钟）

1. 准备测试文档 `input_docs/test_extraction.md`
2. 设置环境变量 `export OPENAI_API_KEY="..."`
3. 运行完整流程 `python main.py --init && python main.py`
4. 检查数据库 `extractions` 表
5. 验证 extraction_json 内容
6. 评估提取质量（召回率、准确率）

### 步骤 7: 编写单元测试（30分钟）

创建 `tests/test_extractor.py`:

```python
import os
import pytest
from layers.extractors.llm_extractor import LLMExtractor

# 跳过测试如果没有 API key
pytestmark = pytest.mark.skipif(
    not os.getenv('OPENAI_API_KEY'),
    reason="OPENAI_API_KEY not set"
)


def test_extract_entities():
    """测试实体提取"""
    text = "我使用 **Python** 和 FastAPI 开发项目"
    extractor = LLMExtractor(model="gpt-4o-mini")
    result = extractor.extract(text)
    
    assert len(result.entities) >= 2
    entity_texts = [e.text for e in result.entities]
    assert "Python" in entity_texts
    assert "FastAPI" in entity_texts


def test_extract_time_explicit():
    """测试显式时间提取"""
    text = "2024年3月15日完成了数据库设计任务"
    extractor = LLMExtractor(model="gpt-4o-mini")
    result = extractor.extract(text)
    
    assert len(result.events) > 0
    event = result.events[0]
    assert event.time is not None
    assert "2024-03-15" in event.time.normalized
    assert event.time.source == "explicit"


def test_extract_state_candidates():
    """测试状态候选提取"""
    text = "正在学习 Rust 编程语言，通过《Rust 权威指南》进行系统学习"
    extractor = LLMExtractor(model="gpt-4o-mini")
    result = extractor.extract(text)
    
    assert len(result.state_candidates) > 0
    state = result.state_candidates[0]
    assert "Rust" in state.summary
    assert state.category in ["dynamic", "static"]
    

def test_extract_with_context():
    """测试带上下文的提取"""
    text = "本月完成了三个项目"
    context = {
        'document_title': '2024年3月工作日志',
        'document_time': '2024-03'
    }
    extractor = LLMExtractor(model="gpt-4o-mini")
    result = extractor.extract(text, context)
    
    # 应该能从上下文推断时间
    if result.events:
        assert result.events[0].time.source in ["document_context", "inferred"]


def test_json_schema_compliance():
    """测试输出是否符合 schema"""
    text = "使用 Python 开发"
    extractor = LLMExtractor(model="gpt-4o-mini")
    result = extractor.extract(text)
    
    # 验证所有必需字段
    assert hasattr(result, 'context')
    assert hasattr(result, 'entities')
    assert hasattr(result, 'events')
    assert hasattr(result, 'state_candidates')
    assert hasattr(result, 'relation_candidates')
    assert hasattr(result, 'retrieval_candidates')
    
    # 验证类型
    assert isinstance(result.entities, list)
    assert isinstance(result.events, list)
```

---

## 🧪 测试策略

### 测试数据准备

创建 `input_docs/test_extraction.md`:

```markdown
# 2024年3月学习笔记

本月主要进行了以下工作：

## 技术学习

正在学习 **Rust** 编程语言，通过《Rust 权威指南》进行系统学习。目前已完成前三章内容。

在3月15日和张三一起参加了线上技术分享会，讨论了 Rust 的所有权机制。

## 项目进展

使用 Python 和 FastAPI 完成了后端 API 开发。数据库选用 PostgreSQL。

计划下周开始前端开发，技术栈是 React + TypeScript。

## 个人偏好

- 喜欢使用 VSCode 进行开发
- 对函数式编程感兴趣
- 倾向于使用静态类型语言
```

### 预期提取结果

**实体**:
- Rust (tool)
- 《Rust 权威指南》 (product)
- 张三 (person)
- Python (tool)
- FastAPI (framework)
- PostgreSQL (tool)
- React (framework)
- TypeScript (language)
- VSCode (tool)

**事件**:
- 参加了线上技术分享会 (2024-03-15)
- 完成了后端 API 开发

**状态候选**:
- 正在学习 Rust 编程语言 (dynamic/ongoing_learning)
- 计划下周开始前端开发 (dynamic/planned_task)
- 喜欢使用 VSCode (static/preference)
- 对函数式编程感兴趣 (static/interest)

---

## ⚠️ 风险与应对（修订版）

### 风险 1: API 成本过高
**应对**: 
- 使用便宜模型（gpt-4o-mini ~$0.15/1M tokens）
- chunk 已经切分，单次 token 控制在 500-1000
- 预估：100 个 chunks ≈ 50k tokens ≈ $0.01

### 风险 2: LLM 输出不稳定
**应对**:
- 设置低温度（temperature=0.1）
- 使用 `response_format={"type": "json_object"}` 强制 JSON
- 规则后处理验证和修复

### 风险 3: API 调用失败
**应对**:
- 重试机制（最多 3 次）
- 降级策略（失败时用规则抽取）
- 记录失败的 chunks，手动处理

### 风险 4: 时间推断不准确
**应对**:
- Prompt 中强调时间来源标注
- 规则预处理提取显式日期
- 低置信度时标记为 `inferred`

### 风险 5: API Key 安全
**应对**:
- 从环境变量读取（不硬编码）
- 添加 `.env` 到 `.gitignore`
- 支持本地模型替代方案（后续）

---

## 📊 成功指标（修订版）

1. **功能完整性**: 6 个验收标准全部通过
2. **数据质量**: 测试文档抽取
   - 实体召回率 > 85%（核心实体基本不漏）
   - 状态候选召回率 > 80%
   - 时间来源标注准确率 > 90%
3. **代码质量**: 通过所有单元测试
4. **可维护性**: Prompt 清晰，易于调整
5. **成本控制**: 单个 chunk 平均成本 < $0.0002

---

## 📝 后续改进方向

本次实现是**基于 LLM 的 v1 版本**，后续可以：

1. **Few-shot 示例优化** - 在 prompt 中加入高质量示例
2. **混合策略** - 简单 chunks 用规则，复杂 chunks 用 LLM
3. **本地模型支持** - 集成 Ollama/LLaMA 降低成本
4. **Prompt 自动优化** - 基于评估结果迭代 prompt
5. **批量处理** - 多个 chunks 一次性发送（降低调用次数）
6. **主动学习** - 低置信度结果人工标注后改进 prompt

---

## ✅ 审查清单（修订版）

请审查以下方面：

- [ ] LLM 方案是否合理？精度是否能满足需求？
- [ ] Prompt 设计是否清晰？JSON Schema 是否完整？
- [ ] 成本控制策略是否可行？
- [ ] 降级方案是否充分（API 失败时）？
- [ ] 实施步骤是否清晰？
- [ ] 测试策略是否充分？
- [ ] 是否有遗漏的风险？
- [ ] 预估工作量是否合理（3-5 小时）？

---

## 🔑 依赖项

- `openai` >= 1.0.0（或 `anthropic` 如果用 Claude）
- 环境变量：`OPENAI_API_KEY`
- Python >= 3.7

---

**计划制定者**: Claude (GitHub Copilot CLI)  
**修订原因**: 提高精度，引入 LLM 方案  
**等待审查**: 是  
**下一步**: 审查通过 → 开始实施
