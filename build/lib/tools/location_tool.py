# -*- coding: utf-8 -*-
"""
当前位置获取工具（LangChain @tool 规范）

支持两种定位方式：
1. 浏览器 Geolocation API（前端调用，米级精度）→ 逆地理编码得到详细地址
2. IP 定位（服务端调用，市级精度）→ 作为 fallback

逆地理编码返回省/市/区/街道/周边 POI 等详细信息。
"""

from typing import Optional

from langchain_core.tools import tool

from config import settings
from utils.api_request import http_client


# ========== 内部辅助函数 ==========

def _get_location_by_ip() -> dict:
    """通过高德 IP 定位接口获取当前位置信息（市级精度，作为 fallback）"""
    url = "https://restapi.amap.com/v3/ip"
    params = {"key": settings.AMAP_API_KEY}
    try:
        resp = http_client.get(url, params=params)
        if resp.get("status") == "1":
            return {
                "province": resp.get("province", ""),
                "city": resp.get("city", ""),
                "adcode": resp.get("adcode", ""),
                "rectangle": resp.get("rectangle", ""),
                "location": resp.get("location", ""),
                "success": True,
            }
    except Exception:
        pass
    return {"success": False}


def _regeocode_detailed(lnglat: str) -> dict:
    """高德逆地理编码：经度,纬度 => 结构化详细地址

    返回字段：
        formatted_address: 完整格式化地址
        province: 省
        city: 市
        district: 区
        township: 街道/乡镇
        street: 街道名
        number: 门牌号
        adcode: 区域编码
        pois: 周边兴趣点列表
    """
    url = "https://restapi.amap.com/v3/geocode/regeo"
    params = {
        "key": settings.AMAP_API_KEY,
        "location": lnglat,
        "extensions": "all",  # 返回周边 POI
        "poitype": "商务住宅|科教文化服务|交通设施服务",
        "radius": "500",
        "output": "json",
    }
    try:
        resp = http_client.get(url, params=params)
        if resp.get("status") == "1":
            regeo = resp.get("regeocode", {})
            addr_comp = regeo.get("addressComponent", {})

            # 街道门牌信息
            street_info = addr_comp.get("streetNumber", {}) or {}
            if isinstance(street_info, str):
                street_info = {}

            # 周边 POI
            pois_raw = regeo.get("pois", []) or []
            pois = []
            for p in pois_raw[:3]:
                if isinstance(p, dict):
                    pois.append({
                        "name": p.get("name", ""),
                        "type": p.get("type", ""),
                        "distance": p.get("distance", ""),
                    })

            return {
                "formatted_address": regeo.get("formatted_address", ""),
                "province": addr_comp.get("province", "") or "",
                "city": addr_comp.get("city", "") or "",
                "district": addr_comp.get("district", "") or "",
                "township": addr_comp.get("township", "") or "",
                "street": street_info.get("street", "") or "",
                "number": street_info.get("number", "") or "",
                "adcode": addr_comp.get("adcode", "") or "",
                "pois": pois,
                "success": True,
            }
    except Exception:
        pass
    return {"success": False}


def _lnglat_to_address(lnglat: str) -> str:
    """高德逆地理编码：经度,纬度 => 文字地址（简化版，兼容旧调用）"""
    detail = _regeocode_detailed(lnglat)
    if detail.get("success"):
        return detail.get("formatted_address", "")
    return ""


def _format_location_detail(detail: dict, lnglat: str = "") -> str:
    """格式化详细地址信息为可读文本"""
    if not detail.get("success"):
        return f"⚠️ 坐标 {lnglat} 无法解析出地址"

    lines = ["📍 精准定位结果："]
    if detail.get("formatted_address"):
        lines.append(f"  📫 完整地址：{detail['formatted_address']}")
    if detail.get("province"):
        lines.append(f"  🏛 省/直辖市：{detail['province']}")
    if detail.get("city"):
        lines.append(f"  🏙 城市：{detail['city']}")
    if detail.get("district"):
        lines.append(f"  🏘 区/县：{detail['district']}")
    if detail.get("township"):
        lines.append(f"  🛣 街道/乡镇：{detail['township']}")
    if detail.get("street"):
        street_full = detail["street"]
        if detail.get("number"):
            street_full += detail["number"] + "号"
        lines.append(f"  🚏 街道门牌：{street_full}")
    if detail.get("adcode"):
        lines.append(f"  🔢 区域编码：{detail['adcode']}")
    if lnglat:
        lines.append(f"  📐 经纬度：{lnglat}")

    pois = detail.get("pois", [])
    if pois:
        lines.append("  📍 周边地标：")
        for p in pois:
            dist = f"（{p['distance']}米）" if p.get("distance") else ""
            lines.append(f"    · {p['name']} {dist}")

    return "\n".join(lines)


# ========== @tool 工具 ==========

@tool(parse_docstring=True)
def get_current_location() -> str:
    """获取用户当前所在城市，通过 IP 定位（市级精度）。

    适用场景：需要快速知道用户所在城市、作为交通路线规划的默认起点。
    精度：市级（无法定位到区/街道）。
    返回内容：当前所在省份、城市、区域编码、坐标范围。

    Args:
        无参数，直接调用即可。
    """
    loc = _get_location_by_ip()
    if not loc.get("success"):
        return "⚠️ IP 定位失败，建议使用浏览器精准定位或手动输入城市"

    province = loc.get("province", "")
    city = loc.get("city", "")
    adcode = loc.get("adcode", "")
    rectangle = loc.get("rectangle", "")

    lines = ["📍 IP 定位结果（市级精度）："]
    if province:
        lines.append(f"  省份：{province}")
    if city:
        lines.append(f"  城市：{city}")
    if adcode:
        lines.append(f"  区域编码：{adcode}")
    if rectangle:
        lines.append(f"  坐标范围：{rectangle}")

    if not city and province:
        lines.append(f"  （{province} 下未定位到具体城市）")

    lines.append("\n💡 提示：如需更精准定位（区/街道），请使用浏览器定位功能。")
    return "\n".join(lines)


@tool(parse_docstring=True)
def reverse_geocode(lng: str, lat: str) -> str:
    """将经纬度坐标转换为详细文字地址（省/市/区/街道/周边地标）。

    适用场景：浏览器 Geolocation API 获取精确坐标后，转换为可读地址。
    精度：米级（取决于输入坐标精度）。
    返回内容：完整地址、省市区街道、周边 3 个地标 POI。

    Args:
        lng: 经度，如 "116.481488"。
        lat: 纬度，如 "39.990464"。
    """
    lng_clean = lng.strip()
    lat_clean = lat.strip()
    if not lng_clean or not lat_clean:
        return "⚠️ 经纬度不能为空"

    lnglat = f"{lng_clean},{lat_clean}"
    detail = _regeocode_detailed(lnglat)
    return _format_location_detail(detail, lnglat)


@tool(parse_docstring=True)
def get_precise_location(lng: str, lat: str) -> str:
    """根据浏览器获取的精确经纬度，返回用户当前详细位置（省/市/区/街道/地标）。

    适用场景：前端浏览器 Geolocation API 获取坐标后调用，得到详细地址用于交通路线规划。
    精度：米级（GPS/WiFi 定位）。
    返回内容：完整地址、省市区街道、周边地标、经纬度。

    Args:
        lng: 经度，如 "116.481488"。
        lat: 纬度，如 "39.990464"。
    """
    lng_clean = lng.strip()
    lat_clean = lat.strip()
    if not lng_clean or not lat_clean:
        return "⚠️ 经纬度不能为空"

    lnglat = f"{lng_clean},{lat_clean}"
    detail = _regeocode_detailed(lnglat)
    return _format_location_detail(detail, lnglat)
