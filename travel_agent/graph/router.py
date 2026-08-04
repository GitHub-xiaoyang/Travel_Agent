# -*- coding: utf-8 -*-
"""
Graph 路由函数模块（重构版）

新流程路由：
  意图解析 → 任务+参数提取 → 工具调用 → 资源汇总 → 模板分析 → 输出渲染
  每步都检查异常，异常时跳转 fallback_node
"""

from travel_agent.state import TravelAgentState
from travel_agent.nodes.constants import (
    NODE_FALLBACK,
    NODE_INTENT,
    NODE_TASK_PARAM,
    NODE_TOOL_CALLS,
    NODE_RESOURCE_AGG,
    NODE_TEMPLATE_ANALYSIS,
)


def _has_exception(state: TravelAgentState) -> bool:
    """集中判断 state 是否包含异常"""
    return state.has_exception


def _safe_route(state: TravelAgentState, normal_target: str) -> str:
    """统一路由异常拦截"""
    if _has_exception(state):
        return NODE_FALLBACK
    return normal_target


def route_after_intent(state: TravelAgentState) -> str:
    """
    意图解析后路由 → 任务+参数提取

    检查意图解析结果，异常时跳转 fallback。
    """
    if _has_exception(state):
        return NODE_FALLBACK
    if not state.intent_info:
        return NODE_FALLBACK
    return NODE_TASK_PARAM


def route_after_task_param(state: TravelAgentState) -> str:
    """
    任务+参数提取后路由 → 工具调用

    如果没有提取到任务，跳转 fallback。
    """
    if _has_exception(state):
        return NODE_FALLBACK
    if not state.extracted_tasks:
        return NODE_FALLBACK
    return NODE_TOOL_CALLS


def route_after_tool_calls(state: TravelAgentState) -> str:
    """
    工具调用后路由 → 资源汇总

    所有工具并行执行完成后，进入资源汇总。
    """
    return _safe_route(state, NODE_RESOURCE_AGG)


def route_after_resource_agg(state: TravelAgentState) -> str:
    """
    资源汇总后路由 → 模板分析

    资源汇总完成后，进入模板分析选择输出模板。
    """
    return _safe_route(state, NODE_TEMPLATE_ANALYSIS)


def route_after_template_analysis(state: TravelAgentState) -> str:
    """
    模板分析后路由 → END

    模板分析完成后直接结束，输出渲染由前端流式处理。
    异常时跳转 fallback。
    """
    if _has_exception(state):
        return NODE_FALLBACK
    from langgraph.graph import END
    return END
