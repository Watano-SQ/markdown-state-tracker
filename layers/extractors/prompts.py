"""
Prompt 模板定义
"""
from typing import Dict, Any, Optional


# 系统角色提示词
SYSTEM_PROMPT = """你是一个专业的信息抽取助手，擅长从 Markdown 文本中提取结构化信息。

你的任务是准确识别：
1. **实体（entities）**：人物、工具、组织、地点、概念等
2. **事件（events）**：发生的具体事情，包含时间、参与者、地点
3. **状态候选（state_candidates）**：表示当前状态或偏好的信息
4. **关系候选（relation_candidates）**：对象之间的关系
5. **检索候选（retrieval_candidates）**：需要进一步明确的模糊对象（缩写、代称等）

重要原则：
1. 严格遵循 JSON Schema，所有字段类型必须正确
2. 时间信息必须标注来源（explicit/document_context/inferred/unknown）
3. state_candidates 必须尽量标注 subject_type 与 subject_key；主体不明时使用 subject_type=unknown，不要捏造
4. 对不确定的信息降低置信度（0.3-0.5），不要捏造
5. 检索候选用于标记需要进一步明确的对象
6. 如果某类信息不存在，返回空数组 []
7. 只返回 JSON，不要添加任何解释文字"""


# JSON Schema 定义
JSON_SCHEMA = """{
  "context": {
    "chunk_position": "start|middle|end（可选，文本在文档中的位置）",
    "document_title": "文档标题（可选）",
    "document_author": "文档作者线索（可选，不等同于状态主体）",
    "document_time": {"normalized": "文档默认时间（可选）", "source": "document_context", "raw": "原始时间（可选）"},
    "document_mode": "personal|team|hybrid（可选，文档解释模式）",
    "section": "所属章节标题（可选）"
  },
  "entities": [
    {
      "text": "实体文本（必需）",
      "type": "person|organization|tool|concept|location|product|event|other（必需）",
      "context": "上下文说明（可选）",
      "confidence": 0.0-1.0（必需，默认1.0）
    }
  ],
  "events": [
    {
      "description": "事件描述（必需）",
      "time": {
        "normalized": "YYYY-MM-DD 或 YYYY-MM 或 YYYY（可选）",
        "source": "explicit|document_context|inferred|unknown（必需）",
        "raw": "原始时间文本（可选）"
      },
      "participants": ["参与者列表（可选）"],
      "location": "地点（可选）",
      "context": "上下文（可选）",
      "confidence": 0.0-1.0（必需）
    }
  ],
  "state_candidates": [
    {
      "summary": "状态摘要（必需）",
      "canonical_summary": "稳定语义摘要（可选，用于 state identity）",
      "display_summary": "展示摘要（可选，用于输出文案）",
      "category": "dynamic|static（必需）",
      "subtype": "ongoing_project|recent_event|pending_task|active_interest|preference|background|skill|relationship|other（必需）",
      "detail": "详细信息（可选）",
      "time": {
        "normalized": "时间（可选）",
        "source": "explicit|document_context|inferred|unknown",
        "raw": "原始文本（可选）"
      },
      "subject_type": "person|team|project|organization|unknown（必需，状态主体类型）",
      "subject_key": "主体稳定标识；unknown 时可为空（可选）",
      "confidence": 0.0-1.0（必需）
    }
  ],
  "relation_candidates": [
    {
      "source": "源对象（必需）",
      "target": "目标对象（必需）",
      "relation_type": "uses|works_with|learning|belongs_to|related_to|depends_on|created|manages|other（必需）",
      "context": "关系上下文（可选）",
      "confidence": 0.0-1.0（必需）
    }
  ],
  "retrieval_candidates": [
    {
      "surface_form": "原始出现形式（必需）",
      "type_guess": "类型猜测（可选）",
      "context": "上下文（可选）",
      "priority": 0-10（必需，10为最高优先级）
    }
  ]
}"""


# 状态类型说明
STATE_TYPE_GUIDE = """
状态分类指南：
- dynamic（动态状态）：近期活跃、正在进行、可能变化的事项
  - ongoing_project: 进行中的项目
  - recent_event: 近期发生的事件
  - pending_task: 待办事项、计划中的任务
  - active_interest: 当前关注的领域或话题

- static（稳定状态）：长期不变或缓慢变化的信息
  - preference: 偏好设定（喜欢/不喜欢）
  - background: 背景信息（教育、职业等）
  - skill: 技能/能力
  - relationship: 人际关系
"""


# 时间来源说明
TIME_SOURCE_GUIDE = """
时间来源标注指南：
- explicit: 文本中明确写出的时间（如"2024年3月15日"、"去年12月"）
- document_context: 从文档标题或元信息推断（如标题是"2024年3月周报"）
- inferred: 从上下文推断但不确定（如"最近"、"上周"需要根据当前时间推算）
- unknown: 无法确定时间或未提及时间
"""


SUBJECT_ATTRIBUTION_GUIDE = """
主体归属指南：
- document_author 只是解释线索，不等同于状态主体
- document_mode 只表示文档整体倾向，不能替代候选级主体判断
- subject_type 可选值：person、team、project、organization、unknown
- subject_key 应尽量稳定，例如明确人名、团队名、项目名或组织名；不要用 summary 原文当 key
- 主体不明、只是通用建议、教程知识、引用资料或第三方事实时，使用 subject_type=unknown
"""


def build_user_prompt(
    text: str,
    context: Optional[Dict[str, Any]] = None,
    hints: Optional[Dict[str, Any]] = None
) -> str:
    """
    构建用户 prompt
    
    Args:
        text: chunk 文本内容
        context: 文档上下文（标题、默认时间等）
        hints: 规则预处理提取的提示信息
    
    Returns:
        格式化的 user prompt
    """
    context = context or {}
    hints = hints or {}
    
    # 构建上下文部分
    context_parts = []
    if context.get('document_title'):
        context_parts.append(f"- 文档标题: {context['document_title']}")
    if context.get('document_author'):
        context_parts.append(f"- 文档作者: {context['document_author']}")
    if context.get('document_time'):
        context_parts.append(f"- 文档时间: {_format_document_time(context['document_time'])}")
    if context.get('document_mode'):
        context_parts.append(f"- 文档模式: {context['document_mode']}")
    if context.get('chunk_position'):
        context_parts.append(f"- 文本位置: {context['chunk_position']}")
    if context.get('section'):
        context_parts.append(f"- 所属章节: {context['section']}")
    
    context_str = '\n'.join(context_parts) if context_parts else "无额外上下文"
    
    # 构建提示部分
    hints_str = ""
    if hints:
        hint_parts = []
        if hints.get('explicit_dates'):
            hint_parts.append(f"- 检测到的显式日期: {hints['explicit_dates']}")
        if hints.get('markdown_entities'):
            hint_parts.append(f"- Markdown 标记的实体: {hints['markdown_entities']}")
        if hint_parts:
            hints_str = f"\n【预处理提示】\n" + '\n'.join(hint_parts)
    
    return f"""请从以下文本中提取结构化信息，以 JSON 格式返回。

【待分析文本】
{text}

【文档上下文】
{context_str}
{hints_str}

【输出格式要求】
严格按照以下 JSON Schema 返回，只返回 JSON 对象，不要添加任何解释：

{JSON_SCHEMA}

{STATE_TYPE_GUIDE}

{TIME_SOURCE_GUIDE}

{SUBJECT_ATTRIBUTION_GUIDE}

【注意事项】
1. confidence 值：明确信息用 0.9-1.0，推断信息用 0.6-0.8，不确定用 0.3-0.5
2. 如果某类信息不存在，返回空数组 []
3. 检索候选（retrieval_candidates）用于标记缩写、代称、模糊指代等需要进一步明确的对象
4. 时间的 source 字段必填，normalized 字段尽量填写（如果能推断出具体或大致时间）
5. state_candidate 的 subject_type 必填；subject_type 不是 unknown 时，subject_key 必填"""


def _format_document_time(document_time: Any) -> str:
    """格式化文档时间上下文，避免把 dict 原样塞进 prompt。"""
    if isinstance(document_time, dict):
        normalized = document_time.get('normalized')
        source = document_time.get('source')
        raw = document_time.get('raw')
        parts = []
        if normalized:
            parts.append(str(normalized))
        if source:
            parts.append(f"source={source}")
        if raw and raw != normalized:
            parts.append(f"raw={raw}")
        return " / ".join(parts) if parts else str(document_time)

    return str(document_time)
