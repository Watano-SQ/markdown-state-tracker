"""
测试 ExtractionResult 新 schema 的正确性
"""
import sys
import json
import unittest
from pathlib import Path

# 确保可以导入 layers 模块
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from layers.middle_layer import (
    ExtractionResult, ExtractionContext, TimeInfo,
    Entity, Event, StateCandidate, RelationCandidate, RetrievalCandidate,
    SourceContextBlock,
)
from layers.extractors.llm_extractor import LLMExtractor


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
        section="技术学习",
        source_context_blocks=[
            SourceContextBlock(
                source_block_id=10,
                source_type="table_block",
                section_label="技术学习",
                text_preview="| 工具 | 用途 |",
                start_offset=20,
                end_offset=80,
            )
        ],
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
            canonical_summary="学习 Rust 编程语言",
            display_summary="正在学习 Rust 编程语言",
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
    assert len(result.context.source_context_blocks) == 1
    assert result.context.source_context_blocks[0].source_type == "table_block"
    assert result.state_candidates[0].subject_type == "person"
    assert result.state_candidates[0].subject_key == "Alice"
    assert result.state_candidates[0].canonical_summary == "学习 Rust 编程语言"
    assert result.state_candidates[0].display_summary == "正在学习 Rust 编程语言"
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
            "section": "测试章节",
            "source_context_blocks": [
                {
                    "source_block_id": 7,
                    "source_type": "quote_material",
                    "section_label": "测试章节",
                    "text_preview": "引用上下文",
                    "start_offset": 10,
                    "end_offset": 20,
                    "ignored_extra": "ok"
                }
            ],
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
                "canonical_summary": "学习 Python",
                "display_summary": "正在学习 Python",
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
    assert len(result.context.source_context_blocks) == 1
    assert result.context.source_context_blocks[0].source_block_id == 7
    assert result.context.source_context_blocks[0].source_type == "quote_material"
    assert len(result.entities) == 1
    assert result.entities[0].text == "Python"
    assert len(result.events) == 1
    assert result.events[0].time.source == "explicit"
    assert result.events[0].participants == ["Alice"]
    assert len(result.state_candidates) == 1
    assert result.state_candidates[0].summary == "正在学习 Python"
    assert result.state_candidates[0].canonical_summary == "学习 Python"
    assert result.state_candidates[0].display_summary == "正在学习 Python"
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


def test_llm_extractor_preserves_canonical_context():
    """测试 LLM 漏回或改写 context 时，保存代码侧 canonical context。"""
    extractor = object.__new__(LLMExtractor)

    def fake_call(_user_prompt, log_context=None):
        return {
            "context": {
                "document_title": "LLM 改写标题",
                "source_context_blocks": []
            },
            "entities": [],
            "events": [],
            "state_candidates": [],
            "relation_candidates": [],
            "retrieval_candidates": [],
        }

    extractor._call_llm_with_retry = fake_call
    canonical_context = {
        "document_title": "代码侧标题",
        "document_author": "代码侧作者",
        "chunk_position": "middle",
        "section": "进展",
        "source_context_blocks": [
            {
                "source_block_id": 42,
                "source_type": "table_block",
                "section_label": "进展",
                "text_preview": "表格上下文",
                "start_offset": 100,
                "end_offset": 180,
            }
        ],
    }

    result = LLMExtractor.extract(
        extractor,
        "今天我完成了 canonical context 持久化。",
        canonical_context,
    )

    assert result.context.document_title == "代码侧标题"
    assert result.context.document_author == "代码侧作者"
    assert len(result.context.source_context_blocks) == 1
    assert result.context.source_context_blocks[0].source_block_id == 42
    assert result.context.source_context_blocks[0].source_type == "table_block"

    print("[PASS] canonical context 持久化测试通过")


class ExtractionSchemaTests(unittest.TestCase):
    def test_basic_creation(self):
        test_basic_creation()

    def test_with_data(self):
        test_with_data()

    def test_to_dict(self):
        test_to_dict()

    def test_from_dict(self):
        test_from_dict()

    def test_json_roundtrip(self):
        test_json_roundtrip()

    def test_time_source_values(self):
        test_time_source_values()

    def test_llm_extractor_preserves_canonical_context(self):
        test_llm_extractor_preserves_canonical_context()


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
        test_llm_extractor_preserves_canonical_context()
        
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
