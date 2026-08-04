# -*- coding: utf-8 -*-
"""
输出渲染服务

提供 OutputRenderService 类和流式输出接口，
供前端通过 st.write_stream 调用实现流式渲染。
"""

import re
from typing import Optional

from openai import OpenAI

from config import settings
from travel_agent.nodes.constants import (
    TEMPLATE_WEATHER,
    TEMPLATE_TRAFFIC,
    TEMPLATE_SCENIC,
    TEMPLATE_FOOD,
    TEMPLATE_HOTEL,
    TEMPLATE_PLAN,
    TEMPLATE_COMBINED,
    TEMPLATE_LUGGAGE,
    TEMPLATE_FUN,
)
from travel_agent.prompt_templates.prompt_loader import render_by_type

llm_client = OpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL
)
MODEL_NAME = settings.LLM_MODEL_NAME

# 所有支持的模板类型
ALL_TEMPLATE_TYPES = {
    TEMPLATE_WEATHER,
    TEMPLATE_TRAFFIC,
    TEMPLATE_SCENIC,
    TEMPLATE_FOOD,
    TEMPLATE_HOTEL,
    TEMPLATE_PLAN,
    TEMPLATE_COMBINED,
    TEMPLATE_LUGGAGE,
    TEMPLATE_FUN,
}


def _postprocess_markdown_newlines(text: str) -> str:
    """
    后处理：将单换行转为双换行，确保 Streamlit markdown 正确渲染段落

    Streamlit 的 st.markdown() 遵循 Markdown 规范，
    单换行 \\n 不会渲染为换行（会合并到同一行），
    需要双换行 \\n\\n 才会分段。

    策略：
    1. 将所有 \\n 替换为 \\n\\n（单换行变段落分隔）
    2. 将3个以上连续换行压缩为2个（避免过多空行）

    Args:
        text: LLM 原始输出文本

    Returns:
        处理后的文本，所有换行均为双换行
    """
    if not text:
        return text
    # 单换行 → 双换行
    text = text.replace("\n", "\n\n")
    # 3+换行 → 2换行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


class OutputRenderService:
    """输出渲染业务逻辑类"""

    def _validate_and_prepare_context(self, template_type: str, context: dict) -> dict:
        """
        验证并准备模板上下文，处理缺失的变量

        Args:
            template_type: 模板类型
            context: 模板上下文

        Returns:
            处理后的安全上下文
        """
        safe_context = {}

        # 标准字段列表（适用于所有模板）
        standard_fields = [
            "city", "days", "crowd", "demand", "travel_time",
            "intent_name", "start_location", "destination",
            "season", "task_list", "all_resources",
        ]

        # 模板特定字段
        template_specific_fields = {
            TEMPLATE_WEATHER: ["weather_data"],
            TEMPLATE_TRAFFIC: ["traffic_data"],
            TEMPLATE_SCENIC: ["scenic_data"],
            TEMPLATE_FOOD: ["food_data"],
            TEMPLATE_HOTEL: ["hotel_data"],
            TEMPLATE_PLAN: [
                "weather_data", "traffic_data", "scenic_data",
                "food_data", "hotel_data", "all_resources", "task_list",
            ],
            TEMPLATE_COMBINED: [
                "weather_data", "traffic_data", "scenic_data",
                "food_data", "hotel_data", "all_resources", "task_list",
            ],
            TEMPLATE_LUGGAGE: ["weather_data", "season"],
            TEMPLATE_FUN: ["fun_data", "weather_data"],
        }

        # 确定需要的字段
        required_fields = list(standard_fields)
        if template_type in template_specific_fields:
            required_fields.extend(template_specific_fields[template_type])

        # 处理每个字段
        for field in required_fields:
            value = context.get(field, "")
            if value is None or value == "":
                safe_context[field] = "暂无相关信息"
            elif isinstance(value, list):
                safe_context[field] = "、".join(str(v) for v in value) if value else "暂无相关信息"
            else:
                safe_context[field] = str(value)

        # 添加所有原始上下文（供模板使用）
        for key, value in context.items():
            if key not in safe_context:
                if value is None or value == "":
                    safe_context[key] = "暂无相关信息"
                elif isinstance(value, list):
                    safe_context[key] = "、".join(str(v) for v in value) if value else "暂无相关信息"
                else:
                    safe_context[key] = str(value)

        return safe_context

    def _build_render_prompt(self, template_type: str, context: dict) -> str:
        """
        根据模板类型和上下文构建渲染 Prompt

        Args:
            template_type: 模板类型
            context: 模板上下文

        Returns:
            渲染后的 Prompt
        """
        # 验证模板类型
        if template_type not in ALL_TEMPLATE_TYPES:
            template_type = TEMPLATE_COMBINED

        # 验证并准备上下文
        safe_context = self._validate_and_prepare_context(template_type, context)

        # 移除与函数参数冲突的键
        safe_context.pop("template_type", None)

        try:
            return render_by_type(template_type, **safe_context)
        except Exception as e:
            print(f"[输出渲染] 模板渲染异常: {e}, 使用默认模板")
            return render_by_type(TEMPLATE_COMBINED, **safe_context)

    def render(self, template_type: str, context: dict) -> str:
        """
        使用 LLM 渲染最终输出文案（非流式）

        Args:
            template_type: 模板类型
            context: 模板上下文

        Returns:
            渲染后的文案
        """
        try:
            prompt = self._build_render_prompt(template_type, context)

            response = llm_client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=0.3,
            )
            raw_text = response.choices[0].message.content.strip()
            return _postprocess_markdown_newlines(raw_text)
        except Exception as e:
            print(f"[输出渲染] LLM调用异常: {e}")
            # 兜底：直接返回模板上下文的摘要
            return _postprocess_markdown_newlines(self._fallback_render(template_type, context))

    def render_stream(self, template_type: str, context: dict):
        """
        使用 LLM 流式渲染最终输出文案（generator）

        Args:
            template_type: 模板类型
            context: 模板上下文

        Yields:
            增量文本片段
        """
        try:
            prompt = self._build_render_prompt(template_type, context)

            stream = llm_client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=0.3,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"[输出渲染] LLM流式调用异常: {e}")
            fallback_text = self._fallback_render(template_type, context)
            yield fallback_text

    def _fallback_render(self, template_type: str, context: dict) -> str:
        """
        兜底渲染：当 LLM 调用失败时，直接格式化上下文返回

        Args:
            template_type: 模板类型
            context: 模板上下文

        Returns:
            格式化的兜底文案
        """
        city = context.get("city", "未知")
        intent_name = context.get("intent_name", "查询")

        lines = [f"✨ {city}{intent_name}结果", ""]

        # 添加相关数据
        data_fields = [
            ("weather_data", "🌤️ 天气信息"),
            ("traffic_data", "🚗 交通信息"),
            ("scenic_data", "🏞️ 景点推荐"),
            ("food_data", "🍜 美食推荐"),
            ("hotel_data", "🏨 住宿推荐"),
            ("all_resources", "📋 综合资源"),
            ("season", "🧥 穿搭建议"),
            ("fun_data", "🎉 趣玩活动"),
        ]

        for field_key, field_label in data_fields:
            data = context.get(field_key, "")
            if data and data != "暂无相关信息":
                lines.append(f"{field_label}：")
                # 截取前200字符
                display_data = data[:200] + "..." if len(data) > 200 else data
                lines.append(display_data)
                lines.append("")

        lines.append(f"#{city} #旅行助手")
        return "\n".join(lines)


# 全局单例
_output_service = OutputRenderService()


def stream_output(template_type: str, template_context: dict):
    """
    流式输出接口（供前端 st.write_stream 调用）

    Args:
        template_type: 模板类型
        template_context: 模板上下文

    Yields:
        增量文本片段
    """
    if not template_type or template_type not in ALL_TEMPLATE_TYPES:
        template_type = TEMPLATE_COMBINED

    yield from _output_service.render_stream(template_type, template_context or {})
