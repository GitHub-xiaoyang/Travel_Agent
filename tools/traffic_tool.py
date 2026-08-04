# -*- coding: utf-8 -*-
"""
交通路线规划工具（LangChain @tool 规范）

基于定位状态自动分级规划：
- 有精确定位（经纬度）：按直线距离分级
  - >300km：仅推荐飞机、高铁
  - 10~300km：自驾（距离优先 strategy=2，返回距离）
  - <=10km：骑行、打车、步行（骑行/步行返回距离，打车返回距离+预估费用）
- 无精确定位：省内出行方式（自驾/骑行/步行/公交，保留原逻辑）
"""

import math
from typing import Dict, List

from langchain_core.tools import tool

from config import settings
from utils.api_request import http_client


def _address_to_lnglat(address: str, city: str) -> str:
    """高德地理编码：文字地址 => 经度,纬度"""
    url = "https://restapi.amap.com/v3/geocode/geo"
    params = {
        "key": settings.AMAP_API_KEY,
        "address": address,
        "city": city
    }
    resp = http_client.get(url, params=params)
    if resp.get("status") != "1" or not resp.get("geocodes"):
        return ""
    return resp["geocodes"][0].get("location", "")


def _get_province_by_lnglat(lnglat: str) -> str:
    """通过高德逆地理编码获取坐标所属省份"""
    url = "https://restapi.amap.com/v3/geocode/regeo"
    params = {
        "key": settings.AMAP_API_KEY,
        "location": lnglat,
        "output": "json",
    }
    try:
        resp = http_client.get(url, params=params)
        if resp.get("status") == "1":
            addr = resp.get("regeocode", {}).get("addressComponent", {})
            province = addr.get("province", "")
            if isinstance(province, list):
                province = province[0] if province else ""
            return province or ""
    except Exception:
        pass
    return ""


def _haversine_distance(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """计算两个经纬度之间的直线距离（公里），使用 Haversine 公式"""
    earth_radius = 6371.0
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(earth_radius * c, 1)


def _parse_lnglat(lnglat: str):
    """将 "lng,lat" 字符串解析为 (float, float)"""
    parts = lnglat.split(",")
    if len(parts) != 2:
        return None, None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None, None


# ========== 路线查询基础函数 ==========

def _get_driving_route(origin: str, destination: str, strategy: int = 2) -> Dict:
    """查询自驾路线（strategy=2 距离优先）"""
    url = "https://restapi.amap.com/v3/direction/driving"
    params = {
        "key": settings.AMAP_API_KEY,
        "origin": origin,
        "destination": destination,
        "strategy": strategy
    }
    return http_client.get(url, params=params)


def _get_common_route(mode: str, origin: str, destination: str) -> Dict:
    """查询骑行/步行路线"""
    url = "https://restapi.amap.com/v3/direction"
    params = {
        "key": settings.AMAP_API_KEY,
        "origin": origin,
        "destination": destination
    }
    return http_client.get(f"{url}/{mode}", params=params)


def _get_transit_route(origin: str, destination: str, city: str) -> Dict:
    """查询公交路线"""
    url = "https://restapi.amap.com/v3/direction"
    params = {
        "key": settings.AMAP_API_KEY,
        "origin": origin,
        "destination": destination,
        "city": city,
        "strategy": 0
    }
    return http_client.get(f"{url}/transit/integrated", params=params)


# ========== 路线解析函数 ==========

def _parse_driving_info(raw: Dict) -> Dict:
    """解析自驾路线数据（strategy=2），返回距离、耗时、打车费用"""
    if raw.get("status") != "1":
        return None
    try:
        path = raw["route"]["paths"][0]
        distance_km = round(int(path["distance"]) / 1000, 1)
        duration_min = round(int(path["duration"]) / 60)
        taxi_cost = path.get("taxi_cost", "")
        return {
            "mode": "自驾",
            "distance_km": distance_km,
            "duration_min": duration_min,
            "taxi_cost": taxi_cost,
            "desc": f"自驾路线（距离优先），距离约{distance_km}km"
        }
    except Exception:
        return None


def _parse_taxi_info(raw: Dict) -> Dict:
    """从自驾路线数据中提取打车信息（距离+预估费用）"""
    if raw.get("status") != "1":
        return None
    try:
        path = raw["route"]["paths"][0]
        distance_km = round(int(path["distance"]) / 1000, 1)
        duration_min = round(int(path["duration"]) / 60)
        taxi_cost = path.get("taxi_cost", "")
        cost_str = f"预估费用{taxi_cost}元" if taxi_cost else "预估费用未知"
        return {
            "mode": "打车",
            "distance_km": distance_km,
            "duration_min": duration_min,
            "taxi_cost": taxi_cost,
            "desc": f"打车，距离约{distance_km}km，{cost_str}"
        }
    except Exception:
        return None


def _parse_riding_walking_info(mode: str, raw: Dict) -> Dict:
    """解析骑行/步行路线数据，返回距离"""
    mode_name = "骑行" if mode == "riding" else "步行"
    if raw.get("status") != "1":
        return None
    try:
        path = raw["route"]["paths"][0]
        distance_km = round(int(path["distance"]) / 1000, 1)
        duration_min = round(int(path["duration"]) / 60)
        return {
            "mode": mode_name,
            "distance_km": distance_km,
            "duration_min": duration_min,
            "taxi_cost": "",
            "desc": f"{mode_name}路线，距离约{distance_km}km"
        }
    except Exception:
        return None


def _parse_route_info(mode: str, raw: Dict):
    """解析省内路线原始数据为标准化信息（保留兼容旧逻辑）"""
    res = {"mode": mode, "cost": None, "duration_min": None, "desc": ""}
    if raw.get("status") != "1":
        return None
    try:
        if mode == "transit":
            item = raw["route"]["transits"][0]
            res["cost"] = int(float(item["cost"]))
            res["duration_min"] = round(int(item["duration"]) / 60)
            res["desc"] = "公交地铁组合出行"
        elif mode == "driving":
            item = raw["route"]["paths"][0]
            res["cost"] = int(item["tolls"])
            res["duration_min"] = round(int(item["duration"]) / 60)
            res["desc"] = f"自驾，高速费{item['tolls']}元"
        elif mode == "riding":
            item = raw["route"]["paths"][0]
            res["cost"] = 0
            res["duration_min"] = round(int(item["duration"]) / 60)
            res["desc"] = "骑行（电动车/自行车）"
        elif mode == "walking":
            item = raw["route"]["paths"][0]
            res["cost"] = 0
            res["duration_min"] = round(int(item["duration"]) / 60)
            res["desc"] = "步行路线"
    except Exception:
        return None
    return res


# ========== 省内出行（无定位时的兼容逻辑） ==========

def _load_all_routes(origin, destination, city) -> List:
    """加载省内所有出行方式的路线"""
    route_list = []
    for m in ["driving", "riding", "walking"]:
        try:
            data = _get_common_route(m, origin, destination)
            info = _parse_route_info(m, data)
            if info:
                route_list.append(info)
        except Exception:
            continue
    try:
        transit_data = _get_transit_route(origin, destination, city)
        transit_info = _parse_route_info("transit", transit_data)
        if transit_info:
            route_list.append(transit_info)
    except Exception:
        pass
    return route_list


def _get_top3_recommend(origin, destination, city):
    """从省内路线中选出最快/最便宜/均衡的推荐方案"""
    routes = _load_all_routes(origin, destination, city)
    if not routes:
        return []
    fastest = min(routes, key=lambda x: x["duration_min"])
    cheapest = min(routes, key=lambda x: x["cost"])
    balance = min(routes, key=lambda x: x["duration_min"] + x["cost"])
    final = []
    used = set()
    for item in [fastest, cheapest, balance]:
        if item["mode"] not in used:
            used.add(item["mode"])
            final.append(item)
    for r in routes:
        if len(final) >= 4:
            break
        if r["mode"] not in used:
            used.add(r["mode"])
            final.append(r)
    return final


def _get_intercity_recommend(distance_km: float) -> List[Dict]:
    """根据直线距离推荐跨省出行方式（仅飞机+高铁）"""
    recommendations = []
    if distance_km > 300:
        recommendations.append({
            "mode": "飞机",
            "reason": f"直线距离约{distance_km}km，距离较远，飞机更快捷"
        })
        recommendations.append({
            "mode": "高铁/动车",
            "reason": f"直线距离约{distance_km}km，高铁出行便捷舒适"
        })
    else:
        # <=300km 不应该走此分支，但兜底处理
        recommendations.append({
            "mode": "高铁/动车",
            "reason": f"直线距离约{distance_km}km，高铁/动车合适"
        })
    return recommendations


@tool(parse_docstring=True)
def query_traffic_route(
    start_address: str = "",
    end_address: str = "",
    city: str = "",
    start_lng: str = "",
    start_lat: str = "",
    travel_days: str = "",
    travel_time: str = ""
) -> str:
    """智能路线规划，基于定位状态自动分级。

    有精确定位（start_lng/start_lat）时按距离分级：
    - >300km：仅推荐飞机、高铁两种方式
    - 10~300km：自驾（距离优先 strategy=2，返回距离）
    - <=10km：骑行、打车、步行（骑行/步行返回距离，打车返回距离+预估费用）

    无精确定位时：省内出行方式（自驾/骑行/步行/公交），start_address 为空自动 IP 定位。

    适用场景：用户询问两地之间的交通路线、怎么去、出行方案。
    返回内容：分区块展示出发地、目的地、距离、推荐方式。

    Args:
        start_address: 出发地文字地址，如"北京"、"成都春熙路"。可选，有经纬度时优先用经纬度。
        end_address: 目的地文字地址，如"上海"、"杭州西湖"。
        city: 目的地城市，如"上海"、"杭州"。
        start_lng: 出发地经度（精准定位获取），如"116.397428"。可选，提供后启用距离分级规划。
        start_lat: 出发地纬度（精准定位获取），如"39.90923"。可选，提供后启用距离分级规划。
        travel_days: 出行天数，如"3天"。可选。
        travel_time: 出行时间段，如"周末"、"五一"。可选。
    """
    start_addr = start_address.strip() if start_address else ""
    end_addr = end_address.strip()
    city_clean = city.strip()
    start_lng_str = start_lng.strip() if start_lng else ""
    start_lat_str = start_lat.strip() if start_lat else ""

    if not end_addr or not city_clean:
        return "信息不全，请补充目的地和所在城市"

    has_precise_location = bool(start_lng_str and start_lat_str)

    # === 解析起点坐标 ===
    if has_precise_location:
        origin = f"{start_lng_str},{start_lat_str}"
        if not start_addr:
            start_addr = "当前位置"
    else:
        # 无经纬度，使用地址解析或 IP 定位
        if not start_addr:
            try:
                from tools.location_tool import _get_location_by_ip
                loc = _get_location_by_ip()
                if loc.get("success") and loc.get("city"):
                    start_addr = loc["city"]
                else:
                    return "⚠️ 未提供出发地且自动定位失败，请告诉我出发地或所在城市～"
            except Exception:
                return "⚠️ 未提供出发地且自动定位失败，请告诉我出发地或所在城市～"
        origin = _address_to_lnglat(start_addr, city_clean)

    destination = _address_to_lnglat(end_addr, city_clean)
    if not origin or not destination:
        return f"地址「{start_addr}」或「{end_addr}」无法解析出坐标，请更换更详细地址"

    # 计算直线距离
    lng1, lat1 = _parse_lnglat(origin)
    lng2, lat2 = _parse_lnglat(destination)
    distance_km = _haversine_distance(lng1, lat1, lng2, lat2)

    output = []
    output.append(f"出发地：{start_addr} → 目的地：{end_addr}")
    output.append(f"直线距离：约{distance_km}km | 出行时长：{travel_days} | 出行时段：{travel_time}")

    # ========== 有精确定位：按距离分级规划 ==========
    if has_precise_location:
        if distance_km > 300:
            # >300km：仅推荐飞机、高铁
            output.append("")
            output.append("━" * 30)
            output.append("✈️ 长途出行推荐（>300km）")
            output.append("━" * 30)
            output.append(f"直线距离：约{distance_km}km")
            for rec in _get_intercity_recommend(distance_km):
                output.append(f"  📌 {rec['mode']}")
                output.append(f"     {rec['reason']}")

        elif distance_km > 10:
            # 10~300km：自驾（strategy=2 距离优先，返回距离）
            output.append("")
            output.append("━" * 30)
            output.append("🚗 中短途出行推荐（10~300km）")
            output.append("━" * 30)
            output.append(f"直线距离：约{distance_km}km")
            try:
                driving_raw = _get_driving_route(origin, destination, strategy=2)
                driving_info = _parse_driving_info(driving_raw)
                if driving_info:
                    output.append(f"  📌 自驾（距离优先路线）")
                    output.append(f"     距离：约{driving_info['distance_km']}km")
                    output.append(f"     耗时：约{driving_info['duration_min']}分钟")
                    output.append(f"     {driving_info['desc']}")
                else:
                    output.append("  自驾路线查询失败，请稍后重试")
            except Exception:
                output.append("  自驾路线查询失败，请稍后重试")

        else:
            # <=10km：骑行、打车、步行
            output.append("")
            output.append("━" * 30)
            output.append("🚲 短途出行推荐（<=10km）")
            output.append("━" * 30)
            output.append(f"直线距离：约{distance_km}km")

            # 打车（自驾 strategy=2 路线距离 + taxi_cost）
            try:
                driving_raw = _get_driving_route(origin, destination, strategy=2)
                taxi_info = _parse_taxi_info(driving_raw)
                if taxi_info:
                    output.append(f"  📌 打车")
                    output.append(f"     距离：约{taxi_info['distance_km']}km")
                    output.append(f"     耗时：约{taxi_info['duration_min']}分钟")
                    cost_str = f"     预估费用：{taxi_info['taxi_cost']}元" if taxi_info['taxi_cost'] else ""
                    if cost_str:
                        output.append(cost_str)
            except Exception:
                pass

            # 骑行（返回距离）
            try:
                riding_raw = _get_common_route("riding", origin, destination)
                riding_info = _parse_riding_walking_info("riding", riding_raw)
                if riding_info:
                    output.append(f"  📌 骑行")
                    output.append(f"     距离：约{riding_info['distance_km']}km")
                    output.append(f"     耗时：约{riding_info['duration_min']}分钟")
            except Exception:
                pass

            # 步行（返回距离）
            try:
                walking_raw = _get_common_route("walking", origin, destination)
                walking_info = _parse_riding_walking_info("walking", walking_raw)
                if walking_info:
                    output.append(f"  📌 步行")
                    output.append(f"     距离：约{walking_info['distance_km']}km")
                    output.append(f"     耗时：约{walking_info['duration_min']}分钟")
            except Exception:
                pass

        return "\n".join(output)

    # ========== 无精确定位：省内出行方式（保留原逻辑） ==========
    # 判断同省/跨省
    start_province = _get_province_by_lnglat(origin)
    end_province = _get_province_by_lnglat(destination)
    is_same_province = (
        start_province and end_province and start_province == end_province
    )

    # === 跨省出行部分（仅跨省时显示）===
    if not is_same_province:
        output.append("")
        output.append("━" * 30)
        output.append("📦 跨省出行")
        output.append("━" * 30)
        output.append(f"出发地：{start_addr}（{start_province}）")
        output.append(f"目的地：{end_addr}（{end_province}）")
        output.append(f"直线距离：约{distance_km}km")
        intercity = _get_intercity_recommend(distance_km)
        for rec in intercity:
            output.append(f"推荐方式：{rec['mode']}")
            output.append(f"推荐理由：{rec['reason']}")

    # === 省内出行部分（始终显示）===
    output.append("")
    output.append("━" * 30)
    output.append("🚗 省内出行")
    output.append("━" * 30)
    output.append(f"出发地：{start_addr} → 目的地：{end_addr}")

    route_data = _get_top3_recommend(origin, destination, city_clean)
    name_map = {
        "transit": "公共交通",
        "driving": "自驾",
        "riding": "骑行/电动车",
        "walking": "步行"
    }

    if route_data:
        output.append("省内交通方案：")
        for idx, way in enumerate(route_data, 1):
            cost_info = f"花费：{way['cost']}元" if way['cost'] else "免费"
            output.append(f"  {idx}. {name_map.get(way['mode'], way['mode'])} | 耗时：{way['duration_min']}分钟 | {cost_info} | {way['desc']}")
    else:
        output.append("省内暂无可用路线数据")

    return "\n".join(output)
