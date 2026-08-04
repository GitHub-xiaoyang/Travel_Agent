# -*- coding: utf-8 -*-
"""
模板分析节点（重构版）

根据意图解析结果和任务组合，选择最合适的输出模板。
严格对应流程图中的"模板分析"阶段。

核心逻辑：
1. 单任务 → 使用对应类型模板（如天气查询 → weather_template）
2. 多任务 → 使用组合模板或行程模板
3. 全流程规划 → 使用行程模板（plan_template）
4. 根据模板类型构建 template_context，供 output_node 使用
"""

from travel_agent.nodes import with_node_error_handler, NODE_TEMPLATE_ANALYSIS
from travel_agent.nodes.constants import (
    INTENT_TEMPLATE_MAP,
    MULTI_TASK_TEMPLATES,
    INTENT_DISPLAY_MAP,
    TASK_DISPLAY_MAP,
    TASK_WEATHER_QUERY,
    TASK_TRAFFIC_PLAN,
    TASK_SCENIC_QUERY,
    TASK_FOOD_QUERY,
    TASK_HOTEL_QUERY,
    TASK_PLAN_GENERATION,
    TEMPLATE_WEATHER,
    TEMPLATE_TRAFFIC,
    TEMPLATE_SCENIC,
    TEMPLATE_FOOD,
    TEMPLATE_HOTEL,
    TEMPLATE_PLAN,
    TEMPLATE_COMBINED,
    TEMPLATE_LUGGAGE,
    TEMPLATE_FUN,
    TOOL_WEATHER,
    TOOL_TRAFFIC,
    TOOL_SCENIC,
    TOOL_FOOD,
    TOOL_HOTEL,
    TOOL_LUGGAGE,
    TOOL_FUN,
)
from travel_agent.state import TravelAgentState


def _infer_intent_from_tools(required_tools: list[str], core_demand: str = "") -> str:
    """
    根据工具列表和核心需求推断意图动作

    Args:
        required_tools: 需要调用的工具列表
        core_demand: 核心需求描述

    Returns:
        推断的意图动作字符串
    """
    if not required_tools:
        # 根据 core_demand 推断
        if "天气" in core_demand:
            return "query_weather"
        if "交通" in core_demand or "路线" in core_demand:
            return "query_traffic"
        if "景点" in core_demand or "景区" in core_demand:
            return "query_scenic"
        if "美食" in core_demand or "餐厅" in core_demand:
            return "query_food"
        if "酒店" in core_demand or "住宿" in core_demand:
            return "query_hotel"
        if "行李" in core_demand or "穿搭" in core_demand:
            return "query_luggage"
        if "行程" in core_demand or "规划" in core_demand:
            return "full_plan"
        return "general_chat"

    tools_set = set(required_tools)

    # 单工具意图
    if len(required_tools) == 1:
        tool = required_tools[0]
        tool_intent_map = {
            TOOL_WEATHER: "query_weather",
            TOOL_TRAFFIC: "query_traffic",
            TOOL_SCENIC: "query_scenic",
            TOOL_FOOD: "query_food",
            TOOL_HOTEL: "query_hotel",
            TOOL_LUGGAGE: "query_luggage",
            TOOL_FUN: "query_fun",
        }
        if tool in tool_intent_map:
            return tool_intent_map[tool]

    # 多工具组合 → full_plan
    if len(required_tools) >= 2:
        # 如果包含行程规划相关工具，判定为 full_plan
        plan_tools = {TOOL_WEATHER, TOOL_SCENIC, TOOL_FOOD, TOOL_HOTEL, TOOL_TRAFFIC}
        overlap = tools_set & plan_tools
        if len(overlap) >= 2:
            return "full_plan"

    # 尝试从 core_demand 推断
    return _infer_intent_from_tools([], core_demand)


def _select_template(intent_action: str, tasks: list[str]) -> str:
    """
    根据意图和任务组合选择输出模板

    Args:
        intent_action: 意图动作
        tasks: 任务列表

    Returns:
        模板类型字符串
    """
    # 1. 优先使用意图→模板映射（单意图直接匹配）
    if intent_action and intent_action in INTENT_TEMPLATE_MAP:
        template = INTENT_TEMPLATE_MAP[intent_action]
        if template:
            return template

    # 2. 根据任务组合选择
    task_set = frozenset(tasks)

    # 多任务组合模板（精确匹配）
    if task_set in MULTI_TASK_TEMPLATES:
        return MULTI_TASK_TEMPLATES[task_set]

    # 3. 全流程规划 → 行程模板
    if TASK_PLAN_GENERATION in tasks:
        return TEMPLATE_PLAN

    # 4. 单任务对应模板
    if len(tasks) == 1:
        task = tasks[0]
        task_template_map = {
            TASK_WEATHER_QUERY: TEMPLATE_WEATHER,
            TASK_TRAFFIC_PLAN: TEMPLATE_TRAFFIC,
            TASK_SCENIC_QUERY: TEMPLATE_SCENIC,
            TASK_FOOD_QUERY: TEMPLATE_FOOD,
            TASK_HOTEL_QUERY: TEMPLATE_HOTEL,
        }
        if task in task_template_map:
            return task_template_map[task]

    # 5. 多任务但非预定义组合 → 使用组合模板
    if len(tasks) > 1:
        return TEMPLATE_COMBINED

    # 6. 默认模板
    return TEMPLATE_COMBINED


def _build_template_context(state: TravelAgentState, template_type: str, intent_action: str) -> dict:
    """
    构建模板上下文

    根据选中的模板类型，从 state 中提取所需数据，
    构建供 output_node 使用的上下文字典。

    Args:
        state: 当前状态
        template_type: 选中的模板类型
        intent_action: 意图动作

    Returns:
        模板上下文字典
    """
    params = state.extracted_params
    tool_results = state.tool_results

    # 基础上下文
    context = {
        "city": params.get("目的地", "") or params.get("当前位置", ""),
        "days": params.get("出行天数", "") or "未指定",
        "crowd": params.get("出行人数", "") or "未指定",
        "demand": params.get("核心需求", "") or "",
        "travel_time": params.get("出行时间段", "") or "",
        "template_type": template_type,
        "intent_name": INTENT_DISPLAY_MAP.get(intent_action, "查询"),
        "start_location": params.get("当前位置", "") or "",
        "destination": params.get("目的地", "") or "",
    }

    # 工具结果映射
    tool_result_map = {
        "weather": "天气数据",
        "traffic": "交通数据",
        "scenic": "景点数据",
        "food": "美食数据",
        "hotel": "住宿数据",
        "luggage": "行李穿搭",
        "fun": "趣玩活动",
    }

    # 将所有工具结果加入上下文
    for tool_name, result in tool_results.items():
        if result:
            context[f"{tool_name}_data"] = result
            context[tool_result_map.get(tool_name, f"{tool_name}数据")] = result

    # 根据模板类型添加特定格式化数据
    if template_type == TEMPLATE_WEATHER:
        context["weather_data"] = tool_results.get("weather", "暂无天气数据")

    elif template_type == TEMPLATE_TRAFFIC:
        context["traffic_data"] = tool_results.get("traffic", "暂无交通数据")

    elif template_type == TEMPLATE_SCENIC:
        context["scenic_data"] = tool_results.get("scenic", "暂无景点数据")

    elif template_type == TEMPLATE_FOOD:
        context["food_data"] = tool_results.get("food", "暂无美食数据")

    elif template_type == TEMPLATE_HOTEL:
        context["hotel_data"] = tool_results.get("hotel", "暂无住宿数据")

    elif template_type == TEMPLATE_LUGGAGE:
        # 行李穿搭需要天气数据作为参考
        context["weather_data"] = tool_results.get("weather", "")
        context["season"] = _infer_season(template_type)

    elif template_type == TEMPLATE_FUN:
        context["fun_data"] = tool_results.get("fun", "")

    elif template_type == TEMPLATE_PLAN:
        # 行程模板需要所有资源 + 汇总文本
        context["weather_data"] = tool_results.get("weather", "")
        context["traffic_data"] = tool_results.get("traffic", "")
        context["scenic_data"] = tool_results.get("scenic", "")
        context["food_data"] = tool_results.get("food", "")
        context["hotel_data"] = tool_results.get("hotel", "")
        context["all_resources"] = state.aggregated_all_resource or "暂无资源数据"
        context["task_list"] = [
            TASK_DISPLAY_MAP.get(t, t) for t in state.extracted_tasks
        ]

    elif template_type == TEMPLATE_COMBINED:
        # 组合模板包含所有有数据的资源
        context["all_resources"] = state.aggregated_all_resource or ""
        context["task_list"] = [
            TASK_DISPLAY_MAP.get(t, t) for t in state.extracted_tasks
        ]

    return context


def _infer_season(template_type: str) -> str:
    """
    根据模板类型推断当前季节提示（用于行李穿搭模板）

    Args:
        template_type: 模板类型

    Returns:
        季节提示字符串
    """
    # 简化处理，实际可根据月份动态判断
    from datetime import datetime
    month = datetime.now().month
    if month in (3, 4, 5):
        return "春季（3-5月）：建议轻薄外套+长袖"
    elif month in (6, 7, 8):
        return "夏季（6-8月）：建议短袖+防晒用品"
    elif month in (9, 10, 11):
        return "秋季（9-11月）：建议长袖+薄外套"
    else:
        return "冬季（12-2月）：建议羽绒服+保暖内衣"


@with_node_error_handler(NODE_TEMPLATE_ANALYSIS)
def analyze_template(state: TravelAgentState) -> dict:
    """
    LangGraph 节点：模板分析

    根据意图+任务组合选择输出模板，并构建模板上下文。
    确保输出模板与意图匹配，提供最合适的展示形式。

    Args:
        state: 包含 extracted_tasks 和 tool_results 的状态

    Returns:
        选中的模板类型和模板上下文
    """
    tasks = state.extracted_tasks
    params = state.extracted_params
    tool_results = state.tool_results

    # 推断意图动作
    intent_action = ""
    if state.intent_info:
        intent_info = state.intent_info
        # 优先使用 required_tools 推断
        if intent_info.required_tools:
            intent_action = _infer_intent_from_tools(
                intent_info.required_tools,
                intent_info.core_demand or ""
            )
        # 再尝试从 core_demand 推断
        if not intent_action or intent_action == "general_chat":
            core_demand = intent_info.core_demand or ""
            intent_action = _infer_intent_from_tools([], core_demand)

    # 如果仍无法推断，根据任务列表推断
    if not intent_action or intent_action == "general_chat":
        task_to_intent_map = {
            TASK_WEATHER_QUERY: "query_weather",
            TASK_TRAFFIC_PLAN: "query_traffic",
            TASK_SCENIC_QUERY: "query_scenic",
            TASK_FOOD_QUERY: "query_food",
            TASK_HOTEL_QUERY: "query_hotel",
        }
        if len(tasks) == 1 and tasks[0] in task_to_intent_map:
            intent_action = task_to_intent_map[tasks[0]]
        elif len(tasks) >= 2:
            intent_action = "full_plan"

    # 选择模板
    template_type = _select_template(intent_action, tasks)

    # 构建模板上下文
    template_context = _build_template_context(state, template_type, intent_action)

    print(f"\n[模板分析] 模板选择")
    print(f"  意图: {intent_action} ({INTENT_DISPLAY_MAP.get(intent_action, '未知')})")
    print(f"  任务: {[TASK_DISPLAY_MAP.get(t, t) for t in tasks]}")
    print(f"  选中模板: {template_type}")
    print(f"  模板上下文键: {list(template_context.keys())}")

    return {
        "selected_template": template_type,
        "template_context": template_context,
    }
