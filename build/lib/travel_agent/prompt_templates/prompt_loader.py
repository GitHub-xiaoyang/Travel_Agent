# -*- coding: utf-8 -*-
"""
Prompt 模板加载工具

统一管理 prompt_templates/ 目录下的 .txt 模板文件，
提供带变量替换的模板渲染能力。

模板变量使用 Python str.format 占位符语法，如：{user_query}
"""

from pathlib import Path
from typing import Any

# prompt_templates 目录路径（基于本文件所在位置）
TEMPLATE_DIR = Path(__file__).parent.resolve()

# 模板文件名常量 — 新增模板时在此注册
INTENT_PROMPT = "intent_prompt.txt"
SCHEDULE_PROMPT = "schedule_prompt.txt"
OPTIMIZE_PROMPT = "optimize_prompt.txt"
FALLBACK_PROMPT = "fallback_prompt.txt"
TOOL_REPLY_PROMPT = "tool_reply_prompt.txt"

# ========== 意图搭配输出模板（新流程） ==========
WEATHER_TEMPLATE = "weather_template.txt"
TRAFFIC_TEMPLATE = "traffic_template.txt"
SCENIC_TEMPLATE = "scenic_template.txt"
FOOD_TEMPLATE = "food_template.txt"
HOTEL_TEMPLATE = "hotel_template.txt"
PLAN_TEMPLATE = "plan_template.txt"
COMBINED_TEMPLATE = "combined_template.txt"
LUGGAGE_TEMPLATE = "luggage_template.txt"
FUN_TEMPLATE = "fun_template.txt"

# 模板类型 → 文件名映射（完整覆盖所有意图）
TEMPLATE_TYPE_MAP = {
    "weather_template": WEATHER_TEMPLATE,
    "traffic_template": TRAFFIC_TEMPLATE,
    "scenic_template": SCENIC_TEMPLATE,
    "food_template": FOOD_TEMPLATE,
    "hotel_template": HOTEL_TEMPLATE,
    "plan_template": PLAN_TEMPLATE,
    "combined_template": COMBINED_TEMPLATE,
    "luggage_template": LUGGAGE_TEMPLATE,
    "fun_template": FUN_TEMPLATE,
}

# 模板缓存，避免重复磁盘IO
_template_cache: dict[str, str] = {}


def load_template(template_name: str) -> str:
    """
    加载指定名称的 prompt 模板文件（带缓存）

    Args:
        template_name: 模板文件名，使用本模块常量（如 INTENT_PROMPT）

    Returns:
        模板原始文本内容

    Raises:
        FileNotFoundError: 模板文件不存在
    """
    if template_name in _template_cache:
        return _template_cache[template_name]

    file_path = TEMPLATE_DIR / template_name
    if not file_path.exists():
        raise FileNotFoundError(
            f"Prompt 模板未找到: {file_path}，"
            f"请确认 prompt_templates/{template_name} 文件存在"
        )

    content = file_path.read_text(encoding="utf-8").strip()
    _template_cache[template_name] = content
    return content


def render_template(template_name: str, **kwargs: Any) -> str:
    """
    加载模板并使用变量渲染

    Args:
        template_name: 模板文件名
        **kwargs: 模板中的 {变量名} 及对应值

    Returns:
        渲染后的完整 prompt 字符串

    Example:
        >>> render_template(INTENT_PROMPT, user_query="我想去成都")
        "你是出行意图抽取专家..."
    """
    template = load_template(template_name)
    return template.format(**kwargs)


def render_by_type(template_type: str, **kwargs: Any) -> str:
    """
    按模板类型渲染（意图搭配输出模板专用）

    Args:
        template_type: 模板类型（如 "weather_template"）
        **kwargs: 模板中的变量及对应值

    Returns:
        渲染后的完整 prompt 字符串
    """
    template_file = TEMPLATE_TYPE_MAP.get(template_type)
    if not template_file:
        # 使用默认模板
        template_file = COMBINED_TEMPLATE

    # 处理空值，替换为占位文字
    safe_kwargs = {}
    for key, value in kwargs.items():
        if value is None or value == "":
            safe_kwargs[key] = "暂无相关信息"
        else:
            safe_kwargs[key] = str(value)

    return render_template(template_file, **safe_kwargs)


def reload_template(template_name: str) -> str:
    """
    强制重新加载模板（忽略缓存），常用于热更新场景

    Args:
        template_name: 模板文件名

    Returns:
        重新加载后的模板内容
    """
    file_path = TEMPLATE_DIR / template_name
    content = file_path.read_text(encoding="utf-8").strip()
    _template_cache[template_name] = content
    return content


def clear_cache() -> None:
    """清空全部模板缓存"""
    _template_cache.clear()
