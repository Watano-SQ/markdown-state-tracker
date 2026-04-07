"""
基于 LLM 的抽取器
"""
import json
import time
from typing import Optional, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from layers.middle_layer import ExtractionResult
from .config import ExtractorConfig, default_config
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .rule_helper import preprocess_text, postprocess_result


class LLMExtractor:
    """基于 LLM 的抽取器"""
    
    def __init__(
        self,
        config: Optional[ExtractorConfig] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ):
        """
        初始化 LLM 抽取器
        
        Args:
            config: 抽取器配置（优先使用）
            api_key: OpenAI API Key（覆盖配置）
            model: 模型名称（覆盖配置）
            temperature: 温度参数（覆盖配置）
        """
        # 使用提供的配置或默认配置
        self.config = config or ExtractorConfig(
            api_key=api_key,
            model=model,
            temperature=temperature
        )
        
        # 验证配置
        self.config.validate()
        
        # 延迟导入 OpenAI（避免未安装时报错）
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.config.api_key)
        except ImportError:
            raise ImportError(
                "openai package not installed. "
                "Please install it with: pip install openai"
            )
        
        self.model = self.config.model
        self.temperature = self.config.temperature
    
    def extract(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExtractionResult:
        """
        从文本中提取结构化信息
        
        Args:
            text: chunk 文本
            context: 文档上下文（标题、时间等）
        
        Returns:
            ExtractionResult 对象
        """
        context = context or {}
        
        # 1. 规则预处理
        preprocessed = preprocess_text(text, context)
        
        # 2. 构建 prompt
        user_prompt = build_user_prompt(
            text=preprocessed['text'],
            context=context,
            hints=preprocessed.get('hints', {})
        )
        
        # 3. 调用 LLM（带重试）
        result_json = self._call_llm_with_retry(user_prompt)
        
        # 4. 后处理
        result_json = postprocess_result(result_json, preprocessed)
        
        # 5. 转换为 ExtractionResult
        return ExtractionResult.from_dict(result_json)
    
    def _call_llm_with_retry(self, user_prompt: str) -> Dict[str, Any]:
        """
        调用 LLM，带重试机制
        
        Args:
            user_prompt: 用户 prompt
        
        Returns:
            解析后的 JSON 结果
        """
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                    timeout=self.config.timeout
                )
                
                # 解析 JSON
                content = response.choices[0].message.content
                result = json.loads(content)
                return result
                
            except json.JSONDecodeError as e:
                last_error = e
                print(f"JSON 解析失败 (尝试 {attempt + 1}/{self.config.max_retries}): {e}")
                
            except Exception as e:
                last_error = e
                print(f"LLM 调用失败 (尝试 {attempt + 1}/{self.config.max_retries}): {e}")
            
            # 重试前等待
            if attempt < self.config.max_retries - 1:
                time.sleep(1 * (attempt + 1))  # 递增等待时间
        
        # 所有重试都失败
        raise RuntimeError(f"LLM extraction failed after {self.config.max_retries} attempts: {last_error}")
    
    def extract_batch(
        self,
        chunks: list,
        context: Optional[Dict[str, Any]] = None
    ) -> list:
        """
        批量提取（顺序处理）
        
        Args:
            chunks: chunk 列表，每个包含 'text' 字段
            context: 共享的文档上下文
        
        Returns:
            ExtractionResult 列表
        """
        results = []
        for i, chunk in enumerate(chunks):
            text = chunk.get('text', chunk) if isinstance(chunk, dict) else chunk
            
            # 添加位置信息
            chunk_context = {**(context or {})}
            if len(chunks) > 1:
                if i == 0:
                    chunk_context['chunk_position'] = 'start'
                elif i == len(chunks) - 1:
                    chunk_context['chunk_position'] = 'end'
                else:
                    chunk_context['chunk_position'] = 'middle'
            
            result = self.extract(text, chunk_context)
            results.append(result)
        
        return results


# 便捷函数
_default_extractor: Optional[LLMExtractor] = None


def extract_from_chunk(
    text: str,
    context: Optional[Dict[str, Any]] = None,
    extractor: Optional[LLMExtractor] = None
) -> ExtractionResult:
    """
    从 chunk 提取信息（便捷接口）
    
    Args:
        text: chunk 文本
        context: 上下文信息
        extractor: 复用的 extractor 实例（可选）
    
    Returns:
        ExtractionResult
    """
    global _default_extractor
    
    if extractor is not None:
        return extractor.extract(text, context)
    
    # 使用或创建默认 extractor
    if _default_extractor is None:
        _default_extractor = LLMExtractor()
    
    return _default_extractor.extract(text, context)
