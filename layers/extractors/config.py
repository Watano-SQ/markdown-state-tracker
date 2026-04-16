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
        # override=True: .env 文件优先于系统环境变量
        load_dotenv(env_path, override=True)
except ImportError:
    pass  # dotenv 不是必需的


class ExtractorConfig:
    """抽取器配置类 - 支持多个 LLM 提供商"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_retries: int = 3,
        timeout: int = 30,
        extra_body: Optional[dict] = None
    ):
        """
        Args:
            api_key: API Key（默认从环境变量 OPENAI_API_KEY 读取）
            base_url: API Base URL（默认从环境变量 OPENAI_BASE_URL 读取）
                     - OpenAI: https://api.openai.com/v1 (默认)
                     - MiniMax: https://api.minimaxi.com/v1
                     - DeepSeek: https://api.deepseek.com/v1
                     - 其他兼容 OpenAI 的服务
            model: 模型名称（默认从环境变量 LLM_MODEL 读取，fallback: gpt-4o-mini）
                  - OpenAI: gpt-4o-mini, gpt-4o, gpt-4-turbo
                  - MiniMax: MiniMax-M2.7, MiniMax-M2.7-highspeed, MiniMax-M2.5
                  - DeepSeek: deepseek-chat, deepseek-coder
            temperature: 温度参数（默认从环境变量 LLM_TEMPERATURE 读取）
                        - OpenAI: 0-2（推荐 0.1-0.7）
                        - MiniMax: (0.0, 1.0]（推荐 1.0）
            max_retries: 最大重试次数
            timeout: 超时时间（秒）
            extra_body: 额外的请求参数（如 MiniMax 的 reasoning_split）
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.base_url = base_url or os.getenv('OPENAI_BASE_URL')
        self.model = model or os.getenv('LLM_MODEL', 'gpt-4o-mini')
        
        # 自动检测提供商并设置默认温度
        default_temp = self._get_default_temperature()
        self.temperature = temperature or float(os.getenv('LLM_TEMPERATURE', str(default_temp)))
        
        self.max_retries = max_retries
        self.timeout = timeout
        
        # 额外参数（从环境变量或参数）
        if extra_body is None:
            extra_body = self._get_default_extra_body()
        self.extra_body = extra_body
    
    def _get_default_temperature(self) -> float:
        """根据模型自动选择默认温度"""
        if 'MiniMax' in self.model or 'minimax' in self.model.lower():
            return 1.0  # MiniMax 推荐
        elif 'deepseek' in self.model.lower():
            return 0.7  # DeepSeek 推荐
        else:
            return 0.1  # OpenAI 推荐（稳定输出）
    
    def _get_default_extra_body(self) -> dict:
        """根据提供商设置默认额外参数"""
        extra = {}
        
        # MiniMax 特定参数
        if 'MiniMax' in self.model or 'minimax' in self.model.lower():
            # 启用思考内容分离（便于调试和分析）
            reasoning_split = os.getenv('LLM_REASONING_SPLIT', 'true').lower() == 'true'
            if reasoning_split:
                extra['reasoning_split'] = True
        
        return extra
    
    def get_provider(self) -> str:
        """检测 LLM 提供商"""
        if self.base_url:
            if 'minimaxi.com' in self.base_url:
                return 'minimax'
            elif 'deepseek.com' in self.base_url:
                return 'deepseek'
            elif 'openai.com' in self.base_url:
                return 'openai'
            else:
                return 'custom'
        
        # 通过模型名推断
        model_lower = self.model.lower()
        if 'minimax' in model_lower:
            return 'minimax'
        elif 'deepseek' in model_lower:
            return 'deepseek'
        elif 'gpt' in model_lower:
            return 'openai'
        else:
            return 'unknown'
    
    def validate(self) -> bool:
        """验证配置是否有效"""
        if not self.api_key:
            raise ValueError(
                "API Key not found. "
                "Please set OPENAI_API_KEY in .env file or environment variable."
            )
        
        # 提供商特定验证
        provider = self.get_provider()
        
        # MiniMax 温度验证
        if provider == 'minimax':
            if self.temperature <= 0.0 or self.temperature > 1.0:
                raise ValueError(
                    f"MiniMax temperature must be in (0.0, 1.0], got {self.temperature}. "
                    f"Recommended: 1.0"
                )
        
        # OpenAI 温度验证
        elif provider == 'openai':
            if self.temperature < 0.0 or self.temperature > 2.0:
                raise ValueError(
                    f"OpenAI temperature must be in [0.0, 2.0], got {self.temperature}"
                )
        
        return True


# 默认配置实例
default_config = ExtractorConfig()
