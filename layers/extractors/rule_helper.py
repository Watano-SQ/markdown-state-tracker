"""
规则辅助处理：预处理和后处理
"""
import re
from typing import Dict, Any, List, Optional


def preprocess_text(text: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    规则预处理：提取显式信息作为 LLM 的辅助提示
    
    Args:
        text: chunk 文本
        context: 文档上下文
    
    Returns:
        预处理结果，包含原文本和提取的提示信息
    """
    hints = {}
    
    # 1. 提取显式日期
    explicit_dates = extract_explicit_dates(text)
    if explicit_dates:
        hints['explicit_dates'] = explicit_dates
    
    # 2. 提取 Markdown 标记的实体（加粗、代码块）
    markdown_entities = extract_markdown_entities(text)
    if markdown_entities:
        hints['markdown_entities'] = markdown_entities
    
    # 3. 提取章节标题（如果有）
    sections = extract_sections(text)
    if sections:
        hints['sections'] = sections
    
    return {
        'text': text,
        'hints': hints
    }


def extract_explicit_dates(text: str) -> List[str]:
    """提取显式日期表达"""
    dates = []
    
    # 中文日期格式
    patterns = [
        r'\d{4}年\d{1,2}月\d{1,2}日',  # 2024年3月15日
        r'\d{4}年\d{1,2}月',            # 2024年3月
        r'\d{1,2}月\d{1,2}日',          # 3月15日
        r'\d{4}-\d{2}-\d{2}',           # 2024-03-15
        r'\d{4}/\d{2}/\d{2}',           # 2024/03/15
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        dates.extend(matches)
    
    return list(set(dates))


def extract_markdown_entities(text: str) -> List[Dict[str, str]]:
    """提取 Markdown 标记的实体"""
    entities = []
    
    # 加粗文本：**text** 或 __text__
    bold_pattern = r'\*\*([^*]+)\*\*|__([^_]+)__'
    for match in re.finditer(bold_pattern, text):
        entity_text = match.group(1) or match.group(2)
        if entity_text and len(entity_text) < 50:  # 过滤过长的内容
            entities.append({
                'text': entity_text,
                'marker': 'bold'
            })
    
    # 行内代码：`text`
    code_pattern = r'`([^`]+)`'
    for match in re.finditer(code_pattern, text):
        entity_text = match.group(1)
        if entity_text and len(entity_text) < 50:
            entities.append({
                'text': entity_text,
                'marker': 'code'
            })
    
    return entities


def extract_sections(text: str) -> List[str]:
    """提取章节标题"""
    sections = []
    
    # Markdown 标题：# ## ### 等
    header_pattern = r'^#{1,6}\s+(.+)$'
    for line in text.split('\n'):
        match = re.match(header_pattern, line.strip())
        if match:
            sections.append(match.group(1))
    
    return sections


def postprocess_result(result: Dict[str, Any], preprocessed: Dict[str, Any]) -> Dict[str, Any]:
    """
    规则后处理：验证和修复 LLM 输出
    
    Args:
        result: LLM 返回的 JSON 结果
        preprocessed: 预处理信息
    
    Returns:
        修复后的结果
    """
    # 1. 确保所有必需字段存在
    result = ensure_required_fields(result)
    
    # 2. 验证和修复置信度值
    result = fix_confidence_values(result)
    
    # 3. 验证时间来源
    result = fix_time_sources(result)
    
    # 4. 去重实体
    result = deduplicate_entities(result)
    
    return result


def ensure_required_fields(result: Dict[str, Any]) -> Dict[str, Any]:
    """确保所有必需字段存在"""
    default_structure = {
        'context': {
            'chunk_position': None,
            'section': None
        },
        'entities': [],
        'events': [],
        'state_candidates': [],
        'relation_candidates': [],
        'retrieval_candidates': []
    }
    
    # 合并默认值
    for key, default_value in default_structure.items():
        if key not in result:
            result[key] = default_value
        elif key == 'context' and isinstance(default_value, dict):
            for sub_key, sub_default in default_value.items():
                if sub_key not in result[key]:
                    result[key][sub_key] = sub_default
    
    return result


def fix_confidence_values(result: Dict[str, Any]) -> Dict[str, Any]:
    """修复置信度值"""
    def fix_confidence(item: Dict[str, Any]) -> Dict[str, Any]:
        if 'confidence' not in item:
            item['confidence'] = 1.0
        else:
            # 确保在 0-1 范围内
            conf = item['confidence']
            if isinstance(conf, (int, float)):
                item['confidence'] = max(0.0, min(1.0, float(conf)))
            else:
                item['confidence'] = 1.0
        return item
    
    # 修复各类列表中的置信度
    for key in ['entities', 'events', 'state_candidates', 'relation_candidates']:
        if key in result and isinstance(result[key], list):
            result[key] = [fix_confidence(item) for item in result[key]]
    
    return result


def fix_time_sources(result: Dict[str, Any]) -> Dict[str, Any]:
    """修复时间来源字段"""
    valid_sources = {'explicit', 'document_context', 'inferred', 'unknown'}
    
    def fix_time(time_obj: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not time_obj or not isinstance(time_obj, dict):
            return None
        
        # 确保 source 字段有效
        if 'source' not in time_obj or time_obj['source'] not in valid_sources:
            time_obj['source'] = 'unknown'
        
        return time_obj
    
    # 修复 events 中的时间
    if 'events' in result and isinstance(result['events'], list):
        for event in result['events']:
            if 'time' in event:
                event['time'] = fix_time(event['time'])
    
    # 修复 state_candidates 中的时间
    if 'state_candidates' in result and isinstance(result['state_candidates'], list):
        for state in result['state_candidates']:
            if 'time' in state:
                state['time'] = fix_time(state['time'])
    
    return result


def deduplicate_entities(result: Dict[str, Any]) -> Dict[str, Any]:
    """去重实体"""
    if 'entities' not in result or not isinstance(result['entities'], list):
        return result
    
    seen = set()
    unique_entities = []
    
    for entity in result['entities']:
        if not isinstance(entity, dict) or 'text' not in entity:
            continue
        
        key = (entity['text'].lower(), entity.get('type', 'other'))
        if key not in seen:
            seen.add(key)
            unique_entities.append(entity)
    
    result['entities'] = unique_entities
    return result
