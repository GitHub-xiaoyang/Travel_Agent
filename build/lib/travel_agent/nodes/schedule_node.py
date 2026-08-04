# -*- coding: utf-8 -*-
"""
行程数据模型与转换工具

提供 FinalTravelSchedule 数据模型和 Markdown 转换函数，
供 optimize_node 和 main_app 复用。
"""

from pydantic import BaseModel, Field


class TimeBlock(BaseModel):
    """时间段行程块（所有字段均有默认值，兼容 LLM 字段缺失）"""
    model_config = {"populate_by_name": True, "extra": "ignore"}

    time_period: str = Field(default="", alias="time", description="时间段")
    location: str = Field(default="", description="地点")
    activity_detail: str = Field(default="", alias="activity", description="游玩内容")
    traffic_method: str = Field(default="", alias="traffic", description="交通方式")
    note: str = Field(default="", description="备注")


class DailySchedule(BaseModel):
    """每日行程（所有字段均有默认值，兼容 LLM 字段缺失）"""
    model_config = {"populate_by_name": True, "extra": "ignore"}

    day_no: int = Field(default=1, alias="day", description="第几天")
    weather_tip: str = Field(default="", alias="weather", description="天气提示")
    time_arrange: list[TimeBlock] = Field(default_factory=list, alias="schedule", description="时间安排")
    dine_recommend: list[str] = Field(default_factory=list, alias="food", description="推荐美食")
    day_tips: str = Field(default="", alias="tips", description="当日贴士")


class FinalTravelSchedule(BaseModel):
    """完整行程（所有字段均有默认值，兼容 LLM 字段缺失）"""
    model_config = {"populate_by_name": True, "extra": "ignore"}

    overall_intro: str = Field(default="", alias="intro", description="行程总览")
    daily_plan_list: list[DailySchedule] = Field(default_factory=list, alias="daily_plan", description="每日行程")
    style_markdown: str = Field(default="", description="小红书风格完整文案，由 LLM 直接生成")


def convert_schedule_to_markdown(schedule: FinalTravelSchedule) -> str:
    """将结构化行程转为 Markdown 文本"""
    md_lines = [f"# {schedule.overall_intro}", ""]
    for day in schedule.daily_plan_list:
        md_lines.append(f"## Day{day.day_no}")
        md_lines.append(f"当日天气适配：{day.weather_tip}")
        md_lines.append("| 时间段 | 地点 | 游玩内容 | 交通 | 备注 |")
        md_lines.append("|--------|------|----------|------|------|")
        for block in day.time_arrange:
            md_lines.append(
                f"| {block.time_period} | {block.location} | {block.activity_detail} | {block.traffic_method} | {block.note} |"
            )
        md_lines.append(f"\n🍚推荐美食：{'、'.join(day.dine_recommend)}")
        md_lines.append(f"💡当日贴士：{day.day_tips}")
        md_lines.append("\n---\n")
    return "\n".join(md_lines)
