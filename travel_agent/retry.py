# -*- coding: utf-8 -*-
"""
LLM/API 重试装饰器模块

支持：
1. 指数退避重试
2. 可配置最大重试次数
3. 特定异常类型才重试
4. 重试间隔可配置
"""

import time
import random
import logging
from functools import wraps
from typing import Callable, Type, Tuple

from travel_agent.errors import (
    LLMAPIError, LLMRateLimitError, LLMTimeoutError,
    ToolTimeoutError, ToolRateLimitError,
    TravelAgentError,
)

logger = logging.getLogger(__name__)

# 默认重试配置
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # 秒
DEFAULT_MAX_DELAY = 30.0  # 秒
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_JITTER = 0.5  # 随机抖动比例


# 可重试的异常类型（LLM 相关）
LLM_RETRYABLE_ERRORS: Tuple[Type[Exception], ...] = (
    LLMAPIError,
    LLMRateLimitError,
    LLMTimeoutError,
    ConnectionError,
    TimeoutError,
    OSError,
)

# 可重试的异常类型（工具相关）
TOOL_RETRYABLE_ERRORS: Tuple[Type[Exception], ...] = (
    ToolTimeoutError,
    ToolRateLimitError,
    ConnectionError,
    TimeoutError,
    OSError,
)


def _is_retryable(
    error: Exception,
    retryable_errors: Tuple[Type[Exception], ...]
) -> bool:
    """判断异常是否可重试"""
    # 直接 isinstance 检查
    if isinstance(error, retryable_errors):
        return True

    # 检查原始异常（对于 TravelAgentError 包装的情况）
    if isinstance(error, TravelAgentError) and error.original_error:
        return isinstance(error.original_error, retryable_errors)

    return False


def _calculate_delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    backoff_factor: float,
    jitter: float,
) -> float:
    """计算指数退避延迟时间"""
    # 基础指数退避
    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
    # 添加随机抖动
    jitter_amount = delay * jitter * (2 * random.random() - 1)
    delay = max(delay + jitter_amount, 0)
    return delay


def with_llm_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    jitter: float = DEFAULT_JITTER,
) -> Callable:
    """
    LLM 调用重试装饰器

    自动捕获 LLM 相关异常并进行指数退避重试。
    重试次数耗尽后抛出原始异常。

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟秒数
        max_delay: 最大延迟秒数
        backoff_factor: 退避因子
        jitter: 抖动比例（0-1）

    Returns:
        装饰器函数

    Usage:
        @with_llm_retry(max_retries=3)
        def call_llm(prompt):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # 判断是否可重试
                    if not _is_retryable(e, LLM_RETRYABLE_ERRORS):
                        # 不可重试，直接抛出
                        raise

                    # 最后一次尝试也失败
                    if attempt == max_retries:
                        logger.error(
                            f"[重试耗尽] {func.__name__} 在 {max_retries + 1} 次尝试后失败: {e}"
                        )
                        raise

                    # 计算延迟并等待
                    delay = _calculate_delay(
                        attempt=attempt,
                        base_delay=base_delay,
                        max_delay=max_delay,
                        backoff_factor=backoff_factor,
                        jitter=jitter,
                    )

                    logger.warning(
                        f"[重试] {func.__name__} 第 {attempt + 1}/{max_retries} 次重试，"
                        f"等待 {delay:.2f}s... 错误: {e}"
                    )
                    time.sleep(delay)

            raise last_exception

        return wrapper

    return decorator


def with_tool_retry(
    max_retries: int = 2,
    base_delay: float = 0.5,
    max_delay: float = 5.0,
    backoff_factor: float = 2.0,
    jitter: float = 0.3,
) -> Callable:
    """
    工具调用重试装饰器

    针对外部 API 工具调用的重试策略，
    相比 LLM 重试更短的等待时间。

    Args:
        max_retries: 最大重试次数（默认2次）
        base_delay: 基础延迟秒数
        max_delay: 最大延迟秒数

    Returns:
        装饰器函数

    Usage:
        @with_tool_retry(max_retries=2)
        def call_amap(city):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not _is_retryable(e, TOOL_RETRYABLE_ERRORS):
                        raise

                    if attempt == max_retries:
                        logger.error(
                            f"[重试耗尽] {func.__name__} 在 {max_retries + 1} 次尝试后失败: {e}"
                        )
                        raise

                    delay = _calculate_delay(
                        attempt=attempt,
                        base_delay=base_delay,
                        max_delay=max_delay,
                        backoff_factor=backoff_factor,
                        jitter=jitter,
                    )

                    logger.warning(
                        f"[重试] {func.__name__} 第 {attempt + 1}/{max_retries} 次重试，"
                        f"等待 {delay:.2f}s... 错误: {e}"
                    )
                    time.sleep(delay)

            raise last_exception

        return wrapper

    return decorator


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_errors: Tuple[Type[Exception], ...] = LLM_RETRYABLE_ERRORS,
) -> Callable:
    """
    通用重试装饰器

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟
        max_delay: 最大延迟
        retryable_errors: 可重试的异常类型

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not _is_retryable(e, retryable_errors):
                        raise

                    if attempt == max_retries:
                        raise

                    delay = _calculate_delay(
                        attempt=attempt,
                        base_delay=base_delay,
                        max_delay=max_delay,
                        backoff_factor=2.0,
                        jitter=0.5,
                    )
                    time.sleep(delay)

            raise last_exception

        return wrapper

    return decorator