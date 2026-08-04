# -*- coding: utf-8 -*-
"""
天气查询工具（LangChain @tool 规范）

LLM 通过 bind_tools 自主调用，参数由 LLM 直接生成，无需内部 LLM 解析。
"""

from langchain_core.tools import tool

from config import settings
from utils.api_request import http_client


@tool(parse_docstring=True)
def query_weather(city: str) -> str:
    """查询城市实时天气及多日预报，基于高德天气接口。

    适用场景：用户询问某城市天气、气温、天气预报、是否下雨、穿什么。
    返回内容：实时天气 + 今日及后续多日昼夜预报。

    Args:
        city: 城市名称，如"杭州"、"成都"、"北京"。
    """
    url = "https://restapi.amap.com/v3/weather/weatherInfo"
    params = {
        "key": settings.AMAP_API_KEY,
        "city": city,
        "extensions": "all"
    }
    try:
        raw_data = http_client.get(url, params=params)
    except Exception as e:
        return f"{city}天气查询失败：网络请求失败：{str(e)}"

    if raw_data.get("status") != "1":
        err = raw_data.get("error", "高德天气接口异常")
        return f"{city}天气查询失败：{err}"

    res_lines = []
    live_info = raw_data.get("lives", [])
    if live_info:
        live = live_info[0]
        res_lines.append(f"【{live.get('city')} 实时天气】")
        res_lines.append(f"天气：{live.get('weather')}，当前气温：{live.get('temperature')}℃")
        res_lines.append(f"风向风力：{live.get('winddirection')}{live.get('windpower')}级，湿度：{live.get('humidity')}%")

    forecast_group = raw_data.get("forecasts", [])
    if forecast_group:
        casts = forecast_group[0].get("casts", [])
        res_lines.append("\n====今日及后续天气预报====")
        for day in casts:
            date = day.get("date", "未知日期")
            day_weather = day.get("dayweather", "")
            night_weather = day.get("nightweather", "")
            day_temp = day.get("daytemp", "")
            night_temp = day.get("nighttemp", "")
            res_lines.append(f"{date} | 白天：{day_weather} {day_temp}℃  夜间：{night_weather} {night_temp}℃")

    return "\n".join(res_lines) if res_lines else f"{city}天气数据为空"
