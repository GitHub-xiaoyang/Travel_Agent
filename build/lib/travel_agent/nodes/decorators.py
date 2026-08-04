# -*- coding: utf-8 -*-
"""
全局异常装饰器

为所有 LangGraph 节点函数提供统一的异常处理，
消除每个节点中重复的 try-except 样板代码。

用法：
    @with_node_error_handler(NODE_INTENT)
    def parse_intent(state: TravelAgentState) -> TravelAgentState:
        # 业务逻辑，异常会被自动捕获并写入 state
        ...
"""

import traceback
from functools import wraps
from typing import Callable

from travel_agent.state import TravelAgentState


def with_node_error_handler(node_name: str) -> Callable:
    """
    节点异常统一处理装饰器

    自动捕获节点函数中的所有异常，将错误信息写入 State，
    使 LangGraph 路由逻辑能检测到 has_exception 并跳转到 fallback_node。

    Args:
        node_name: 节点名称常量（如 NODE_INTENT）

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(state: TravelAgentState, *args, **kwargs) -> dict:
            try:
                return func(state, *args, **kwargs)
            except Exception as e:
                # 异常时只返回错误相关字段（dict），避免并发更新冲突
                return {
                    "has_exception": True,
                    "error_msg": str(e),
                    "error_trace": traceback.format_exc(),
                    "error_step": node_name,
                    "user_query_origin": state.user_input,
                }

        return wrapper

    return decorator


def with_tool_error_handler(tool_name: str, default_return: str = "") -> Callable:
    """
    工具调用异常统一处理装饰器

    用于工具类的 run/execute 方法，
    捕获异常并返回友好的错误信息字符串。

    Args:
        tool_name: 工具名称
        default_return: 异常时的默认返回值

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                return f"{tool_name}调用失败：{str(e)}"

        return wrapper

    return decorator