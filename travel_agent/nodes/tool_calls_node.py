# -*- coding: utf-8 -*-
"""
工具调用节点

根据任务+参数提取结果，并行调用所有需要的工具。
严格对应流程图中的"工具调用"阶段。

每个任务对应一个或多个工具，工具参数从 extracted_params 中获取。
所有工具并行执行（通过 ThreadPoolExecutor），结果汇总到 tool_results。

集成 TTL 内存缓存：天气 24h、景点/美食/酒店 7d 内同参数命中缓存跳过 API 调用。
交通查询不缓存（实时路线数据）。
"""

import concurrent.futures
from typing import Any

from tools import query_weather, query_traffic_route, search_scenic, search_food, search_poi
from travel_agent.errors import classify_exception
from travel_agent.nodes import with_node_error_handler, NODE_TOOL_CALLS
from travel_agent.nodes.constants import (
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
    TASK_TOOL_MAP,
)
from travel_agent.state import TravelAgentState


def _call_weather_tool(params: dict) -> tuple[str, str]:
    """
    调用天气查询工具

    Args:
        params: 参数字典

    Returns:
        (tool_name, result)
    """
    city = params.get("目的地", "") or params.get("当前位置", "")
    if not city:
        return (TOOL_WEATHER, "天气查询：未指定目的地城市，无法查询")

    try:
        result = query_weather.invoke({"city": city})
        return (TOOL_WEATHER, result)
    except Exception as e:
        err = classify_exception(e)
        return (TOOL_WEATHER, f"天气查询失败[{err.code}]：{err.message}")


def _call_traffic_tool(params: dict) -> tuple[str, str]:
    """
    调用交通查询工具（不缓存，实时路线数据）

    Args:
        params: 参数字典

    Returns:
        (tool_name, result)
    """
    destination = params.get("目的地", "")
    if not destination:
        return (TOOL_TRAFFIC, "交通查询：未指定目的地，无法规划路线")

    city = destination
    start_address = params.get("当前位置", "")
    start_lng = params.get("当前经度", "")
    start_lat = params.get("当前纬度", "")

    invoke_params = {
        "end_address": destination,
        "city": city,
    }

    # 有定位时注入经纬度，启用距离分级规划
    if start_lng and start_lat:
        invoke_params["start_lng"] = start_lng
        invoke_params["start_lat"] = start_lat
        if start_address:
            invoke_params["start_address"] = start_address
    elif start_address:
        invoke_params["start_address"] = start_address

    try:
        result = query_traffic_route.invoke(invoke_params)
        return (TOOL_TRAFFIC, result)
    except Exception as e:
        err = classify_exception(e)
        return (TOOL_TRAFFIC, f"交通查询失败[{err.code}]：{err.message}")


def _call_scenic_tool(params: dict) -> tuple[str, str]:
    """
    调用景点查询工具

    Args:
        params: 参数字典

    Returns:
        (tool_name, result)
    """
    city = params.get("目的地", "") or params.get("当前位置", "")
    if not city:
        return (TOOL_SCENIC, "景点查询：未指定目的地城市，无法查询")

    try:
        result = search_scenic.invoke({"city": city})
        return (TOOL_SCENIC, result)
    except Exception as e:
        err = classify_exception(e)
        return (TOOL_SCENIC, f"景点查询失败[{err.code}]：{err.message}")


def _call_food_tool(params: dict) -> tuple[str, str]:
    """
    调用美食查询工具

    Args:
        params: 参数字典

    Returns:
        (tool_name, result)
    """
    city = params.get("目的地", "") or params.get("当前位置", "")
    if not city:
        return (TOOL_FOOD, "美食查询：未指定目的地城市，无法查询")

    try:
        result = search_food.invoke({"city": city})
        return (TOOL_FOOD, result)
    except Exception as e:
        err = classify_exception(e)
        return (TOOL_FOOD, f"美食查询失败[{err.code}]：{err.message}")


def _call_hotel_tool(params: dict) -> tuple[str, str]:
    """
    调用酒店查询工具（使用 search_poi）

    Args:
        params: 参数字典

    Returns:
        (tool_name, result)
    """
    city = params.get("目的地", "") or params.get("当前位置", "")
    if not city:
        return (TOOL_HOTEL, "酒店查询：未指定目的地城市，无法查询")

    try:
        result = search_poi.invoke({
            "city": city,
            "poi_type": "酒店",
        })
        return (TOOL_HOTEL, result)
    except Exception as e:
        err = classify_exception(e)
        return (TOOL_HOTEL, f"酒店查询失败[{err.code}]：{err.message}")


# ========== 任务 → 工具调用函数映射 ==========
TASK_CALL_MAP = {
    TASK_WEATHER_QUERY: _call_weather_tool,
    TASK_TRAFFIC_PLAN: _call_traffic_tool,
    TASK_SCENIC_QUERY: _call_scenic_tool,
    TASK_FOOD_QUERY: _call_food_tool,
    TASK_HOTEL_QUERY: _call_hotel_tool,
}


def _execute_tool_calls(tasks: list[str], params: dict) -> dict[str, str]:
    """
    并行执行所有工具调用

    Args:
        tasks: 任务列表
        params: 参数字典

    Returns:
        工具结果字典 {tool_name: result}
    """
    results = {}

    # 收集需要执行的工具
    callables = {}
    for task in tasks:
        if task in TASK_CALL_MAP:
            # 获取该任务对应的工具名列表
            tool_names = TASK_TOOL_MAP.get(task, [task])
            for tool_name in tool_names:
                if tool_name not in callables:
                    callables[tool_name] = TASK_CALL_MAP[task]

    if not callables:
        return results

    # 并行执行所有工具
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(callables)) as executor:
        future_to_tool = {
            executor.submit(func, params): tool_name
            for tool_name, func in callables.items()
        }

        for future in concurrent.futures.as_completed(future_to_tool):
            try:
                tool_name, result = future.result()
                results[tool_name] = result
                print(f"  [工具完成] {tool_name}: {len(result)} 字符")
            except Exception as e:
                tool_name = future_to_tool[future]
                results[tool_name] = f"工具执行异常: {str(e)}"
                print(f"  [工具异常] {tool_name}: {str(e)}")

    return results


@with_node_error_handler(NODE_TOOL_CALLS)
def execute_tool_calls(state: TravelAgentState) -> dict:
    """
    LangGraph 节点：工具调用（并行执行）

    根据 extracted_tasks 列表，并行调用所有需要的工具。
    所有工具结果汇总到 tool_results 字典中。

    Args:
        state: 包含 extracted_tasks 和 extracted_params 的状态

    Returns:
        工具结果字典
    """
    tasks = state.extracted_tasks
    params = state.extracted_params

    if not tasks:
        print("[工具调用] 无任务需要执行")
        return {"tool_results": {}}

    print(f"\n[工具调用] 开始执行 {len(tasks)} 个任务")
    for task in tasks:
        print(f"  - {task}")

    # 并行执行所有工具
    tool_results = _execute_tool_calls(tasks, params)

    print(f"[工具调用] 完成，共 {len(tool_results)} 个工具返回结果")

    # 更新 history_resource_cache（供 resource_aggregation_node 合并）
    cache_update = {}
    destination = params.get("目的地", "")
    if destination:
        cache = state.get_cached_resource(destination) or {}
        for tool_name, result in tool_results.items():
            cache[f"{tool_name}_result"] = result
        state.set_cached_resource(destination, cache)
        cache_update = {destination: cache}

    return {
        "tool_results": tool_results,
        "history_resource_cache": cache_update,
    }
