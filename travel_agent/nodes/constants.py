# -*- coding: utf-8 -*-
"""
节点名称常量定义 + 共享意图解析常量

新流程拓扑（严格按用户流程图）：
  用户输入 → 意图解析 → 任务+参数提取 → 工具调用(并行) → 资源汇总 → 模板分析 → 输出结果
"""

# ========== 业务节点名（新流程） ==========
NODE_INTENT = "intent_node"
NODE_TASK_PARAM = "task_param_node"
NODE_TOOL_CALLS = "tool_calls_node"
NODE_RESOURCE_AGG = "resource_aggregation_node"
NODE_TEMPLATE_ANALYSIS = "template_analysis_node"
NODE_OUTPUT = "output_node"
NODE_FALLBACK = "fallback_node"

# ========== 工具名常量（用于任务映射） ==========
TOOL_WEATHER = "weather"
TOOL_SCENIC = "scenic"
TOOL_FOOD = "food"
TOOL_HOTEL = "hotel"
TOOL_TRAFFIC = "traffic"
TOOL_LUGGAGE = "luggage"
TOOL_FUN = "fun"

# ========== 任务 → 工具映射 ==========
# 流程图中的任务列表
TASK_WEATHER_QUERY = "天气查询"
TASK_TRAFFIC_PLAN = "交通规划"
TASK_SCENIC_QUERY = "景点查询"
TASK_FOOD_QUERY = "美食查询"
TASK_HOTEL_QUERY = "住宿查询"
TASK_PLAN_GENERATION = "行程攻略"

# 任务 → 对应工具
TASK_TOOL_MAP = {
    TASK_WEATHER_QUERY: [TOOL_WEATHER],
    TASK_TRAFFIC_PLAN: [TOOL_TRAFFIC],
    TASK_SCENIC_QUERY: [TOOL_SCENIC],
    TASK_FOOD_QUERY: [TOOL_FOOD],
    TASK_HOTEL_QUERY: [TOOL_HOTEL],
    TASK_PLAN_GENERATION: [TOOL_WEATHER, TOOL_SCENIC, TOOL_FOOD, TOOL_HOTEL, TOOL_TRAFFIC],
}

# ========== 意图 → 任务映射 ==========
# 根据意图确定需要执行的任务列表
INTENT_TASK_MAP = {
    "query_weather": [TASK_WEATHER_QUERY],
    "query_traffic": [TASK_TRAFFIC_PLAN],
    "query_scenic": [TASK_SCENIC_QUERY],
    "query_food": [TASK_FOOD_QUERY],
    "query_hotel": [TASK_HOTEL_QUERY],
    "query_luggage": [TASK_PLAN_GENERATION],
    "query_fun": [TASK_PLAN_GENERATION],
    "book_ticket": [TASK_SCENIC_QUERY],
    "full_plan": [TASK_WEATHER_QUERY, TASK_TRAFFIC_PLAN, TASK_SCENIC_QUERY, TASK_FOOD_QUERY, TASK_HOTEL_QUERY],
    "optimize_plan": [TASK_PLAN_GENERATION],
}

# ========== 参数定义（流程图中的参数列表） ==========
PARAM_DESTINATION = "目的地"
PARAM_DAYS = "出行天数"
PARAM_CROWD = "出行人数"
PARAM_REQUIREMENTS = "其他"  # 景点要求/美食推荐必吃/网红等

# ========== 节点显示名（用于进度反馈） ==========
NODE_DISPLAY_NAMES = {
    NODE_INTENT: "意图解析",
    NODE_TASK_PARAM: "任务+参数提取",
    NODE_TOOL_CALLS: "工具调用",
    NODE_RESOURCE_AGG: "资源汇总",
    NODE_TEMPLATE_ANALYSIS: "模板分析",
    NODE_OUTPUT: "输出渲染",
    NODE_FALLBACK: "异常兜底",
}


# ============================================================
# 共享意图解析常量（chat_agent.py + intent_node.py 共用）
# ============================================================

# 意图 → 中文名映射
ACTION_LABELS = {
    "query_weather": "天气查询",
    "query_scenic": "景点查询",
    "query_food": "美食查询",
    "query_hotel": "酒店查询",
    "query_traffic": "交通查询",
    "query_luggage": "行李穿搭",
    "query_fun": "趣玩活动",
    "book_ticket": "门票预订",
    "full_plan": "完整行程规划",
    "optimize_plan": "行程优化",
    "general_chat": "闲聊",
}

# 需要城市参数的意图（天气查询例外：可通过定位兜底）
CITY_REQUIRED_ACTIONS = {
    "query_scenic", "query_food", "query_hotel",
    "query_fun", "book_ticket", "query_luggage"
}

# 意图 → 关键词映射（规则引擎 + 兜底共用）
INTENT_KEYWORDS = {
    "query_weather": ["天气", "气温", "下雨", "温度", "天气预报", "冷热", "穿衣", "下雨吗", "下雪", "近日天气", "今天天气", "最近天气", "查天气", "天气如何"],
    "query_scenic": ["景点", "景区", "公园", "游玩", "打卡", "必去", "风景区", "名胜", "好玩的"],
    "query_food": ["美食", "餐厅", "小吃", "好吃", "推荐吃", "美食推荐", "特色菜", "吃什么"],
    "query_hotel": ["酒店", "民宿", "住宿", "旅馆", "宾馆", "客栈"],
    "query_traffic": ["交通", "路线", "怎么去", "怎么坐车", "地铁", "打车", "公交", "自驾", "骑行", "步行", "飞机", "高铁", "火车"],
    "query_luggage": ["行李", "打包", "穿搭", "带什么", "准备什么", "行李清单"],
    "query_fun": ["趣玩", "活动", "娱乐", "体验", "玩什么", "休闲"],
    "book_ticket": ["门票", "预订", "订票", "买票", "预约"],
    "full_plan": ["规划", "安排", "攻略", "行程", "几天", "帮我规划", "帮我安排", "推荐路线", "旅游", "旅行", "度假"],
    "optimize_plan": ["优化", "调整", "修改行程", "改行程", "重新规划"],
}

# 城市列表（简化版，用于城市名提取）
CITY_NAMES = [
    "北京", "上海", "广州", "深圳", "成都", "杭州", "重庆", "武汉", "西安", "南京",
    "苏州", "天津", "长沙", "青岛", "郑州", "厦门", "宁波", "合肥", "福州", "济南",
    "大连", "昆明", "沈阳", "哈尔滨", "南昌", "贵阳", "南宁", "太原", "兰州",
    "海口", "三亚", "石家庄", "乌鲁木齐", "呼和浩特", "银川", "西宁", "拉萨",
    "丽江", "大理", "桂林", "张家界", "九寨沟", "黄山", "泰山", "峨眉山",
]


# ============================================================
# 意图降级规则（chat_agent.py + main_app.py 共用）
# ============================================================

def check_degrade(action: str, city: str = "", current_location: str = "") -> str:
    """
    统一降级检查：判断工具意图是否需要降级为 general_chat

    规则：
    - query_weather 永不降级（可通过定位兜底或引导用户指定城市）
    - 其他 CITY_REQUIRED_ACTIONS 意图，无城市且无定位时降级
    - 非工具意图（如 general_chat）保持原样

    Args:
        action: 意图动作（如 query_weather, query_scenic 等）
        city: 用户明确指定的城市名
        current_location: 定位获取的当前位置（可为空）

    Returns:
        降级后的意图动作
    """
    # 天气查询特殊处理：永不降级
    if action == "query_weather":
        return action

    # 需要城市的意图，检查降级条件
    if action in CITY_REQUIRED_ACTIONS:
        if not city and not current_location:
            return "general_chat"

    return action


# ============================================================
# 输出模板映射（意图+任务组合 → 输出模板类型）
# ============================================================

# 模板类型常量
TEMPLATE_WEATHER = "weather_template"
TEMPLATE_TRAFFIC = "traffic_template"
TEMPLATE_SCENIC = "scenic_template"
TEMPLATE_FOOD = "food_template"
TEMPLATE_HOTEL = "hotel_template"
TEMPLATE_PLAN = "plan_template"
TEMPLATE_COMBINED = "combined_template"
TEMPLATE_LUGGAGE = "luggage_template"
TEMPLATE_FUN = "fun_template"

# 意图 → 模板类型映射（完整覆盖所有意图）
INTENT_TEMPLATE_MAP = {
    "query_weather": TEMPLATE_WEATHER,
    "query_traffic": TEMPLATE_TRAFFIC,
    "query_scenic": TEMPLATE_SCENIC,
    "query_food": TEMPLATE_FOOD,
    "query_hotel": TEMPLATE_HOTEL,
    "query_luggage": TEMPLATE_LUGGAGE,
    "query_fun": TEMPLATE_FUN,
    "book_ticket": TEMPLATE_SCENIC,
    "full_plan": TEMPLATE_PLAN,
    "optimize_plan": TEMPLATE_PLAN,
    "general_chat": None,
}

# 多任务组合 → 模板类型（基于任务集合的精确匹配）
MULTI_TASK_TEMPLATES = {
    # 天气 + 景点 → 组合模板
    frozenset([TASK_WEATHER_QUERY, TASK_SCENIC_QUERY]): TEMPLATE_COMBINED,
    # 天气 + 美食 → 组合模板
    frozenset([TASK_WEATHER_QUERY, TASK_FOOD_QUERY]): TEMPLATE_COMBINED,
    # 天气 + 交通 → 组合模板
    frozenset([TASK_WEATHER_QUERY, TASK_TRAFFIC_PLAN]): TEMPLATE_COMBINED,
    # 景点 + 美食 → 组合模板
    frozenset([TASK_SCENIC_QUERY, TASK_FOOD_QUERY]): TEMPLATE_COMBINED,
    # 景点 + 住宿 → 组合模板
    frozenset([TASK_SCENIC_QUERY, TASK_HOTEL_QUERY]): TEMPLATE_COMBINED,
    # 美食 + 住宿 → 组合模板
    frozenset([TASK_FOOD_QUERY, TASK_HOTEL_QUERY]): TEMPLATE_COMBINED,
    # 天气 + 景点 + 美食 → 行程模板
    frozenset([TASK_WEATHER_QUERY, TASK_SCENIC_QUERY, TASK_FOOD_QUERY]): TEMPLATE_PLAN,
    # 天气 + 交通 + 景点 → 行程模板
    frozenset([TASK_WEATHER_QUERY, TASK_TRAFFIC_PLAN, TASK_SCENIC_QUERY]): TEMPLATE_PLAN,
}

# 意图 → 中文显示名（用于模板上下文）
INTENT_DISPLAY_MAP = {
    "query_weather": "天气查询",
    "query_traffic": "交通规划",
    "query_scenic": "景点推荐",
    "query_food": "美食推荐",
    "query_hotel": "住宿推荐",
    "query_luggage": "行李穿搭",
    "query_fun": "趣玩活动",
    "book_ticket": "门票预订",
    "full_plan": "完整行程",
    "optimize_plan": "行程优化",
    "general_chat": "闲聊",
}

# 任务 → 中文显示名
TASK_DISPLAY_MAP = {
    TASK_WEATHER_QUERY: "天气查询",
    TASK_TRAFFIC_PLAN: "交通规划",
    TASK_SCENIC_QUERY: "景点查询",
    TASK_FOOD_QUERY: "美食查询",
    TASK_HOTEL_QUERY: "住宿查询",
    TASK_PLAN_GENERATION: "行程攻略",
}
