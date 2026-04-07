# Extraction JSON Schema 定义

## 概述

`extraction_json` 是 chunk 级的局部观察层，用于存储从单个 chunk 中提取的结构化信息。

**设计原则：**
- 这是局部观察，不是最终的 state
- 时间信息包含来源标记（显式/推断/文档上下文）
- 不机械套用 5W1H
- state_candidates 是候选，不是 "why"
- relation_candidates 是观察到的关系，不是 "how"

## 顶层结构

```python
@dataclass
class ExtractionResult:
    context: ExtractionContext              # 抽取上下文
    entities: List[Entity]                  # 实体列表
    events: List[Event]                     # 事件列表
    state_candidates: List[StateCandidate]  # 状态候选
    relation_candidates: List[RelationCandidate]  # 关系候选
    retrieval_candidates: List[RetrievalCandidate]  # 检索候选
```

## 各部分详细定义

### 1. ExtractionContext（抽取上下文）

记录 chunk 的元信息，帮助理解后续抽取内容。

```python
@dataclass
class ExtractionContext:
    chunk_position: Optional[str] = None     # start | middle | end
    document_title: Optional[str] = None     # 文档标题
    document_time: Optional[TimeInfo] = None # 文档默认时间上下文
    section: Optional[str] = None            # 所属章节
```

**示例：**
```json
{
  "context": {
    "chunk_position": "start",
    "document_title": "项目周报 2024-03",
    "document_time": {
      "normalized": "2024-03",
      "source": "document_context"
    },
    "section": "本周进展"
  }
}
```

### 2. TimeInfo（时间信息）

带来源的时间信息，区分显式、推断、文档上下文等来源。

```python
@dataclass
class TimeInfo:
    normalized: Optional[str] = None  # 标准化时间（ISO 8601 或自定义）
    source: str = "unknown"           # explicit | document_context | inferred | unknown
    raw: Optional[str] = None         # 原始时间文本
```

**时间来源类型：**
- `explicit` - 文本中显式提到的时间（"2024年3月15日"）
- `document_context` - 从文档元信息推断（文档标题、文件名）
- `inferred` - 从上下文推断（"上周"、"最近"）
- `unknown` - 无法确定来源

**示例：**
```json
{
  "normalized": "2024-03-15",
  "source": "explicit",
  "raw": "3月15日"
}
```

### 3. Entity（实体）

从 chunk 中观察到的实体。

```python
@dataclass
class Entity:
    text: str                      # 实体文本
    type: str                      # 实体类型
    context: Optional[str] = None  # 上下文信息
    confidence: float = 1.0        # 置信度（0-1）
```

**实体类型建议：**
- `person` - 人物
- `organization` - 组织/公司
- `location` - 地点
- `concept` - 概念
- `tool` - 工具/技术
- `project` - 项目
- `product` - 产品

**示例：**
```json
{
  "text": "GPT-4",
  "type": "tool",
  "context": "用于代码生成",
  "confidence": 1.0
}
```

### 4. Event（事件）

从 chunk 中观察到的事件。

```python
@dataclass
class Event:
    description: str                        # 事件描述
    time: Optional[TimeInfo] = None         # 时间信息
    participants: List[str] = []            # 参与者
    location: Optional[str] = None          # 地点
    context: Optional[str] = None           # 上下文
    confidence: float = 1.0                 # 置信度
```

**示例：**
```json
{
  "description": "完成了数据库设计",
  "time": {
    "normalized": "2024-03-15",
    "source": "explicit",
    "raw": "昨天"
  },
  "participants": ["张三", "李四"],
  "location": "线上会议",
  "confidence": 0.9
}
```

### 5. StateCandidate（状态候选）

chunk 中观察到的状态候选，不是最终的 state。

```python
@dataclass
class StateCandidate:
    summary: str                            # 状态摘要
    category: Optional[str] = None          # 大类建议（dynamic/static）
    subtype: Optional[str] = None           # 小类建议
    detail: Optional[str] = None            # 详细信息
    time: Optional[TimeInfo] = None         # 时间信息
    confidence: float = 1.0                 # 置信度
```

**注意：**
- 这是候选，需要后续聚合成正式的 state
- 不同 chunk 可能提取出重复或冲突的候选
- category/subtype 只是建议，最终由聚合逻辑决定

**示例：**
```json
{
  "summary": "正在学习 Rust 编程语言",
  "category": "dynamic",
  "subtype": "ongoing_learning",
  "detail": "已完成前三章内容",
  "time": {
    "normalized": "2024-03",
    "source": "document_context"
  },
  "confidence": 0.85
}
```

### 6. RelationCandidate（关系候选）

chunk 中观察到的关系候选。

```python
@dataclass
class RelationCandidate:
    source: str                     # 源对象文本
    target: str                     # 目标对象文本
    relation_type: str              # 关系类型
    context: Optional[str] = None   # 上下文
    confidence: float = 1.0         # 置信度
```

**关系类型建议：**
- `uses` - 使用
- `belongs_to` - 属于
- `related_to` - 相关
- `depends_on` - 依赖
- `works_with` - 与...合作
- `created_by` - 创建者

**示例：**
```json
{
  "source": "我",
  "target": "VSCode",
  "relation_type": "uses",
  "context": "日常开发工具",
  "confidence": 1.0
}
```

### 7. RetrievalCandidate（检索候选）

语义不确定但局部重要的对象，需要后续补充检索。

```python
@dataclass
class RetrievalCandidate:
    surface_form: str               # 原始出现形式
    type_guess: Optional[str] = None  # 类型猜测
    context: Optional[str] = None   # 上下文
    priority: int = 0               # 优先级（0-10）
```

**使用场景：**
- 缩写（"GPT" - 需要确认是 GPT-3/4 还是其他）
- 人名（"老王" - 需要确认具体身份）
- 项目代号（"项目X" - 需要补充完整信息）

**示例：**
```json
{
  "surface_form": "老李",
  "type_guess": "person",
  "context": "一起参与项目的同事",
  "priority": 5
}
```

## 完整示例

```json
{
  "context": {
    "chunk_position": "middle",
    "document_title": "2024年3月工作日志",
    "document_time": {
      "normalized": "2024-03",
      "source": "document_context"
    },
    "section": "技术学习"
  },
  "entities": [
    {
      "text": "Rust",
      "type": "tool",
      "context": "编程语言",
      "confidence": 1.0
    },
    {
      "text": "《Rust 权威指南》",
      "type": "product",
      "confidence": 1.0
    }
  ],
  "events": [
    {
      "description": "开始学习 Rust 编程语言",
      "time": {
        "normalized": "2024-03-10",
        "source": "explicit",
        "raw": "本月10日"
      },
      "participants": [],
      "confidence": 0.9
    }
  ],
  "state_candidates": [
    {
      "summary": "正在学习 Rust 编程语言",
      "category": "dynamic",
      "subtype": "ongoing_learning",
      "detail": "通过《Rust 权威指南》进行系统学习",
      "time": {
        "normalized": "2024-03",
        "source": "document_context"
      },
      "confidence": 0.85
    },
    {
      "summary": "对系统编程感兴趣",
      "category": "static",
      "subtype": "interest",
      "confidence": 0.7
    }
  ],
  "relation_candidates": [
    {
      "source": "我",
      "target": "Rust",
      "relation_type": "learning",
      "context": "系统编程语言学习",
      "confidence": 0.9
    }
  ],
  "retrieval_candidates": []
}
```

## Python 代码示例

### 创建抽取结果

```python
from layers.middle_layer import (
    ExtractionResult, ExtractionContext, TimeInfo,
    Entity, Event, StateCandidate, RelationCandidate
)

# 创建时间信息
doc_time = TimeInfo(
    normalized="2024-03",
    source="document_context"
)

event_time = TimeInfo(
    normalized="2024-03-10",
    source="explicit",
    raw="本月10日"
)

# 创建上下文
context = ExtractionContext(
    chunk_position="middle",
    document_title="2024年3月工作日志",
    document_time=doc_time,
    section="技术学习"
)

# 创建实体
entities = [
    Entity(text="Rust", type="tool", context="编程语言", confidence=1.0),
    Entity(text="《Rust 权威指南》", type="product", confidence=1.0)
]

# 创建事件
events = [
    Event(
        description="开始学习 Rust 编程语言",
        time=event_time,
        participants=[],
        confidence=0.9
    )
]

# 创建状态候选
state_candidates = [
    StateCandidate(
        summary="正在学习 Rust 编程语言",
        category="dynamic",
        subtype="ongoing_learning",
        detail="通过《Rust 权威指南》进行系统学习",
        time=doc_time,
        confidence=0.85
    )
]

# 创建关系候选
relation_candidates = [
    RelationCandidate(
        source="我",
        target="Rust",
        relation_type="learning",
        context="系统编程语言学习",
        confidence=0.9
    )
]

# 组装抽取结果
result = ExtractionResult(
    context=context,
    entities=entities,
    events=events,
    state_candidates=state_candidates,
    relation_candidates=relation_candidates,
    retrieval_candidates=[]
)

# 保存到数据库
from layers.middle_layer import save_extraction

extraction_id = save_extraction(
    chunk_id=1,
    result=result,
    extractor_type="llm",
    model_name="gpt-4",
    prompt_version="v1.0"
)
```

### 从数据库读取并反序列化

```python
import json
from db import get_connection
from layers.middle_layer import ExtractionResult

conn = get_connection()
cursor = conn.execute("SELECT extraction_json FROM extractions WHERE id = ?", (1,))
row = cursor.fetchone()

if row:
    # 从 JSON 字符串反序列化
    extraction_dict = json.loads(row['extraction_json'])
    result = ExtractionResult.from_dict(extraction_dict)
    
    # 访问结构化数据
    print(f"Context: {result.context.document_title}")
    print(f"Entities: {len(result.entities)}")
    print(f"Events: {len(result.events)}")
    for event in result.events:
        print(f"  - {event.description} at {event.time.normalized if event.time else 'unknown'}")
```

## 设计说明

### 为什么不机械套用 5W1H？

- **Who**: 不单独设字段，通过 entities (type=person) 和 event.participants 表达
- **What**: event.description 或 state_candidate.summary
- **When**: TimeInfo 对象，不是简单字符串
- **Where**: event.location 或 entity (type=location)
- **Why**: 不直接存储，通过 state_candidates 和 relation_candidates 推断
- **How**: 不直接存储，通过关系网络体现

### state vs state_candidate

- `state_candidate` 是 chunk 级观察，可能重复、不完整
- `state` 是聚合后的最终状态，存在 states 表
- 多个 chunk 的 state_candidates 会合并成一个 state

### relation vs relation_candidate

- `relation_candidate` 是局部观察到的关系
- `relations` 表是正式关系，需要验证和去重
- 不是所有候选都会成为正式关系

---

日期：2026-04-05  
版本：v1.0
