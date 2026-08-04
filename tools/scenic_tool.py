# -*- coding: utf-8 -*-
"""
景点查询工具（LangChain @tool 规范）

LLM 通过 bind_tools 自主调用，参数由 LLM 直接生成，消除原 parse_params_by_llm 冗余 LLM 调用。
"""

from langchain_core.tools import tool

from config import settings
from utils.api_request import http_client


@tool(parse_docstring=True)
def search_scenic(city: str, keyword: str = "") -> str:
    """查询城市旅游景点、自然风光、人文古迹、公园景区。

    适用场景：用户询问某城市有什么景点、好玩的地方、必去打卡地、公园。
    返回内容：景点名称、类型、详细地址、游客评分、参考人均消费。

    Args:
        city: 目标城市名称，如"成都"、"杭州"。
        keyword: 筛选关键词，如人群/需求标签（情侣拍照、亲子休闲、宽窄巷子、大佛）。可选，为空则查热门景点。
    """
    city_clean = city.strip()
    keyword_clean = keyword.strip() if keyword else ""

    if not city_clean:
        return "未识别到目的地城市，无法查询景点"

    url = "https://restapi.amap.com/v3/place/text"
    params = {
        "key": settings.AMAP_API_KEY,
        "keywords": keyword_clean,
        "city": city_clean,
        "types": "110000",
        "citylimit": "true",
        "offset": 8,
        "page": 1
    }

    try:
        resp = http_client.get(url, params=params)
    except Exception as e:
        return f"【{city_clean}】景点接口请求失败：{str(e)}"

    if resp.get("status") != "1":
        return f"【{city_clean}】景点接口请求失败，查询异常"

    poi_list = resp.get("pois", [])
    if not poi_list:
        return f"在{city_clean}未找到「{keyword_clean or '景点'}」相关景点"

    lines = [f"===== {city_clean}｜{keyword_clean or '热门景点'} 景点推荐 ====="]
    for idx, spot in enumerate(poi_list, 1):
        name = spot.get("name", "暂无名称")
        address = spot.get("address", "地址未收录")
        category = spot.get("type", "景点")

        biz_ext = spot.get("biz_ext", {})
        rating = biz_ext.get("rating", "暂无评分")
        cost = biz_ext.get("cost", "无人均参考")

        lines.append(f"{idx}. 景点名称：{name}")
        lines.append(f"   景点类型：{category}")
        lines.append(f"   详细地址：{address}")
        lines.append(f"   游客评分：{rating}")
        lines.append(f"   参考人均：{cost}\n")

    return "\n".join(lines)
