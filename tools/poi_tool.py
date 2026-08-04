# -*- coding: utf-8 -*-
"""
通用地标 POI 查询工具（LangChain @tool 规范）

统一高德 POI 搜索接口，覆盖住宿（酒店/民宿）、休闲娱乐（亲子/情侣/运动/文化）两类。
通过 poi_type 参数区分类型码，LLM 自主选择类型，不再拆分为多个工具。
"""

from typing import Dict, List

from langchain_core.tools import tool

from config import settings
from utils.api_request import http_client

# POI 类型码映射（高德分类编码）
_POI_TYPE_MAP = {
    "hotel": {"code": "140000", "label": "酒店住宿"},
    "fun": {"code": "休闲服务|娱乐服务|体育休闲服务", "label": "休闲娱乐"},
}

# 活动关键词映射（fun 类型按人群/需求优化搜索词）
_FUN_KEYWORD_MAP = {
    "亲子": "亲子 乐园 游乐场 儿童乐园",
    "情侣": "约会 电影院 浪漫 咖啡馆",
    "朋友": "聚会 KTV 酒吧 桌游",
    "运动": "健身 球馆 游泳馆 运动中心",
    "文化": "博物馆 展览 美术馆 图书馆",
}


def _build_fun_keyword(activity_type: str) -> str:
    """根据活动类型构建高德搜索关键词"""
    for key, value in _FUN_KEYWORD_MAP.items():
        if key in activity_type:
            return value
    return activity_type


def _search_poi_from_amap(
    city: str,
    poi_type: str,
    keyword: str = "",
    offset: int = 8,
    page: int = 1,
) -> List[Dict]:
    """统一高德 POI 搜索接口

    Args:
        city: 城市名称
        poi_type: "hotel" 或 "fun"
        keyword: 搜索关键词
        offset: 每页数量
        page: 页码

    Returns:
        POI 列表
    """
    type_info = _POI_TYPE_MAP.get(poi_type)
    if not type_info:
        return []

    url = "https://restapi.amap.com/v3/place/text"
    params = {
        "key": settings.AMAP_API_KEY,
        "keywords": keyword,
        "city": city,
        "types": type_info["code"],
        "citylimit": "true",
        "offset": offset,
        "page": page,
    }

    resp = http_client.get(url, params=params)
    if resp.get("status") != "1":
        return []
    return resp.get("pois", [])


def _format_poi_list(
    poi_list: List[Dict],
    poi_type: str,
    keyword: str,
    city: str,
) -> str:
    """格式化 POI 列表为文本"""
    if not poi_list:
        type_label = _POI_TYPE_MAP.get(poi_type, {}).get("label", "地标")
        return f"{city}未找到「{keyword or type_label}」相关{type_label}"

    type_label = _POI_TYPE_MAP.get(poi_type, {}).get("label", "地标")
    lines = [f"===== {city}｜{keyword or '推荐'} {type_label} ====="]
    for idx, poi in enumerate(poi_list, 1):
        name = poi.get("name", "未知场所")
        address = poi.get("address", "地址未收录")
        poi_type_name = poi.get("type", type_label)

        biz_ext = poi.get("biz_ext", {})
        rating = biz_ext.get("rating", "暂无评分")
        cost = biz_ext.get("cost", "暂无参考价")

        lines.append(f"{idx}. {poi_type_name}：{name}")
        lines.append(f"   详细地址：{address}")
        lines.append(f"   评分：{rating} | 参考人均：{cost}\n")

    return "\n".join(lines)


@tool(parse_docstring=True)
def search_poi(city: str, poi_type: str = "fun", keyword: str = "") -> str:
    """查询城市地标 POI（酒店住宿 / 休闲娱乐），统一高德 POI 搜索接口。

    适用场景：
    - poi_type="hotel"：查询酒店、民宿、住宿
    - poi_type="fun"：查询亲子乐园、电影院、KTV、博物馆、健身场馆等休闲娱乐

    返回内容：场所名称、类型、详细地址、评分、参考人均。

    Args:
        city: 目标城市名称，如"成都"、"杭州"。
        poi_type: POI 类型，可选值 "hotel"（酒店住宿）或 "fun"（休闲娱乐）。
        keyword: 搜索关键词。酒店类如"快捷酒店"、"民宿"；娱乐类如"亲子"、"情侣"、"运动"、"文化"。可选，为空则查热门推荐。
    """
    city_clean = city.strip()
    type_clean = poi_type.strip().lower()
    keyword_clean = keyword.strip() if keyword else ""

    if not city_clean:
        return "未识别出行城市，无法查询"

    if type_clean not in _POI_TYPE_MAP:
        return f"poi_type 必须是 'hotel' 或 'fun'，当前值：{poi_type}"

    # 娱乐类按人群/需求优化搜索词
    if type_clean == "fun" and keyword_clean:
        keyword_clean = _build_fun_keyword(keyword_clean)

    try:
        poi_data = _search_poi_from_amap(
            city=city_clean,
            poi_type=type_clean,
            keyword=keyword_clean,
            offset=5 if type_clean == "hotel" else 8,
        )
    except Exception as e:
        return f"{city_clean}{_POI_TYPE_MAP[type_clean]['label']}查询失败：{str(e)}"

    return _format_poi_list(poi_data, type_clean, keyword_clean, city_clean)
