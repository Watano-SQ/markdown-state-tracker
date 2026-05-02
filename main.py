"""
主入口：运行完整流程
"""
import logging
import sys
import os
from pathlib import Path
from time import perf_counter

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

from app_logging import get_logger, log_event, setup_logging, shutdown_logging, summarize_text
from config import DEFAULT_LOG_FILE, INPUT_DIR, OUTPUT_FILE
from db import init_db, close_connection
from layers.aggregator import aggregate_extractions
from layers.input_layer import process_input
from layers.middle_layer import get_stats, get_pending_chunks, save_extraction, mark_document_processed
from layers.output_layer import generate_output


logger = get_logger("pipeline")


def _console_print(enabled: bool, message: str = "") -> None:
    """按需输出控制台摘要。"""
    if enabled:
        print(message)


def run_extraction(pending_chunks: list, verbose: bool = True) -> dict:
    """
    运行抽取流程
    
    Args:
        pending_chunks: 待处理的 chunks
        verbose: 是否输出控制台摘要
    
    Returns:
        抽取结果统计
    """
    if not pending_chunks:
        _console_print(verbose, "  - 没有待处理的 chunks")
        log_event(
            logger,
            logging.INFO,
            "extraction_queue_empty",
            "No pending chunks to extract",
            stage="extraction",
            pending_chunks=0,
        )
        return {'extracted': 0, 'failed': 0}
    
    # 检查是否有 API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        _console_print(verbose, "  [跳过] 未设置 OPENAI_API_KEY，跳过 LLM 抽取")
        _console_print(verbose, "  提示: 请在 .env 文件中设置 OPENAI_API_KEY")
        log_event(
            logger,
            logging.WARNING,
            "extraction_skipped",
            "Skipping extraction because API key is not configured",
            stage="extraction",
            pending_chunks=len(pending_chunks),
        )
        return {'extracted': 0, 'failed': 0, 'skipped': len(pending_chunks)}
    
    # 导入抽取器
    from layers.extractors import LLMExtractor
    
    _console_print(verbose, f"  - 开始处理 {len(pending_chunks)} 个 chunks...")

    # 创建抽取器实例
    extractor = LLMExtractor()
    
    extracted = 0
    failed = 0
    processed_doc_ids = set()
    
    for i, chunk in enumerate(pending_chunks):
        chunk_start = perf_counter()
        log_context = {
            'document_id': chunk['document_id'],
            'path': chunk.get('path'),
            'title': chunk.get('title'),
            'chunk_id': chunk['id'],
            'chunk_index': chunk.get('chunk_index'),
            'token_estimate': chunk.get('token_estimate'),
        }
        text_preview = summarize_text(chunk.get('text'), 120)

        log_event(
            logger,
            logging.INFO,
            "chunk_extract_start",
            "Starting chunk extraction",
            stage="extraction",
            attempt=i + 1,
            pending_chunks=len(pending_chunks),
            text_preview=text_preview,
            **log_context,
        )

        try:
            # 准备上下文
            context = {
                'document_title': chunk.get('title'),
                'chunk_position': 'middle',  # 简化处理
                'section': chunk.get('section_label'),
            }
            
            # 抽取
            result = extractor.extract(chunk['text'], context, log_context=log_context)
            
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
            entity_count = len(result.entities)
            state_count = len(result.state_candidates)
            relation_count = len(result.relation_candidates)
            retrieval_count = len(result.retrieval_candidates)
            _console_print(
                verbose,
                f"    [{i+1}/{len(pending_chunks)}] chunk {chunk['id']}: "
                f"{entity_count} 实体, {state_count} 状态候选"
            )
            log_event(
                logger,
                logging.INFO,
                "chunk_extract_done",
                "Chunk extraction completed",
                stage="extraction",
                model=getattr(extractor, 'model', None),
                provider=getattr(extractor, 'provider', None),
                entity_count=entity_count,
                state_candidate_count=state_count,
                relation_candidate_count=relation_count,
                retrieval_candidate_count=retrieval_count,
                duration_ms=(perf_counter() - chunk_start) * 1000,
                text_preview=text_preview,
                **log_context,
            )
            
        except Exception as e:
            failed += 1
            _console_print(
                verbose,
                f"    [{i+1}/{len(pending_chunks)}] chunk {chunk['id']}: 失败 - {e}"
            )
            logger.exception(
                "Chunk extraction failed",
                extra={
                    'event': 'chunk_extract_failed',
                    'stage': 'extraction',
                    'error_type': type(e).__name__,
                    'duration_ms': (perf_counter() - chunk_start) * 1000,
                    'text_preview': text_preview,
                    **log_context,
                },
            )
    
    # 标记文档为已处理
    completed_doc_ids = set()
    for doc_id in processed_doc_ids:
        if mark_document_processed(doc_id):
            completed_doc_ids.add(doc_id)
    
    log_event(
        logger,
        logging.INFO,
        "extraction_batch_done",
        "Completed extraction batch",
        stage="extraction",
        extracted=extracted,
        failed=failed,
        processed_documents=len(completed_doc_ids),
        incomplete_documents=len(processed_doc_ids) - len(completed_doc_ids),
        pending_chunks=len(pending_chunks),
    )
    return {'extracted': extracted, 'failed': failed}


def run_pipeline(skip_extraction: bool = False, verbose: bool = True) -> dict:
    """运行完整处理流程
    
    Args:
        skip_extraction: 是否跳过抽取步骤
        verbose: 是否输出控制台摘要
    
    Returns:
        处理结果汇总
    """
    results = {}
    run_start = perf_counter()

    log_event(
        logger,
        logging.INFO,
        "run_start",
        "Pipeline run started",
        stage="pipeline",
        input_dir=INPUT_DIR,
        output_file=OUTPUT_FILE,
    )
    
    try:
        # 1. 初始化数据库
        db_start = perf_counter()
        _console_print(verbose, "=" * 50)
        _console_print(verbose, "初始化数据库...")
        log_event(logger, logging.INFO, "db_init_start", "Initializing database", stage="pipeline")
        init_db()
        log_event(
            logger,
            logging.INFO,
            "db_init_done",
            "Database initialization completed",
            stage="pipeline",
            duration_ms=(perf_counter() - db_start) * 1000,
        )
        
        # 2. 输入层处理
        input_start = perf_counter()
        _console_print(verbose, "\n[输入层] 扫描文档...")
        log_event(logger, logging.INFO, "input_scan_start", "Starting input scan", stage="pipeline")
        input_result = process_input()
        results['input'] = input_result
        _console_print(verbose, f"  - 扫描到 {input_result['total']} 个文档")
        _console_print(verbose, f"  - 新增: {input_result['new']}, 修改: {input_result['modified']}")
        if input_result.get('skipped'):
            _console_print(verbose, f"  - 显式排除: {input_result['skipped']}")
        if input_result.get('purged_excluded'):
            _console_print(verbose, f"  - 清理旧排除文档: {input_result['purged_excluded']}")
        for processed in input_result['processed']:
            status = "新增" if processed['is_new'] else "更新"
            _console_print(verbose, f"    [{status}] {processed['path']} -> {processed['chunk_count']} chunks")
        log_event(
            logger,
            logging.INFO,
            "input_scan_done",
            "Input scan completed",
            stage="pipeline",
            total_documents=input_result['total'],
            new_documents=input_result['new'],
            modified_documents=input_result['modified'],
            skipped_documents=input_result.get('skipped', 0),
            purged_documents=input_result.get('purged_excluded', 0),
            processed_documents=len(input_result['processed']),
            duration_ms=(perf_counter() - input_start) * 1000,
        )
        
        # 3. 中间层：抽取
        _console_print(verbose, "\n[抽取层] 处理 chunks...")
        pending = get_pending_chunks()
        log_event(
            logger,
            logging.INFO,
            "extraction_queue_loaded",
            "Loaded pending extraction queue",
            stage="pipeline",
            pending_chunks=len(pending),
        )
        
        if skip_extraction:
            extraction_result = {'extracted': 0, 'failed': 0, 'skipped': len(pending)}
            _console_print(verbose, "  - 跳过抽取（--skip-extraction）")
            log_event(
                logger,
                logging.INFO,
                "extraction_skipped",
                "Skipping extraction step by CLI flag",
                stage="pipeline",
                pending_chunks=len(pending),
            )
        else:
            extraction_result = run_extraction(pending, verbose=verbose)
        
        results['extraction'] = extraction_result
        
        # 4. 聚合层：state_candidates -> states
        _console_print(verbose, "\n[聚合层] 聚合状态候选...")
        log_event(logger, logging.INFO, "aggregation_start", "Starting state aggregation", stage="pipeline")
        aggregation_result = aggregate_extractions()
        results['aggregation'] = aggregation_result
        _console_print(verbose, f"  - 源 extraction 数: {aggregation_result['source_extractions']}")
        _console_print(verbose, f"  - 状态候选数: {aggregation_result['state_candidates']}")
        _console_print(verbose, f"  - 聚合写入数: {aggregation_result['aggregated_candidates']}")
        _console_print(verbose, f"  - 触达状态数: {aggregation_result['touched_states']}")
        _console_print(verbose, f"  - 新增证据数: {aggregation_result['evidence_added']}")
        log_event(
            logger,
            logging.INFO,
            "aggregation_stage_done",
            "State aggregation completed",
            stage="pipeline",
            extractions=aggregation_result['source_extractions'],
            state_candidates=aggregation_result['state_candidates'],
            aggregated_candidates=aggregation_result['aggregated_candidates'],
            touched_states=aggregation_result['touched_states'],
            evidence_added=aggregation_result['evidence_added'],
            invalid_extractions=aggregation_result['invalid_extractions'],
            skipped_candidates=aggregation_result['skipped_candidates'],
            orphan_states_archived=aggregation_result['orphan_states_archived'],
        )

        # 5. 中间层状态
        stats = get_stats()
        pending_after = len(get_pending_chunks())
        results['middle'] = {
            'stats': stats,
            'pending_chunks': pending_after
        }
        _console_print(verbose, "\n[中间层] 当前状态:")
        _console_print(verbose, f"  - 文档数: {stats['documents']}")
        _console_print(verbose, f"  - Chunk 数: {stats['chunks']}")
        _console_print(verbose, f"  - 已抽取: {stats['extractions']}")
        _console_print(verbose, f"  - 待抽取 chunks: {pending_after}")
        _console_print(verbose, f"  - 活跃状态项: {stats['active_states']}")
        log_event(
            logger,
            logging.INFO,
            "middle_stats_collected",
            "Collected middle-layer statistics",
            stage="pipeline",
            pending_chunks=pending_after,
            documents=stats['documents'],
            chunks=stats['chunks'],
            extractions=stats['extractions'],
            active_states=stats['active_states'],
        )
        
        # 6. 输出层生成
        output_start = perf_counter()
        _console_print(verbose, "\n[输出层] 生成状态文档...")
        log_event(logger, logging.INFO, "output_generate_start", "Starting output generation", stage="pipeline")
        output_result = generate_output()
        results['output'] = output_result
        _console_print(verbose, f"  - 输出文件: {output_result['output_path']}")
        _console_print(verbose, f"  - 状态项数: {output_result['total_items']}")
        _console_print(verbose, f"  - 快照 ID: {output_result['snapshot_id']}")
        log_event(
            logger,
            logging.INFO,
            "output_generate_done",
            "Output generation completed",
            stage="pipeline",
            output_path=output_result['output_path'],
            total_items=output_result['total_items'],
            snapshot_id=output_result['snapshot_id'],
            duration_ms=(perf_counter() - output_start) * 1000,
        )
        
        log_event(
            logger,
            logging.INFO,
            "run_end",
            "Pipeline run completed",
            stage="pipeline",
            duration_ms=(perf_counter() - run_start) * 1000,
            pending_chunks=results['middle']['pending_chunks'],
            total_documents=results['input']['total'],
            total_items=results['output']['total_items'],
        )
        _console_print(verbose, "\n" + "=" * 50)
        _console_print(verbose, "处理完成!")
        return results
    except Exception as e:
        logger.exception(
            "Pipeline run failed",
            extra={
                'event': 'run_failed',
                'stage': 'pipeline',
                'error_type': type(e).__name__,
                'duration_ms': (perf_counter() - run_start) * 1000,
            },
        )
        raise


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='本地 Markdown 状态追踪系统')
    parser.add_argument('--init', action='store_true', help='强制重新初始化数据库')
    parser.add_argument('--quiet', '-q', action='store_true', help='安静模式')
    parser.add_argument('--stats', action='store_true', help='仅显示统计信息')
    parser.add_argument('--skip-extraction', action='store_true', help='跳过 LLM 抽取步骤')
    parser.add_argument('--log-level', default='INFO', help='日志级别（默认: INFO）')
    parser.add_argument('--log-file', default=str(DEFAULT_LOG_FILE), help='日志文件路径')
    
    args = parser.parse_args()
    setup_logging(log_file=args.log_file, level=args.log_level, quiet=args.quiet)
    
    try:
        log_event(
            logger,
            logging.INFO,
            "cli_invoked",
            "CLI command invoked",
            stage="cli",
            init=args.init,
            stats=args.stats,
            skip_extraction=args.skip_extraction,
            log_file=args.log_file,
            log_level=args.log_level,
        )

        if args.init:
            print("强制重新初始化数据库...")
            init_db(force=True)
            print("完成。")
            log_event(logger, logging.INFO, "cli_init_done", "Forced database initialization completed", stage="cli")
            return
        
        if args.stats:
            init_db()
            stats = get_stats()
            print("当前状态:")
            for k, v in stats.items():
                print(f"  {k}: {v}")
            log_event(logger, logging.INFO, "cli_stats_done", "Printed statistics to console", stage="cli", **stats)
            return

        run_pipeline(skip_extraction=args.skip_extraction, verbose=not args.quiet)
    finally:
        close_connection()
        shutdown_logging()


if __name__ == '__main__':
    main()
