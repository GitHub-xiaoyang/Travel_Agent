# -*- coding: utf-8 -*-
"""
全局Graph状态定义 — TravelAgentState

本模块定义 LangGraph 全链路流转所需的统一数据载体。
支持并行工具节点、聊天历史、资源缓存等新特性。
"""

from pydantic import BaseModel, Field
from typing import Any, Optional, Annotated
from operator import add


# ========== 自定义 Reducer（用于并行节点合并） ==========
def merge_resource_cache(old: dict, new: dict) -> dict:
    """
    合并资源缓存字典 reducer

    并行工具节点各自更新不同城市/不同资源 key，
    使用本 reducer 深度合并避免并发更新冲突。

    Args:
        old: 当前 state 中的缓存 {城市: {资源key: 资源value}}
        new: 节点返回的缓存更新 {城市: {资源key: 资源value}}

    Returns:
        合并后的完整缓存字典
    """
    if not old:
        return dict(new or {})
    if not new:
        return dict(old)
    result = dict(old)
    for city, resources in new.items():
        if city in result:
            result[city] = {**result[city], **resources}
        else:
            result[city] = dict(resources)
    return result


def merge_bool_or(old: bool, new: bool) -> bool:
    """
    布尔或合并 reducer

    并行节点中任意一个返回 True，结果即为 True。
    用于 has_exception 等字段，避免并行异常时并发更新冲突。

    Args:
        old: 当前 state 中的布尔值
        new: 节点返回的布尔值

    Returns:
        两者逻辑或的结果
    """
    return bool(old) or bool(new)


def merge_str_concat(old: str, new: str) -> str:
    """
    字符串拼接合并 reducer

    将并行节点返回的多个错误信息拼接在一起（换行分隔），
    用于 error_msg、error_trace、error_step 等异常字段，
    避免并行异常时并发更新冲突。

    Args:
        old: 当前 state 中的字符串
        new: 节点返回的字符串

    Returns:
        拼接后的字符串（空值自动跳过）
    """
    if not old and not new:
        return ""
    if not old:
        return str(new)
    if not new:
        return str(old)
    # 避免重复拼接相同内容
    new_s = str(new)
    if new_s in str(old):
        return str(old)
    return f"{old}\n---\n{new_s}"


def merge_str_first(old: str, new: str) -> str:
    """
    字符串保留首个非空值 reducer

    用于 user_query_origin 等字段：并行节点返回的是同一个值，
    只需保留第一个非空值即可，避免并发更新冲突。

    Args:
        old: 当前 state 中的字符串
        new: 节点返回的字符串

    Returns:
        第一个非空字符串（都为空则返回空串）
    """
    if old:
        return old
    return str(new) if new else ""


# ========== 意图信息结构化对象 ==========
class IntentInfo(BaseModel):
    """用户意图解析结果"""

    travel_type: str = Field("", description="出行类型：旅游/商务出差/探亲访友/公司团建/户外徒步/周边短途")
    crowd: str = Field("", description="出行人群：单人出行/情侣/亲子带小孩/带老人/朋友多人/全家老小")
    core_demand: str = Field("", description="用户核心诉求")
    destination: str = Field("", description="目的地城市")
    travel_days: str = Field("", description="出行天数")
    travel_time: str = Field("", description="出行时间段")
    current_location: str = Field("", description="用户当前所在城市（通过定位获取）")
    current_location_detail: str = Field("", description="用户当前详细地址（省市区街道，通过精准定位获取）")
    current_location_lng: str = Field("", description="用户当前经度（精准定位获取，用于交通路线距离计算）")
    current_location_lat: str = Field("", description="用户当前纬度（精准定位获取，用于交通路线距离计算）")
    required_tools: list[str] = Field(default_factory=list, description="需要调用的工具列表")

    def get_city(self) -> str:
        return self.destination or self.travel_type

    def get_days(self) -> str:
        return self.travel_days

    def to_dict(self) -> dict:
        data = self.model_dump()
        data["city"] = self.destination
        return data


# ========== 并行工具结果 ==========
class ToolResult(BaseModel):
    """单个工具节点的结果"""
    tool_name: str = Field("", description="工具名称")
    content: str = Field("", description="工具返回内容")
    success: bool = Field(True, description="是否成功")


class TravelAgentState(BaseModel):
    """旅行Agent全流程状态数据载体"""

    # ========== 用户输入区 ==========
    user_input: str = Field("", description="用户旅行原始话术")

    # ========== 聊天历史（使用 Annotated 支持并行追加） ==========
    chat_history: Annotated[list[dict], add] = Field(default_factory=list, description="对话历史")

    # ========== 意图解析区 ==========
    intent_info: Optional[IntentInfo] = Field(default=None, description="结构化意图")

    # ========== 任务+参数提取区（新流程） ==========
    extracted_tasks: list[str] = Field(default_factory=list, description="从意图提取的任务列表")
    extracted_params: dict[str, Any] = Field(default_factory=dict, description="从意图提取的参数字典")

    # ========== 工具结果区（统一存放所有工具调用结果） ==========
    tool_results: dict[str, str] = Field(default_factory=dict, description="各工具调用结果 {tool_name: result}")

    # ========== 资源缓存（按目的地隔离，Annotated 支持并行节点合并） ==========
    history_resource_cache: Annotated[dict[str, dict[str, Any]], merge_resource_cache] = Field(
        default_factory=dict, description="按目的地缓存历史资源，避免重复调用"
    )

    # ========== 资源聚合区（资源汇总节点写入） ==========
    aggregated_all_resource: str = Field("", description="汇总后的完整资源文本")

    # ========== 模板分析区（模板分析节点写入） ==========
    selected_template: str = Field("", description="选中的输出模板类型")
    template_context: dict[str, Any] = Field(default_factory=dict, description="模板上下文（供模板渲染使用）")

    # ========== 行程生成区（供 plan_template 使用） ==========
    travel_schedule_struct: Any = Field(None, description="结构化行程对象")
    travel_schedule_markdown: str = Field("", description="行程Markdown预览")

    # ========== 优化调整区 ==========
    user_optimize_require: str = Field("", description="用户优化指令")
    optimize_change_list: list[str] = Field(default_factory=list, description="优化改动明细")
    is_optimized: bool = Field(False, description="行程是否经过优化")

    # ========== 输出渲染区 ==========
    final_travel_document: str = Field("", description="最终完整Markdown文案")

    # ========== 异常兜底层（Annotated 支持并行节点异常合并，避免并发更新冲突） ==========
    has_exception: Annotated[bool, merge_bool_or] = Field(False, description="链路是否异常")
    error_msg: Annotated[str, merge_str_concat] = Field("", description="异常简要信息")
    error_trace: Annotated[str, merge_str_concat] = Field("", description="异常完整堆栈")
    error_step: Annotated[str, merge_str_concat] = Field("", description="异常节点名称")
    user_query_origin: Annotated[str, merge_str_first] = Field("", description="用户原始查询")
    is_fallback: bool = Field(False, description="是否兜底状态")
    dev_error_log: str = Field("", description="开发调试日志")

    def get_cached_resource(self, city: str) -> Optional[dict[str, Any]]:
        """获取指定城市的缓存资源（优先内存，回退磁盘）"""
        if city in self.history_resource_cache:
            return self.history_resource_cache[city]
        # 回退到磁盘加载
        from travel_agent.cache_manager import get_city_cache
        disk = get_city_cache(city)
        if disk:
            self.history_resource_cache[city] = disk
        return disk

    def set_cached_resource(self, city: str, resources: dict[str, str]) -> None:
        """
        设置指定城市的缓存资源（仅更新内存）

        注意：并行节点只更新内存，避免并发写 SQLite 冲突。
        磁盘落盘由串行的 resource_aggregation_node 统一执行。

        Args:
            city: 城市名
            resources: 该城市的资源字典
        """
        if city in self.history_resource_cache:
            self.history_resource_cache[city].update(resources)
        else:
            self.history_resource_cache[city] = resources

    def flush_cache_to_disk(self, city: str) -> None:
        """
        将指定城市的内存缓存统一落盘到 SQLite（串行调用，避免并发冲突）

        供 resource_aggregation_node 在合并所有并行节点结果后统一调用。

        Args:
            city: 城市名
        """
        if city not in self.history_resource_cache:
            return
        from travel_agent.cache_manager import update_city_cache
        update_city_cache(city, self.history_resource_cache[city])

    def is_city_cached(self, city: str) -> bool:
        """检查城市是否已缓存（内存或磁盘）"""
        if city in self.history_resource_cache:
            return True
        from travel_agent.cache_manager import get_city_cache
        return get_city_cache(city) is not None

    def load_disk_cache(self) -> None:
        """从 SQLite 加载完整缓存到内存（启动时调用）"""
        from travel_agent.cache_manager import load_all_cache
        disk = load_all_cache()
        for city, resources in disk.items():
            if city not in self.history_resource_cache:
                self.history_resource_cache[city] = resources