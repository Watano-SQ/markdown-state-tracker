"""
抽取器配置
"""
import os
from pathlib import Path
from typing import Optional

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # dotenv 不是必需的


class ExtractorConfig:
    """抽取器配置类"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_retries: int = 3,
        timeout: int = 30
    ):
        """
        Args:
            api_key: OpenAI API Key（默认从环境变量读取）
            model: 模型名称（默认 gpt-4o-mini）
            temperature: 温度参数（默认 0.1）
            max_retries: 最大重试次数
            timeout: 超时时间（秒）
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model or os.getenv('LLM_MODEL', 'gpt-4o-mini')
        self.temperature = temperature or float(os.getenv('LLM_TEMPERATURE', '0.1'))
        self.max_retries = max_retries
        self.timeout = timeout
    
    def validate(self) -> bool:
        """验证配置是否有效"""
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. "
                "Please set it in .env file or environment variable."
            )
        return True


# 默认配置实例
default_config = ExtractorConfig()
