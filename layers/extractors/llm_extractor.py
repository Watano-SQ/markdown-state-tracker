"""
基于 LLM 的抽取器
"""
import json
import time
from typing import Optional, Dict, Any
import logging

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app_logging import get_logger, log_event, summarize_text
from layers.middle_layer import ExtractionResult
from .config import ExtractorConfig
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .rule_helper import preprocess_text, postprocess_result


logger = get_logger("extractor")

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
            
            # 根据是否有 base_url 初始化客户端
            if self.config.base_url:
                self.client = OpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.base_url
                )
            else:
                self.client = OpenAI(api_key=self.config.api_key)
                
        except ImportError:
            raise ImportError(
                "openai package not installed. "
                "Please install it with: pip install openai"
            )
        
        self.model = self.config.model
        self.temperature = self.config.temperature
        self.extra_body = self.config.extra_body
        self.provider = self.config.get_provider()
        
        log_event(
            logger,
            logging.INFO,
            "extractor_initialized",
            "Initialized LLM extractor",
            stage="extraction",
            provider=self.provider,
            model=self.model,
            temperature=self.temperature,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )
    
    def extract(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        log_context: Optional[Dict[str, Any]] = None,
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
        log_context = log_context or {}
        extract_start = time.perf_counter()
        
        # 1. 规则预处理
        preprocessed = preprocess_text(text, context)
        
        # 2. 构建 prompt
        user_prompt = build_user_prompt(
            text=preprocessed['text'],
            context=context,
            hints=preprocessed.get('hints', {})
        )
        
        # 3. 调用 LLM（带重试）
        result_json = self._call_llm_with_retry(user_prompt, log_context=log_context)
        
        # 4. 后处理
        result_json = postprocess_result(result_json, preprocessed)
        
        # 5. 转换为 ExtractionResult
        result = ExtractionResult.from_dict(result_json)
        log_event(
            logger,
            logging.INFO,
            "extract_result_ready",
            "Prepared structured extraction result",
            stage="extraction",
            duration_ms=(time.perf_counter() - extract_start) * 1000,
            entity_count=len(result.entities),
            state_candidate_count=len(result.state_candidates),
            relation_candidate_count=len(result.relation_candidates),
            retrieval_candidate_count=len(result.retrieval_candidates),
            **log_context,
        )
        return result
    
    def _call_llm_with_retry(
        self,
        user_prompt: str,
        log_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        调用 LLM，带重试机制
        
        Args:
            user_prompt: 用户 prompt
        
        Returns:
            解析后的 JSON 结果
        """
        log_context = log_context or {}
        last_error = None
        last_response_preview = None
        
        for attempt in range(self.config.max_retries):
            attempt_number = attempt + 1
            attempt_start = time.perf_counter()
            log_event(
                logger,
                logging.INFO,
                "llm_request_start",
                "Starting LLM request",
                stage="extraction",
                attempt=attempt_number,
                max_retries=self.config.max_retries,
                model=self.model,
                provider=self.provider,
                temperature=self.temperature,
                timeout=self.config.timeout,
                prompt_chars=len(user_prompt),
                **log_context,
            )
            try:
                # 构建请求参数
                request_params = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": self.temperature,
                    "response_format": {"type": "json_object"},
                    "timeout": self.config.timeout
                }
                
                # 添加额外参数（如 MiniMax 的 reasoning_split）
                if self.extra_body:
                    request_params["extra_body"] = self.extra_body
                
                response = self.client.chat.completions.create(**request_params)
                
                # 解析 JSON
                content = response.choices[0].message.content or ""
                result = json.loads(content)
                log_event(
                    logger,
                    logging.INFO,
                    "llm_request_done",
                    "LLM request completed successfully",
                    stage="extraction",
                    attempt=attempt_number,
                    model=self.model,
                    provider=self.provider,
                    response_chars=len(content),
                    duration_ms=(time.perf_counter() - attempt_start) * 1000,
                    **log_context,
                )
                return result
                
            except json.JSONDecodeError as e:
                last_error = e
                last_response_preview = summarize_text(locals().get("content", ""), 200)
                log_event(
                    logger,
                    logging.WARNING,
                    "llm_request_retry",
                    "Retrying after JSON parse failure",
                    stage="extraction",
                    attempt=attempt_number,
                    max_retries=self.config.max_retries,
                    model=self.model,
                    provider=self.provider,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    response_preview=last_response_preview,
                    duration_ms=(time.perf_counter() - attempt_start) * 1000,
                    sleep_seconds=attempt_number,
                    **log_context,
                )
                
            except Exception as e:
                last_error = e
                log_event(
                    logger,
                    logging.WARNING,
                    "llm_request_retry",
                    "Retrying after LLM request failure",
                    stage="extraction",
                    attempt=attempt_number,
                    max_retries=self.config.max_retries,
                    model=self.model,
                    provider=self.provider,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    duration_ms=(time.perf_counter() - attempt_start) * 1000,
                    sleep_seconds=attempt_number,
                    **log_context,
                )
            
            # 重试前等待
            if attempt < self.config.max_retries - 1:
                time.sleep(1 * (attempt + 1))  # 递增等待时间
        
        # 所有重试都失败
        log_event(
            logger,
            logging.ERROR,
            "llm_request_failed",
            "LLM request failed after all retries",
            stage="extraction",
            max_retries=self.config.max_retries,
            model=self.model,
            provider=self.provider,
            error_type=type(last_error).__name__ if last_error else "UnknownError",
            error_message=str(last_error) if last_error else None,
            response_preview=last_response_preview,
            **log_context,
        )
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
