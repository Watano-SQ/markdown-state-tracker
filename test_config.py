"""测试配置加载 - 详细诊断"""
import os
import sys
from pathlib import Path

print("=" * 60)
print("配置诊断工具")
print("=" * 60)

# 检查 .env 文件
env_path = Path(__file__).parent / '.env'
print(f"\n[1] .env 文件检查:")
print(f"    路径: {env_path}")
print(f"    存在: {env_path.exists()}")

if env_path.exists():
    print(f"\n    .env 文件内容 (LLM相关行):")
    with open(env_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            if 'LLM_' in line or 'OPENAI_' in line:
                if not line.strip().startswith('#'):
                    print(f"    {i:3d}: {line.rstrip()}")

# 检查系统环境变量（加载 .env 之前）
print(f"\n[2] 系统环境变量（加载 .env 前）:")
print(f"    LLM_MODEL: {os.environ.get('LLM_MODEL', '(未设置)')}")
print(f"    OPENAI_BASE_URL: {os.environ.get('OPENAI_BASE_URL', '(未设置)')}")
print(f"    OPENAI_API_KEY: {'(已设置)' if os.environ.get('OPENAI_API_KEY') else '(未设置)'}")

# 加载 .env
from dotenv import load_dotenv
load_dotenv(env_path, override=False)  # 不覆盖已有环境变量

print(f"\n[3] 加载 .env 后 (override=False):")
print(f"    LLM_MODEL: {os.getenv('LLM_MODEL')}")
print(f"    OPENAI_BASE_URL: {os.getenv('OPENAI_BASE_URL')}")

# 重新加载，强制覆盖
load_dotenv(env_path, override=True)

print(f"\n[4] 加载 .env 后 (override=True):")
print(f"    LLM_MODEL: {os.getenv('LLM_MODEL')}")
print(f"    OPENAI_BASE_URL: {os.getenv('OPENAI_BASE_URL')}")
print(f"    LLM_TEMPERATURE: {os.getenv('LLM_TEMPERATURE')}")
print(f"    LLM_REASONING_SPLIT: {os.getenv('LLM_REASONING_SPLIT')}")

# 测试 ExtractorConfig
try:
    from layers.extractors.config import ExtractorConfig
    
    config = ExtractorConfig()
    print(f"\n[5] ExtractorConfig 对象:")
    print(f"    model: {config.model}")
    print(f"    base_url: {config.base_url}")
    print(f"    temperature: {config.temperature}")
    print(f"    provider: {config.get_provider()}")
    print(f"    extra_body: {config.extra_body}")
    
    print("\n[6] 配置验证:")
    try:
        config.validate()
        print("    ✅ 配置有效")
    except Exception as e:
        print(f"    ❌ 配置错误: {e}")
        
except Exception as e:
    print(f"\n❌ 加载 ExtractorConfig 失败:")
    print(f"    {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
