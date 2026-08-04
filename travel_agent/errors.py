# -*- coding: utf-8 -*-
"""
自定义业务异常模块

错误分级：
- CRITICAL (50): 系统级致命错误，需要人工介入
- HIGH (40): 严重业务错误，影响核心功能
- MEDIUM (30): 一般业务错误，用户可重试
- LOW (20): 轻微错误，不影响主流程
"""

from enum import IntEnum
from typing import Optional


class ErrorLevel(IntEnum):
    """错误严重级别"""
    CRITICAL = 50  # 系统级致命
    HIGH = 40  # 严重业务
    MEDIUM = 30  # 一般业务
    LOW = 20  # 轻微错误


class TravelAgentError(Exception):
    """旅行 Agent 业务异常基类"""

    def __init__(
        self,
        message: str,
        level: ErrorLevel = ErrorLevel.MEDIUM,
        code: str = "UNKNOWN",
        node_name: str = "",
        original_error: Optional[Exception] = None,
    ):
        self.message = message
        self.level = level
        self.code = code
        self.node_name = node_name
        self.original_error = original_error
        super().__init__(message)

    def __str__(self) -> str:
        level_str = self.level.name
        return f"[{level_str}][{self.code}][{self.node_name}] {self.message}"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "message": self.message,
            "level": self.level.name,
            "code": self.code,
            "node_name": self.node_name,
            "original_error": str(self.original_error) if self.original_error else None,
        }


# ========== LLM 相关异常 ==========
class LLMError(TravelAgentError):
    """LLM 调用异常基类"""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("level", ErrorLevel.HIGH)
        kwargs.setdefault("code", "LLM_ERROR")
        super().__init__(message, **kwargs)


class LLMAPIError(LLMError):
    """LLM API 连接/鉴权错误"""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("level", ErrorLevel.CRITICAL)
        kwargs.setdefault("code", "LLM_API_ERROR")
        super().__init__(message, **kwargs)


class LLMRateLimitError(LLMError):
    """LLM 限流错误"""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("level", ErrorLevel.MEDIUM)
        kwargs.setdefault("code", "LLM_RATE_LIMIT")
        super().__init__(message, **kwargs)


class LLMTimeoutError(LLMError):
    """LLM 超时错误"""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("level", ErrorLevel.MEDIUM)
        kwargs.setdefault("code", "LLM_TIMEOUT")
        super().__init__(message, **kwargs)


class LLMParseError(LLMError):
    """LLM 返回内容解析错误"""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("level", ErrorLevel.MEDIUM)
        kwargs.setdefault("code", "LLM_PARSE_ERROR")
        super().__init__(message, **kwargs)


# ========== 工具调用异常 ==========
class ToolError(TravelAgentError):
    """工具调用异常基类"""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("level", ErrorLevel.HIGH)
        kwargs.setdefault("code", "TOOL_ERROR")
        super().__init__(message, **kwargs)


class ToolTimeoutError(ToolError):
    """工具调用超时"""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("level", ErrorLevel.MEDIUM)
        kwargs.setdefault("code", "TOOL_TIMEOUT")
        super().__init__(message, **kwargs)


class ToolRateLimitError(ToolError):
    """工具调用限流"""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("level", ErrorLevel.LOW)
        kwargs.setdefault("code", "TOOL_RATE_LIMIT")
        super().__init__(message, **kwargs)


# ========== 业务逻辑异常 ==========
class BusinessError(TravelAgentError):
    """业务逻辑异常基类"""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("level", ErrorLevel.MEDIUM)
        kwargs.setdefault("code", "BUSINESS_ERROR")
        super().__init__(message, **kwargs)


class InputValidationError(BusinessError):
    """输入验证错误"""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("level", ErrorLevel.MEDIUM)
        kwargs.setdefault("code", "INPUT_INVALID")
        super().__init__(message, **kwargs)


class ResourceNotFoundError(BusinessError):
    """资源未找到"""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("level", ErrorLevel.HIGH)
        kwargs.setdefault("code", "RESOURCE_NOT_FOUND")
        super().__init__(message, **kwargs)


class CacheError(TravelAgentError):
    """缓存相关异常"""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("level", ErrorLevel.LOW)
        kwargs.setdefault("code", "CACHE_ERROR")
        super().__init__(message, **kwargs)


# ========== 异常映射工具 ==========
def classify_exception(exc: Exception) -> TravelAgentError:
    """将普通异常转换为分级业务异常"""
    if isinstance(exc, TravelAgentError):
        return exc

    err_msg = str(exc).lower()

    # LLM 相关
    if any(k in err_msg for k in ["401", "api key", "unauthorized"]):
        return LLMAPIError(str(exc), original_error=exc)
    if any(k in err_msg for k in ["429", "rate limit", "too many"]):
        return LLMRateLimitError(str(exc), original_error=exc)
    if any(k in err_msg for k in ["timeout", "timed out", "connect"]):
        if "tool" in err_msg:
            return ToolTimeoutError(str(exc), original_error=exc)
        return LLMTimeoutError(str(exc), original_error=exc)
    if "json" in err_msg and ("parse" in err_msg or "validate" in err_msg):
        return LLMParseError(str(exc), original_error=exc)

    # 业务相关
    if any(k in err_msg for k in ["missing", "未识别", "为空", "invalid"]):
        return InputValidationError(str(exc), original_error=exc)
    if any(k in err_msg for k in ["not found", "未找到", "resource"]):
        return ResourceNotFoundError(str(exc), original_error=exc)

    # 默认
    return TravelAgentError(str(exc), original_error=exc)