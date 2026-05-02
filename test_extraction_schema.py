"""
测试 ExtractionResult 新 schema 的正确性
"""
import sys
import json
from pathlib import Path

# 确保可以导入 layers 模块
sys.path.insert(0, str(Path(__file__).parent))

from layers.middle_layer import (
    ExtractionResult, ExtractionContext, TimeInfo,
    Entity, Event, StateCandidate, RelationCandidate, RetrievalCandidate
)


def test_basic_creation():
    """测试基本创建"""
    result = ExtractionResult()
    assert result.context is not None
    assert isinstance(result.entities, list)
    assert isinstance(result.events, list)
    assert len(result.entities) == 0
    print("[PASS] 基本创建测试通过")


def test_with_data():
    """测试完整数据创建"""
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
        document_author="Alice",
        document_time=doc_time,
        document_mode="personal",
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
            confidence=0.85,
            subject_type="person",
            subject_key="Alice",
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
    
    # 创建检索候选
    retrieval_candidates = [
        RetrievalCandidate(
            surface_form="老李",
            type_guess="person",
            context="项目同事",
            priority=5
        )
    ]
    
    # 组装结果
    result = ExtractionResult(
        context=context,
        entities=entities,
        events=events,
        state_candidates=state_candidates,
        relation_candidates=relation_candidates,
        retrieval_candidates=retrieval_candidates
    )
    
    assert len(result.entities) == 2
    assert len(result.events) == 1
    assert len(result.state_candidates) == 1
    assert len(result.relation_candidates) == 1
    assert len(result.retrieval_candidates) == 1
    assert result.context.document_title == "2024年3月工作日志"
    assert result.context.document_author == "Alice"
    assert result.context.document_mode == "personal"
    assert result.state_candidates[0].subject_type == "person"
    assert result.state_candidates[0].subject_key == "Alice"
    assert result.events[0].time.source == "explicit"
    
    print("[PASS] 完整数据创建测试通过")


def test_to_dict():
    """测试序列化为字典"""
    doc_time = TimeInfo(normalized="2024-03", source="document_context")
    context = ExtractionContext(document_time=doc_time)
    entity = Entity(text="Python", type="tool")
    
    result = ExtractionResult(
        context=context,
        entities=[entity]
    )
    
    data = result.to_dict()
    assert isinstance(data, dict)
    assert 'context' in data
    assert 'entities' in data
    assert data['entities'][0]['text'] == "Python"
    assert data['context']['document_time']['normalized'] == "2024-03"
    
    print("[PASS] to_dict 测试通过")


def test_from_dict():
    """测试从字典反序列化"""
    data = {
        "context": {
            "chunk_position": "start",
            "document_title": "测试文档",
            "document_time": {
                "normalized": "2024-03",
                "source": "document_context",
                "raw": None
            },
            "document_mode": "personal",
            "section": "测试章节"
        },
        "entities": [
            {
                "text": "Python",
                "type": "tool",
                "context": "编程语言",
                "confidence": 1.0
            }
        ],
        "events": [
            {
                "description": "学习 Python",
                "time": {
                    "normalized": "2024-03-01",
                    "source": "explicit",
                    "raw": "3月1日"
                },
                "participants": ["Alice"],
                "location": None,
                "context": None,
                "confidence": 0.9
            }
        ],
        "state_candidates": [
            {
                "summary": "正在学习 Python",
                "category": "dynamic",
                "subtype": "learning",
                "detail": None,
                "time": None,
                "subject_type": "person",
                "subject_key": "Alice",
                "confidence": 0.8
            }
        ],
        "relation_candidates": [],
        "retrieval_candidates": []
    }
    
    result = ExtractionResult.from_dict(data)
    
    assert result.context.document_title == "测试文档"
    assert result.context.document_time.normalized == "2024-03"
    assert result.context.document_mode == "personal"
    assert len(result.entities) == 1
    assert result.entities[0].text == "Python"
    assert len(result.events) == 1
    assert result.events[0].time.source == "explicit"
    assert result.events[0].participants == ["Alice"]
    assert len(result.state_candidates) == 1
    assert result.state_candidates[0].summary == "正在学习 Python"
    assert result.state_candidates[0].subject_type == "person"
    assert result.state_candidates[0].subject_key == "Alice"
    
    print("[PASS] from_dict 测试通过")


def test_json_roundtrip():
    """测试 JSON 序列化往返"""
    doc_time = TimeInfo(normalized="2024-03-15", source="explicit", raw="3月15日")
    event = Event(
        description="完成测试",
        time=doc_time,
        participants=["Alice", "Bob"],
        confidence=0.95
    )
    
    result = ExtractionResult(
        events=[event]
    )
    
    # 序列化
    json_str = json.dumps(result.to_dict(), ensure_ascii=False)
    
    # 反序列化
    data = json.loads(json_str)
    result2 = ExtractionResult.from_dict(data)
    
    assert len(result2.events) == 1
    assert result2.events[0].description == "完成测试"
    assert result2.events[0].time.normalized == "2024-03-15"
    assert result2.events[0].time.source == "explicit"
    assert result2.events[0].participants == ["Alice", "Bob"]
    
    print("[PASS] JSON 往返测试通过")


def test_time_source_values():
    """测试时间来源的各种值"""
    sources = ["explicit", "document_context", "inferred", "unknown"]
    
    for source in sources:
        time_info = TimeInfo(normalized="2024-03", source=source)
        assert time_info.source == source
    
    print("[PASS] 时间来源值测试通过")


if __name__ == "__main__":
    print("开始测试 ExtractionResult 新 schema...")
    print()
    
    try:
        test_basic_creation()
        test_with_data()
        test_to_dict()
        test_from_dict()
        test_json_roundtrip()
        test_time_source_values()
        
        print()
        print("=" * 50)
        print("所有测试通过!")
        print("=" * 50)
        
    except AssertionError as e:
        print(f"\n测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
