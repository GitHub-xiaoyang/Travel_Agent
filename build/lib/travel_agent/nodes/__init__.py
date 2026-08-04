# -*- coding: utf-8 -*-
"""
节点模块公共导出（重构版）

新流程节点：
  意图解析 → 任务+参数提取 → 工具调用 → 资源汇总 → 模板分析 → 输出渲染
"""

from travel_agent.nodes.constants import (
    NODE_INTENT,
    NODE_TASK_PARAM,
    NODE_TOOL_CALLS,
    NODE_RESOURCE_AGG,
    NODE_TEMPLATE_ANALYSIS,
    NODE_OUTPUT,
    NODE_FALLBACK,
    NODE_DISPLAY_NAMES,
    INTENT_TASK_MAP,
    TASK_TOOL_MAP,
    TASK_WEATHER_QUERY,
    TASK_TRAFFIC_PLAN,
    TASK_SCENIC_QUERY,
    TASK_FOOD_QUERY,
    TASK_HOTEL_QUERY,
    TASK_PLAN_GENERATION,
    TOOL_WEATHER,
    TOOL_SCENIC,
    TOOL_FOOD,
    TOOL_HOTEL,
    TOOL_TRAFFIC,
    TEMPLATE_WEATHER,
    TEMPLATE_TRAFFIC,
    TEMPLATE_SCENIC,
    TEMPLATE_FOOD,
    TEMPLATE_HOTEL,
    TEMPLATE_PLAN,
    TEMPLATE_COMBINED,
    TEMPLATE_LUGGAGE,
    TEMPLATE_FUN,
    INTENT_TEMPLATE_MAP,
    INTENT_DISPLAY_MAP,
    TASK_DISPLAY_MAP,
)
from travel_agent.nodes.decorators import (
    with_node_error_handler,
    with_tool_error_handler,
)

__all__ = [
    # 节点名
    "NODE_INTENT",
    "NODE_TASK_PARAM",
    "NODE_TOOL_CALLS",
    "NODE_RESOURCE_AGG",
    "NODE_TEMPLATE_ANALYSIS",
    "NODE_OUTPUT",
    "NODE_FALLBACK",
    "NODE_DISPLAY_NAMES",
    # 任务名
    "TASK_WEATHER_QUERY",
    "TASK_TRAFFIC_PLAN",
    "TASK_SCENIC_QUERY",
    "TASK_FOOD_QUERY",
    "TASK_HOTEL_QUERY",
    "TASK_PLAN_GENERATION",
    "INTENT_TASK_MAP",
    "TASK_TOOL_MAP",
    # 工具名
    "TOOL_WEATHER",
    "TOOL_SCENIC",
    "TOOL_FOOD",
    "TOOL_HOTEL",
    "TOOL_TRAFFIC",
    # 模板类型
    "TEMPLATE_WEATHER",
    "TEMPLATE_TRAFFIC",
    "TEMPLATE_SCENIC",
    "TEMPLATE_FOOD",
    "TEMPLATE_HOTEL",
    "TEMPLATE_PLAN",
    "TEMPLATE_COMBINED",
    "TEMPLATE_LUGGAGE",
    "TEMPLATE_FUN",
    "INTENT_TEMPLATE_MAP",
    "INTENT_DISPLAY_MAP",
    "TASK_DISPLAY_MAP",
    # 装饰器
    "with_node_error_handler",
    "with_tool_error_handler",
]
