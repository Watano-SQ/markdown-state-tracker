"""
测试 font 标签过滤逻辑
"""
import sys
from pathlib import Path

# 确保可以导入 layers 模块
sys.path.insert(0, str(Path(__file__).parent))

from layers.extractors.rule_helper import strip_font_tags, preprocess_text


def test_strip_font_tags_basic() -> None:
    """基础场景：移除 font 标签并保留内部文本。"""
    text = '前缀 <font style="color:rgb(31, 31, 31);">正文</font> 后缀'
    cleaned = strip_font_tags(text)
    assert cleaned == '前缀 正文 后缀'
    print('[PASS] 基础 font 标签过滤测试通过')


def test_strip_font_tags_empty() -> None:
    """空标签场景：仅删除标签本身。"""
    text = 'A<font style="color:rgb(31, 31, 31);"></font>B'
    cleaned = strip_font_tags(text)
    assert cleaned == 'AB'
    print('[PASS] 空 font 标签测试通过')


def test_strip_font_tags_case_and_attrs() -> None:
    """大小写与多属性场景。"""
    text = '<FONT size="3" color="red">ABC</FONT>'
    cleaned = strip_font_tags(text)
    assert cleaned == 'ABC'
    print('[PASS] 大小写与属性变体测试通过')


def test_non_font_tags_unchanged() -> None:
    """非 font 标签不应受影响。"""
    text = '保留 <span style="color:red">span</span> 与 <div>block</div>'
    cleaned = strip_font_tags(text)
    assert cleaned == text
    print('[PASS] 非 font 标签不受影响测试通过')


def test_preprocess_text_integration() -> None:
    """集成场景：preprocess_text 返回文本已清洗且 hints 仍可提取。"""
    text = '今天是2024年3月15日。<font style="color:rgb(31, 31, 31);">**Python**</font>'
    processed = preprocess_text(text, context={})

    assert '<font' not in processed['text'].lower()
    assert '</font>' not in processed['text'].lower()
    assert '**Python**' in processed['text']

    hints = processed['hints']
    assert 'explicit_dates' in hints
    assert '2024年3月15日' in hints['explicit_dates']

    assert 'markdown_entities' in hints
    entities = hints['markdown_entities']
    assert any(e.get('text') == 'Python' and e.get('marker') == 'bold' for e in entities)

    print('[PASS] preprocess_text 集成测试通过')


if __name__ == '__main__':
    print('开始测试 font 标签过滤...')
    print()

    try:
        test_strip_font_tags_basic()
        test_strip_font_tags_empty()
        test_strip_font_tags_case_and_attrs()
        test_non_font_tags_unchanged()
        test_preprocess_text_integration()

        print()
        print('=' * 50)
        print('所有 font 标签过滤测试通过!')
        print('=' * 50)

    except AssertionError as e:
        print(f'\n测试失败: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'\n测试错误: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
