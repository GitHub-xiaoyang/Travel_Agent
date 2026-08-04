# -*- coding: utf-8 -*-
"""
任务+参数提取节点

根据意图解析结果，提取需要执行的任务列表和参数字典。
严格对应流程图中的"任务+参数"阶段。

任务：天气查询、交通规划、景点查询、美食查询、住宿查询、行程攻略
参数：目的地、出行天数、出行人数、其他(景点要求/美食推荐等)
"""

from travel_agent.nodes import with_node_error_handler, NODE_TASK_PARAM
from travel_agent.nodes.constants import (
    INTENT_TASK_MAP,
    TASK_TOOL_MAP,
    TASK_WEATHER_QUERY,
    TASK_TRAFFIC_PLAN,
    TASK_SCENIC_QUERY,
    TASK_FOOD_QUERY,
    TASK_HOTEL_QUERY,
    TASK_PLAN_GENERATION,
    TOOL_WEATHER,
    TOOL_TRAFFIC,
    TOOL_SCENIC,
    TOOL_FOOD,
    TOOL_HOTEL,
)
from travel_agent.state import TravelAgentState


def _extract_tasks(intent_action: str) -> list[str]:
    """
    根据意图动作提取任务列表

    Args:
        intent_action: 意图动作（如 query_weather, full_plan 等）

    Returns:
        任务名称列表
    """
    # 从映射表获取
    tasks = INTENT_TASK_MAP.get(intent_action, [])

    # 如果没有映射，根据意图推断
    if not tasks:
        if intent_action == "query_weather":
            tasks = [TASK_WEATHER_QUERY]
        elif intent_action == "query_traffic":
            tasks = [TASK_TRAFFIC_PLAN]
        elif intent_action == "query_scenic" or intent_action == "book_ticket":
            tasks = [TASK_SCENIC_QUERY]
        elif intent_action == "query_food":
            tasks = [TASK_FOOD_QUERY]
        elif intent_action == "query_hotel":
            tasks = [TASK_HOTEL_QUERY]
        elif intent_action == "full_plan":
            tasks = [TASK_WEATHER_QUERY, TASK_TRAFFIC_PLAN, TASK_SCENIC_QUERY, TASK_FOOD_QUERY, TASK_HOTEL_QUERY]
        elif intent_action == "optimize_plan":
            tasks = [TASK_PLAN_GENERATION]
        elif intent_action in ("query_luggage", "query_fun"):
            tasks = [TASK_PLAN_GENERATION]

    return tasks


def _extract_params(state: TravelAgentState) -> dict:
    """
    从意图信息中提取参数字典

    Args:
        state: 当前状态

    Returns:
        参数字典 {目的地, 出行天数, 出行人数, 其他}
    """
    params = {}
    intent = state.intent_info

    if not intent:
        return params

    # 目的地：优先用户指定，其次当前位置城市
    params["目的地"] = intent.destination or intent.current_location or ""

    # 出行天数
    params["出行天数"] = intent.travel_days or ""

    # 出行人数/人群
    params["出行人数"] = intent.crowd or ""

    # 其他参数：核心需求、时间段
    params["核心需求"] = intent.core_demand or ""
    params["出行时间段"] = intent.travel_time or ""

    # 当前位置信息
    params["当前位置"] = intent.current_location or ""
    params["当前位置详情"] = intent.current_location_detail or ""
    params["当前经度"] = intent.current_location_lng or ""
    params["当前纬度"] = intent.current_location_lat or ""

    return params


@with_node_error_handler(NODE_TASK_PARAM)
def extract_tasks_and_params(state: TravelAgentState) -> dict:
    """
    LangGraph 节点：任务+参数提取

    根据意图解析结果，确定需要执行的任务列表和参数。

    Args:
        state: 包含 intent_info 的状态

    Returns:
        提取后的任务列表和参数字典
    """
    if not state.intent_info:
        return {
            "extracted_tasks": [],
            "extracted_params": {},
        }

    # 获取意图动作
    intent_action = ""
    if state.intent_info.required_tools:
        # 根据 required_tools 反推主要意图
        tools = state.intent_info.required_tools
        if TOOL_WEATHER in tools and len(tools) == 1:
            intent_action = "query_weather"
        elif TOOL_TRAFFIC in tools and len(tools) == 1:
            intent_action = "query_traffic"
        elif TOOL_SCENIC in tools and len(tools) == 1:
            intent_action = "query_scenic"
        elif TOOL_FOOD in tools and len(tools) == 1:
            intent_action = "query_food"
        else:
            intent_action = "full_plan"
    else:
        # required_tools 为空时，根据目的地和天数推断意图
        destination = state.intent_info.destination or ""
        days = state.intent_info.travel_days or ""
        if destination and days:
            intent_action = "full_plan"
            print(f"[任务+参数提取] required_tools 为空，但有目的地({destination})+天数({days})，推断为 full_plan")

    # 提取任务
    tasks = _extract_tasks(intent_action)

    # 提取参数
    params = _extract_params(state)

    # 如果没有目的地，尝试用当前位置兜底
    if not params.get("目的地") and params.get("当前位置"):
        params["目的地"] = params["当前位置"]

    # 打印调试信息
    print(f"\n[任务+参数提取] 意图: {intent_action}")
    print(f"  任务: {tasks}")
    print(f"  目的地: {params.get('目的地', '未指定')}")
    print(f"  出行天数: {params.get('出行天数', '未指定')}")
    print(f"  出行人群: {params.get('出行人数', '未指定')}")

    return {
        "extracted_tasks": tasks,
        "extracted_params": params,
    }
