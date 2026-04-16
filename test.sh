#!/bin/bash
# 快速测试脚本

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "========================================"
echo "Markdown State Tracker - 快速测试"
echo "========================================"

# 1. 检查依赖
echo ""
echo "[1] 检查依赖..."
python -c "import openai; print('  ✓ OpenAI 已安装')" 2>/dev/null || echo "  ✗ OpenAI 未安装: pip install openai"
python -c "from dotenv import load_dotenv; print('  ✓ python-dotenv 已安装')" 2>/dev/null || echo "  ✗ python-dotenv 未安装: pip install python-dotenv"

# 2. 检查 API Key
echo ""
echo "[2] 检查 API Key..."
if [ -f ".env" ]; then
    if grep -q "OPENAI_API_KEY" .env; then
        echo "  ✓ .env 文件存在，已配置 API Key"
    else
        echo "  ✗ .env 文件存在但未配置 API Key"
    fi
else
    echo "  ⚠ .env 文件不存在，请执行: cp .env.example .env"
fi

# 3. 检查输入文档
echo ""
echo "[3] 检查输入文档..."
if [ -d "input_docs" ]; then
    count=$(find input_docs -name "*.md" | wc -l)
    echo "  ✓ 找到 $count 个 Markdown 文件"
else
    echo "  ✗ input_docs 目录不存在"
fi

# 4. 快速测试（跳过 LLM）
echo ""
echo "[4] 快速测试（跳过 LLM 抽取）..."
python main.py --init > /dev/null 2>&1
python main.py --skip-extraction > /tmp/test_output.txt 2>&1
if grep -q "处理完成" /tmp/test_output.txt; then
    echo "  ✓ 快速测试通过"
else
    echo "  ✗ 快速测试失败"
    cat /tmp/test_output.txt
fi

# 5. 检查数据库
echo ""
echo "[5] 检查数据库..."
if [ -f "data/state.db" ]; then
    echo "  ✓ 数据库文件存在"
    
    # 检查文档数
    doc_count=$(sqlite3 data/state.db "SELECT COUNT(*) FROM documents;" 2>/dev/null || echo "0")
    echo "    - 文档数: $doc_count"
    
    # 检查 chunks 数
    chunk_count=$(sqlite3 data/state.db "SELECT COUNT(*) FROM chunks;" 2>/dev/null || echo "0")
    echo "    - Chunks 数: $chunk_count"
    
    # 检查 extractions 数
    ext_count=$(sqlite3 data/state.db "SELECT COUNT(*) FROM extractions;" 2>/dev/null || echo "0")
    echo "    - Extractions 数: $ext_count"
else
    echo "  ✗ 数据库文件不存在"
fi

# 6. 检查输出文件
echo ""
echo "[6] 检查输出文件..."
if [ -f "output/status.md" ]; then
    lines=$(wc -l < output/status.md)
    echo "  ✓ 输出文件存在 ($lines 行)"
else
    echo "  ✗ 输出文件不存在"
fi

echo ""
echo "========================================"
echo "测试完成！"
echo "========================================"
echo ""
echo "后续步骤:"
echo "1. 编辑 .env，填入你的 OPENAI_API_KEY"
echo "2. 运行: python main.py"
echo "3. 查看: output/status.md"
echo ""
