# -*- coding: utf-8 -*-
"""
美食查询工具（LangChain @tool 规范）

LLM 通过 bind_tools 自主调用，参数由 LLM 直接生成，消除原 parse_params_by_llm 冗余 LLM 调用。
"""

from typing import Dict, List

from langchain_core.tools import tool

from config import settings
from utils.api_request import http_client


def _search_food_from_amap(city: str, keyword: str) -> List[Dict]:
    """从高德地图 POI 搜索美食店铺"""
    url = "https://restapi.amap.com/v3/place/text"
    params = {
        "key": settings.AMAP_API_KEY,
        "city": city,
        "keywords": f"美食 {keyword}",
        "types": "餐饮服务",
        "citylimit": True,
        "offset": 8,
        "page": 1
    }
    resp = http_client.get(url, params=params)
    if resp.get("status") != "1" or not resp.get("pois"):
        return []
    return resp["pois"]


def _format_food_list(poi_list: List[Dict]) -> str:
    """格式化美食店铺列表为文本"""
    if not poi_list:
        return "没有匹配到符合需求的美食店铺"
    lines = []
    for idx, poi in enumerate(poi_list, 1):
        name = poi.get("name", "未知店名")
        address = poi.get("address", "地址未标注")
        tag = poi.get("type", "")
        lines.append(f"{idx}. {name}")
        lines.append(f"地址：{address}")
        lines.append(f"品类标签：{tag}\n")
    return "\n".join(lines)


@tool(parse_docstring=True)
def search_food(city: str, taste_demand: str = "") -> str:
    """本地美食探店推荐，基于高德 POI 搜索餐饮服务。

    适用场景：用户询问某城市美食、餐厅、吃什么、网红小吃、本地特色菜。
    返回内容：店铺名称、地址、品类标签。

    Args:
        city: 目标城市名称，如"成都"、"杭州"。
        taste_demand: 饮食偏好/口味需求，如"火锅"、"不吃辣的川菜馆"、"网红小吃"、"本地家常菜"。可选，为空则推荐本地特色美食。
    """
    city_clean = city.strip()
    taste = taste_demand.strip() if taste_demand else ""

    if not city_clean:
        return "未识别出行城市，无法查询美食"
    if not taste:
        taste = "本地特色美食"

    try:
        poi_data = _search_food_from_amap(city_clean, taste)
    except Exception as e:
        return f"{city_clean}美食查询失败：{str(e)}"

    return _format_food_list(poi_data)
