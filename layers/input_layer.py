"""
输入层：文档扫描、切分、抽取
"""
import hashlib
import os
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import INPUT_DIR
from db import get_connection


@dataclass
class DocumentInfo:
    """文档信息"""
    path: str
    title: str
    modified_time: float
    content: str
    content_hash: str


@dataclass  
class Chunk:
    """文档片段（仅包含正文切分结果）
    
    Attributes:
        text: 片段文本内容
        index: 片段在文档中的序号（从0开始）
        token_estimate: token 数量估算（可选）
        start_offset: 在原文中的起始位置（可选）
        end_offset: 在原文中的结束位置（可选）
        section_label: 所属章节标签（可选）
    """
    text: str
    index: int
    token_estimate: Optional[int] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    section_label: Optional[str] = None


def compute_hash(content: str) -> str:
    """计算内容 hash"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数（中英文混合，简单按字符估算）"""
    # 简单启发式：中文约 1.5 token/字，英文约 0.25 token/词
    # 这里用粗略估计：字符数 / 2
    return max(1, len(text) // 2)


def extract_title(content: str, filepath: Path) -> str:
    """提取文档标题"""
    # 尝试从第一行 # 标题提取
    lines = content.strip().split('\n')
    for line in lines[:5]:  # 只检查前5行
        line = line.strip()
        if line.startswith('# '):
            return line[2:].strip()
    # 否则用文件名
    return filepath.stem


def scan_documents(input_dir: Path = INPUT_DIR) -> List[DocumentInfo]:
    """扫描目录中的所有 md 文件"""
    documents = []
    
    for md_file in input_dir.rglob('*.md'):
        content = md_file.read_text(encoding='utf-8')
        doc = DocumentInfo(
            path=str(md_file.relative_to(input_dir)),
            title=extract_title(content, md_file),
            modified_time=md_file.stat().st_mtime,
            content=content,
            content_hash=compute_hash(content)
        )
        documents.append(doc)
    
    return documents


def get_changed_documents(documents: List[DocumentInfo]) -> Tuple[List[DocumentInfo], List[DocumentInfo]]:
    """识别新增和修改过的文档
    
    Returns:
        (new_docs, modified_docs)
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    new_docs = []
    modified_docs = []
    
    for doc in documents:
        cursor.execute(
            "SELECT id, content_hash FROM documents WHERE path = ?",
            (doc.path,)
        )
        row = cursor.fetchone()
        
        if row is None:
            new_docs.append(doc)
        elif row['content_hash'] != doc.content_hash:
            modified_docs.append(doc)
    
    return new_docs, modified_docs


def chunk_document(content: str, max_tokens: int = 500) -> List[Chunk]:
    """将文档切分为 chunks
    
    策略：按段落切分，超长段落再按句子切分
    保留 offset 信息以便追溯原文位置
    """
    chunks = []
    
    # 按空行分段
    paragraphs = re.split(r'\n\s*\n', content)
    
    current_chunk = []
    current_tokens = 0
    chunk_index = 0
    current_offset = 0  # 跟踪当前处理位置
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            # 计算跳过的空白字符
            current_offset = content.find(para, current_offset) if para else current_offset + 2
            continue
        
        # 找到段落在原文中的位置
        para_start = content.find(para, current_offset)
        para_end = para_start + len(para)
        current_offset = para_end
            
        para_tokens = estimate_tokens(para)
        
        # 如果单个段落超长，需要进一步切分
        if para_tokens > max_tokens:
            # 先保存当前累积的 chunk
            if current_chunk:
                chunk_text = '\n\n'.join(current_chunk)
                chunk_start = content.find(current_chunk[0])
                chunk_end = chunk_start + len(chunk_text)
                
                chunks.append(Chunk(
                    text=chunk_text,
                    index=chunk_index,
                    token_estimate=current_tokens,
                    start_offset=chunk_start,
                    end_offset=chunk_end
                ))
                chunk_index += 1
                current_chunk = []
                current_tokens = 0
            
            # 按句子切分超长段落
            sentences = re.split(r'([。！？.!?])', para)
            temp_chunk = []
            temp_tokens = 0
            temp_start = para_start
            
            i = 0
            while i < len(sentences):
                sent = sentences[i]
                # 把标点附加到句子上
                if i + 1 < len(sentences) and len(sentences[i+1]) == 1:
                    sent += sentences[i+1]
                    i += 1
                
                sent_tokens = estimate_tokens(sent)
                if temp_tokens + sent_tokens > max_tokens and temp_chunk:
                    chunk_text = ''.join(temp_chunk)
                    chunks.append(Chunk(
                        text=chunk_text,
                        index=chunk_index,
                        token_estimate=temp_tokens,
                        start_offset=temp_start,
                        end_offset=temp_start + len(chunk_text)
                    ))
                    chunk_index += 1
                    temp_chunk = []
                    temp_tokens = 0
                    temp_start = temp_start + len(chunk_text)
                
                temp_chunk.append(sent)
                temp_tokens += sent_tokens
                i += 1
            
            if temp_chunk:
                chunk_text = ''.join(temp_chunk)
                chunks.append(Chunk(
                    text=chunk_text,
                    index=chunk_index,
                    token_estimate=temp_tokens,
                    start_offset=temp_start,
                    end_offset=temp_start + len(chunk_text)
                ))
                chunk_index += 1
        
        # 正常段落
        elif current_tokens + para_tokens > max_tokens and current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunk_start = content.find(current_chunk[0])
            chunk_end = chunk_start + len(chunk_text)
            
            chunks.append(Chunk(
                text=chunk_text,
                index=chunk_index,
                token_estimate=current_tokens,
                start_offset=chunk_start,
                end_offset=chunk_end
            ))
            chunk_index += 1
            current_chunk = [para]
            current_tokens = para_tokens
        else:
            current_chunk.append(para)
            current_tokens += para_tokens
    
    # 保存最后的 chunk
    if current_chunk:
        chunk_text = '\n\n'.join(current_chunk)
        chunk_start = content.find(current_chunk[0])
        chunk_end = chunk_start + len(chunk_text)
        
        chunks.append(Chunk(
            text=chunk_text,
            index=chunk_index,
            token_estimate=current_tokens,
            start_offset=chunk_start,
            end_offset=chunk_end
        ))
    
    return chunks


def save_document_and_chunks(doc: DocumentInfo, chunks: List[Chunk]) -> int:
    """保存文档和 chunks 到数据库，返回 document_id"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 检查是否已存在
    cursor.execute("SELECT id FROM documents WHERE path = ?", (doc.path,))
    existing = cursor.fetchone()
    
    if existing:
        doc_id = existing['id']
        # 更新文档
        cursor.execute("""
            UPDATE documents 
            SET title = ?, modified_time = ?, content_hash = ?, 
                status = 'pending', updated_at = julianday('now')
            WHERE id = ?
        """, (doc.title, doc.modified_time, doc.content_hash, doc_id))
        
        # 删除旧 chunks（CASCADE 会删除相关 extractions）
        cursor.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
    else:
        # 插入新文档
        cursor.execute("""
            INSERT INTO documents (path, title, modified_time, content_hash, status)
            VALUES (?, ?, ?, ?, 'pending')
        """, (doc.path, doc.title, doc.modified_time, doc.content_hash))
        doc_id = cursor.lastrowid
    
    # 插入 chunks
    for chunk in chunks:
        cursor.execute("""
            INSERT INTO chunks (document_id, chunk_index, text, token_estimate, 
                              start_offset, end_offset, section_label)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (doc_id, chunk.index, chunk.text, chunk.token_estimate,
              chunk.start_offset, chunk.end_offset, chunk.section_label))
    
    conn.commit()
    return doc_id


def process_input(input_dir: Path = INPUT_DIR) -> Dict[str, Any]:
    """输入层主流程：扫描 → 识别变更 → 切分 → 存储
    
    Returns:
        处理统计信息
    """
    # 1. 扫描文档
    documents = scan_documents(input_dir)
    
    if not documents:
        return {'total': 0, 'new': 0, 'modified': 0, 'processed': []}
    
    # 2. 识别变更
    new_docs, modified_docs = get_changed_documents(documents)
    docs_to_process = new_docs + modified_docs
    
    # 3. 处理每个文档
    processed = []
    for doc in docs_to_process:
        chunks = chunk_document(doc.content)
        doc_id = save_document_and_chunks(doc, chunks)
        processed.append({
            'path': doc.path,
            'title': doc.title,
            'doc_id': doc_id,
            'chunk_count': len(chunks),
            'is_new': doc in new_docs
        })
    
    return {
        'total': len(documents),
        'new': len(new_docs),
        'modified': len(modified_docs),
        'processed': processed
    }
