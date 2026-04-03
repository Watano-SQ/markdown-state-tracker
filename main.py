"""
主入口：运行完整流程
"""
import sys
from pathlib import Path

# 确保项目根目录在 path 中
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import INPUT_DIR, OUTPUT_FILE
from db import init_db, close_connection, get_connection
from layers.input_layer import process_input
from layers.middle_layer import get_stats, get_pending_chunks
from layers.output_layer import generate_output


def run_pipeline(verbose: bool = True) -> dict:
    """运行完整处理流程
    
    Args:
        verbose: 是否打印详细信息
    
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
    
    # 3. 中间层状态（抽取步骤预留）
    if verbose:
        print("\n[中间层] 当前状态:")
    
    pending = get_pending_chunks()
    stats = get_stats()
    results['middle'] = {
        'stats': stats,
        'pending_chunks': len(pending)
    }
    
    if verbose:
        print(f"  - 文档数: {stats['documents']}")
        print(f"  - Chunk 数: {stats['chunks']}")
        print(f"  - 待抽取 chunks: {len(pending)}")
        print(f"  - 活跃状态项: {stats['active_states']}")
    
    # 4. 输出层生成
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
        run_pipeline(verbose=not args.quiet)
    finally:
        close_connection()


if __name__ == '__main__':
    main()
