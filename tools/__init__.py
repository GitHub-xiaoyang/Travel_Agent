# -*- coding: utf-8 -*-
"""
工具模块公共导出

供节点内 agent 通过 model.bind_tools() 自主调用，亦可直接 .invoke() 调用。
按 graph 分支分组：
- Phase 1: 天气/交通、景点、美食
- Phase 2: 行李/趣玩/酒店（统一为 search_poi）
"""

# Phase 1 分支：天气 & 交通
from tools.weather_tool import query_weather
from tools.traffic_tool import query_traffic_route

# Phase 1 分支：景点
from tools.scenic_tool import search_scenic

# Phase 1 分支：美食
from tools.food_tool import search_food

# Phase 2 分支：行李
from tools.luggage_tool import plan_luggage

# Phase 2 分支：地标 POI（酒店 + 趣玩统一接口）
from tools.poi_tool import search_poi

# 位置定位工具
from tools.location_tool import get_current_location, reverse_geocode

# 分支分组（供节点 agent 引用）
WEATHER_BRANCH_TOOLS = [query_weather, query_traffic_route, get_current_location]
SCENIC_BRANCH_TOOLS = [search_scenic]
FOOD_BRANCH_TOOLS = [search_food]
LUGGAGE_FUN_BRANCH_TOOLS = [plan_luggage, search_poi]

# 全部工具列表（供 bind_tools 统一绑定）
ALL_TRAVEL_TOOLS = [
    query_weather,
    query_traffic_route,
    search_scenic,
    search_food,
    plan_luggage,
    search_poi,
    get_current_location,
    reverse_geocode,
]

__all__ = [
    "query_weather",
    "query_traffic_route",
    "search_scenic",
    "search_food",
    "plan_luggage",
    "search_poi",
    "get_current_location",
    "reverse_geocode",
    "WEATHER_BRANCH_TOOLS",
    "SCENIC_BRANCH_TOOLS",
    "FOOD_BRANCH_TOOLS",
    "LUGGAGE_FUN_BRANCH_TOOLS",
    "ALL_TRAVEL_TOOLS",
]
