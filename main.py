"""
主入口：运行完整流程
"""
import sys
import os
from pathlib import Path

# 确保项目根目录在 path 中
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 加载环境变量
try:
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from config import INPUT_DIR, OUTPUT_FILE
from db import init_db, close_connection, get_connection
from layers.input_layer import process_input
from layers.middle_layer import get_stats, get_pending_chunks, save_extraction, mark_document_processed
from layers.output_layer import generate_output


def run_extraction(pending_chunks: list, verbose: bool = True) -> dict:
    """
    运行抽取流程
    
    Args:
        pending_chunks: 待处理的 chunks
        verbose: 是否打印详细信息
    
    Returns:
        抽取结果统计
    """
    if not pending_chunks:
        return {'extracted': 0, 'failed': 0}
    
    # 检查是否有 API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        if verbose:
            print("  [跳过] 未设置 OPENAI_API_KEY，跳过 LLM 抽取")
            print("  提示: 请在 .env 文件中设置 OPENAI_API_KEY")
        return {'extracted': 0, 'failed': 0, 'skipped': len(pending_chunks)}
    
    # 导入抽取器
    from layers.extractors import LLMExtractor
    
    if verbose:
        print(f"  - 开始处理 {len(pending_chunks)} 个 chunks...")
    
    # 创建抽取器实例
    extractor = LLMExtractor()
    
    extracted = 0
    failed = 0
    processed_doc_ids = set()
    
    for i, chunk in enumerate(pending_chunks):
        try:
            # 准备上下文
            context = {
                'document_title': chunk.get('title'),
                'chunk_position': 'middle',  # 简化处理
            }
            
            # 抽取
            result = extractor.extract(chunk['text'], context)
            
            # 保存结果
            save_extraction(
                chunk_id=chunk['id'],
                result=result,
                extractor_type='llm',
                model_name=extractor.model,
                prompt_version='v1.0'
            )
            
            extracted += 1
            processed_doc_ids.add(chunk['document_id'])
            
            if verbose:
                entity_count = len(result.entities)
                state_count = len(result.state_candidates)
                print(f"    [{i+1}/{len(pending_chunks)}] chunk {chunk['id']}: "
                      f"{entity_count} 实体, {state_count} 状态候选")
            
        except Exception as e:
            failed += 1
            if verbose:
                print(f"    [{i+1}/{len(pending_chunks)}] chunk {chunk['id']}: 失败 - {e}")
    
    # 标记文档为已处理
    for doc_id in processed_doc_ids:
        mark_document_processed(doc_id)
    
    return {'extracted': extracted, 'failed': failed}


def run_pipeline(verbose: bool = True, skip_extraction: bool = False) -> dict:
    """运行完整处理流程
    
    Args:
        verbose: 是否打印详细信息
        skip_extraction: 是否跳过抽取步骤
    
    Returns:
        处理结果汇总
    """
    results = {}
    
    # 1. 初始化数据库
    if verbose:
        print("=" * 50)
        print("初始化数据库...")
    init_db()
    
    # 2. 输入层处理
    if verbose:
        print("\n[输入层] 扫描文档...")
    input_result = process_input()
    results['input'] = input_result
    
    if verbose:
        print(f"  - 扫描到 {input_result['total']} 个文档")
        print(f"  - 新增: {input_result['new']}, 修改: {input_result['modified']}")
        for p in input_result['processed']:
            status = "新增" if p['is_new'] else "更新"
            print(f"    [{status}] {p['path']} -> {p['chunk_count']} chunks")
    
    # 3. 中间层：抽取
    if verbose:
        print("\n[抽取层] 处理 chunks...")
    
    pending = get_pending_chunks()
    
    if skip_extraction:
        if verbose:
            print(f"  - 跳过抽取（--skip-extraction）")
        extraction_result = {'extracted': 0, 'failed': 0, 'skipped': len(pending)}
    else:
        extraction_result = run_extraction(pending, verbose)
    
    results['extraction'] = extraction_result
    
    # 4. 中间层状态
    if verbose:
        print("\n[中间层] 当前状态:")
    
    stats = get_stats()
    results['middle'] = {
        'stats': stats,
        'pending_chunks': len(get_pending_chunks())  # 重新获取
    }
    
    if verbose:
        print(f"  - 文档数: {stats['documents']}")
        print(f"  - Chunk 数: {stats['chunks']}")
        print(f"  - 已抽取: {stats['extractions']}")
        print(f"  - 待抽取 chunks: {results['middle']['pending_chunks']}")
        print(f"  - 活跃状态项: {stats['active_states']}")
    
    # 5. 输出层生成
    if verbose:
        print("\n[输出层] 生成状态文档...")
    output_result = generate_output()
    results['output'] = output_result
    
    if verbose:
        print(f"  - 输出文件: {output_result['output_path']}")
        print(f"  - 状态项数: {output_result['total_items']}")
        print(f"  - 快照 ID: {output_result['snapshot_id']}")
    
    if verbose:
        print("\n" + "=" * 50)
        print("处理完成!")
    
    return results


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='本地 Markdown 状态追踪系统')
    parser.add_argument('--init', action='store_true', help='强制重新初始化数据库')
    parser.add_argument('--quiet', '-q', action='store_true', help='安静模式')
    parser.add_argument('--stats', action='store_true', help='仅显示统计信息')
    parser.add_argument('--skip-extraction', action='store_true', help='跳过 LLM 抽取步骤')
    
    args = parser.parse_args()
    
    if args.init:
        print("强制重新初始化数据库...")
        init_db(force=True)
        print("完成。")
        return
    
    if args.stats:
        init_db()
        stats = get_stats()
        print("当前状态:")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        return
    
    try:
        run_pipeline(
            verbose=not args.quiet,
            skip_extraction=args.skip_extraction
        )
    finally:
        close_connection()


if __name__ == '__main__':
    main()
