"""
输出层：状态文档生成
"""
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
from time import perf_counter

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app_logging import get_logger, log_event
from config import OUTPUT_FILE
from db import get_connection


logger = get_logger("output")

# 输出模板配置
OUTPUT_CONFIG = {
    'dynamic': {
        'title': '动态状态',
        'description': '近期活跃、正在进行的事项',
        'subtypes': {
            'ongoing_project': '进行中的项目',
            'recent_event': '近期事件',
            'pending_task': '待办事项',
            'active_interest': '当前关注',
        },
        'max_items_per_subtype': 10,
    },
    'static': {
        'title': '稳定状态',
        'description': '长期不变或缓慢变化的信息',
        'subtypes': {
            'preference': '偏好设定',
            'background': '背景信息',
            'skill': '技能/能力',
            'relationship': '人际关系',
        },
        'max_items_per_subtype': 20,
    },
}


def select_states_for_output() -> Dict[str, List[Dict[str, Any]]]:
    """从中间层选择要输出的状态项
    
    这里实现"按需选取"逻辑，不是把整个中间层塞给输出
    """
    start_time = perf_counter()
    conn = get_connection()
    cursor = conn.cursor()
    
    result = {}
    
    for category, config in OUTPUT_CONFIG.items():
        result[category] = {}
        
        for subtype, subtype_label in config['subtypes'].items():
            max_items = config['max_items_per_subtype']
            
            # 按 last_updated 倒序取，保证最新的在前
            cursor.execute("""
                SELECT id,
                       COALESCE(display_summary, summary) AS summary,
                       detail,
                       confidence,
                       first_seen,
                       last_updated
                FROM states
                WHERE category = ? AND subtype = ? AND status = 'active'
                ORDER BY last_updated DESC
                LIMIT ?
            """, (category, subtype, max_items))
            
            items = [dict(row) for row in cursor.fetchall()]
            if items:
                result[category][subtype] = {
                    'label': subtype_label,
                    'items': items
                }
    
    total_items = sum(
        len(subtype_data['items'])
        for category_data in result.values()
        for subtype_data in category_data.values()
    )
    log_event(
        logger,
        logging.INFO,
        "states_selected_for_output",
        "Selected states for output generation",
        stage="output",
        total_items=total_items,
        duration_ms=(perf_counter() - start_time) * 1000,
    )
    return result


def format_julian_date(julian_day: Optional[float]) -> str:
    """将 SQLite 的 Julian Day 转换为可读日期"""
    if julian_day is None:
        return "未知"
    # Julian Day 2440587.5 = Unix epoch (1970-01-01)
    import datetime as dt
    try:
        unix_ts = (julian_day - 2440587.5) * 86400
        return dt.datetime.fromtimestamp(unix_ts).strftime('%Y-%m-%d')
    except:
        return "未知"


def generate_status_document(selected_states: Dict[str, Any]) -> str:
    """生成状态文档 Markdown"""
    lines = []
    
    # 头部
    lines.append("# 状态文档")
    lines.append("")
    lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # 按大类输出
    for category, config in OUTPUT_CONFIG.items():
        category_data = selected_states.get(category, {})
        
        lines.append(f"## {config['title']}")
        lines.append("")
        lines.append(f"*{config['description']}*")
        lines.append("")
        
        if not category_data:
            lines.append("*暂无数据*")
            lines.append("")
            continue
        
        for subtype, subtype_data in category_data.items():
            label = subtype_data['label']
            items = subtype_data['items']
            
            lines.append(f"### {label}")
            lines.append("")
            
            for item in items:
                summary = item['summary']
                detail = item.get('detail', '')
                confidence = item.get('confidence', 1.0)
                last_updated = format_julian_date(item.get('last_updated'))
                
                # 主要信息
                lines.append(f"- **{summary}**")
                
                # 详情（如果有）
                if detail:
                    lines.append(f"  - {detail}")
                
                # 元信息
                meta_parts = []
                if confidence < 1.0:
                    meta_parts.append(f"置信度: {confidence:.0%}")
                meta_parts.append(f"更新: {last_updated}")
                
                if meta_parts:
                    lines.append(f"  - *{' | '.join(meta_parts)}*")
                
                lines.append("")
        
        lines.append("---")
        lines.append("")
    
    # 归档区提示
    lines.append("## 归档区")
    lines.append("")
    lines.append("*已归档的历史状态可通过数据库查询获取*")
    lines.append("")
    
    return '\n'.join(lines)


def save_output(content: str, output_path: Path = OUTPUT_FILE) -> int:
    """保存输出文档并记录快照"""
    start_time = perf_counter()
    # 写入文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding='utf-8')
    
    # 记录快照
    conn = get_connection()
    cursor = conn.cursor()
    
    # 获取当前状态版本（简单用 states 表的最大 id）
    cursor.execute("SELECT MAX(id) FROM states")
    state_version = cursor.fetchone()[0] or 0
    
    cursor.execute("""
        INSERT INTO output_snapshots (content_md, source_state_version)
        VALUES (?, ?)
    """, (content, state_version))
    
    snapshot_id = cursor.lastrowid
    conn.commit()
    log_event(
        logger,
        logging.INFO,
        "output_saved",
        "Saved output document and snapshot",
        stage="output",
        output_path=output_path,
        snapshot_id=snapshot_id,
        total_items=content.count("\n- **"),
        duration_ms=(perf_counter() - start_time) * 1000,
    )
    
    return snapshot_id


def generate_output() -> Dict[str, Any]:
    """输出层主流程：选择 → 生成 → 保存
    
    Returns:
        处理结果信息
    """
    stage_start = perf_counter()
    # 1. 从中间层选择状态
    selected = select_states_for_output()
    
    # 2. 生成文档
    content = generate_status_document(selected)
    
    # 3. 保存
    snapshot_id = save_output(content)
    
    # 统计
    total_items = 0
    for cat_data in selected.values():
        for sub_data in cat_data.values():
            total_items += len(sub_data['items'])
    
    result = {
        'snapshot_id': snapshot_id,
        'output_path': str(OUTPUT_FILE),
        'total_items': total_items,
        'content_length': len(content)
    }
    log_event(
        logger,
        logging.INFO,
        "output_generation_done",
        "Completed output generation",
        stage="output",
        snapshot_id=snapshot_id,
        output_path=OUTPUT_FILE,
        total_items=total_items,
        duration_ms=(perf_counter() - stage_start) * 1000,
    )
    return result
