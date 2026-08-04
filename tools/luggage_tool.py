# -*- coding: utf-8 -*-
"""
行李穿搭规划工具（LangChain @tool 规范）

规则模板生成（按城市/天数/季节），内部复用 query_weather 获取目的地天气。
"""

import re

from langchain_core.tools import tool

from tools.weather_tool import query_weather


def _parse_temperature(weather_text: str) -> tuple[int, int]:
    """从天气文本中提取最高温和最低温"""
    temps = re.findall(r'(\d+)℃', weather_text)
    if not temps:
        return 20, 15
    temp_values = [int(t) for t in temps]
    return max(temp_values), min(temp_values)


def _build_luggage_by_rules(
    weather_text: str, travel_days: str, user_hint: str, city: str
) -> str:
    """根据规则/模板生成行李清单与穿搭方案（无需 LLM）"""
    max_temp, min_temp = _parse_temperature(weather_text)

    # 根据最低温选择衣物
    if min_temp >= 25:
        clothes = ["短袖T恤", "短裤/裙子", "凉鞋/拖鞋", "防晒衣"]
        outerwear = "无需外套"
    elif min_temp >= 15:
        clothes = ["长袖衬衫/T恤", "薄长裤", "运动鞋", "薄外套"]
        outerwear = "薄外套/卫衣"
    elif min_temp >= 5:
        clothes = ["长袖T恤/衬衫", "厚长裤", "运动鞋", "夹克"]
        outerwear = "夹克/风衣"
    else:
        clothes = ["保暖内衣", "毛衣/抓绒", "厚长裤", "羽绒服"]
        outerwear = "羽绒服/厚外套"

    # 下雨检测
    rain_gear = "雨伞/折叠雨衣（天气预报有雨）" if "雨" in weather_text else ""

    # 天数解析
    day_match = re.search(r'(\d+)', travel_days)
    days_num = int(day_match.group(1)) if day_match else 3

    # 构建输出
    lines = [
        "====出行基础信息====",
        f"目的地：{city}",
        f"出行时长：{travel_days}",
        f"个性化需求：{user_hint}",
        "",
        "====标准化天气信息====",
        weather_text,
        "",
        "====行李&穿搭完整方案====",
        "",
        "【分类行李打包清单】",
        "",
        "1️⃣ 证件电子",
        "· 身份证/护照（安检必备）",
        "· 手机 + 充电器 + 充电宝（≤100Wh可登机）",
        "· 旅行保险单（如有）",
        "",
        f"2️⃣ 日常衣物（{days_num}天用量）",
        f"· {'、'.join(clothes)}（建议按天数准备替换衣物）",
        f"· {outerwear}",
    ]
    if rain_gear:
        lines.append(f"· {rain_gear}")

    lines.extend([
        "",
        "3️⃣ 洗护护肤（旅行装≤100ml可登机）",
        "· 洗面奶、护肤品旅行装",
        "· 牙刷牙膏旅行套装",
        "· 毛巾/一次性浴巾",
        "",
        "4️⃣ 常备药品",
        "· 感冒药、退烧药",
        "· 肠胃药、止泻药",
        "· 创可贴、晕车药",
        "",
        "5️⃣ 数码配件",
        "· 数据线（Type-C/Lightning）",
        "· 耳机",
        "· 相机/自拍杆（如有需要）",
        "",
        "6️⃣ 随身小件",
        "· 水杯、纸巾、湿巾",
        "· 零食（长途交通备用）",
        "· 垃圾袋",
        "",
        "【分场景穿搭推荐】",
        "",
        f"☀️ 白天穿搭：{clothes[0]} + {clothes[1]}，舒适透气为主",
        f"🌆 早晚穿搭：{clothes[0]} + {outerwear}，温差大建议叠穿",
    ])

    if rain_gear:
        lines.append(f"🌧 雨天穿搭：{rain_gear}，鞋子选防滑防水款")
    if max_temp >= 30:
        lines.append("🧴 防晒提醒：温度较高，建议防晒霜+墨镜+遮阳帽")

    lines.append("")
    lines.append(f"💡 温馨提示：当前气温 {min_temp}℃-{max_temp}℃，")
    if min_temp < 10:
        lines.append("注意保暖防寒")
    elif max_temp > 30:
        lines.append("注意防暑降温+补水")
    else:
        lines.append("体感舒适，适合出行")
    if user_hint:
        lines.append(f"。个性化需求：{user_hint}")

    return "\n".join(lines)


@tool(parse_docstring=True)
def plan_luggage(city: str, travel_days: str, user_hint: str = "", weather_text: str = "") -> str:
    """根据目的地天气、出行天数生成行李清单与穿搭推荐。

    适用场景：用户询问行李打包、带什么衣服、穿搭建议、出行准备。
    返回内容：分类行李清单 + 分场景穿搭方案。规则模板生成，无 LLM 调用，响应快。

    Args:
        city: 目的地城市名称，如"成都"、"西安"。
        travel_days: 出行天数，如"3天"、"5天"。
        user_hint: 个性化需求提示，如"需要轻便好安检、偏休闲穿搭"。可选。
        weather_text: 已查询的天气文本。若提供则直接使用，不再调用天气接口；为空时自动查询。
    """
    city_clean = city.strip()
    days_clean = travel_days.strip() if travel_days else "3天"
    hint_clean = user_hint.strip() if user_hint else ""

    if not city_clean:
        return "未识别目的地城市，无法生成行李穿搭方案"

    # 优先使用外部传入的天气数据（Phase 1 已查询），否则自动查询
    weather_clean = weather_text.strip() if weather_text else ""
    if not weather_clean:
        try:
            weather_clean = query_weather.invoke({"city": city_clean})
        except Exception as e:
            weather_clean = (
                f"【天气获取失败】{city_clean}天气接口调用异常，按照该城市当前季节规划行李穿搭，"
                f"留意温差、降雨。错误：{str(e)}"
            )

    return _build_luggage_by_rules(weather_clean, days_clean, hint_clean, city_clean)
