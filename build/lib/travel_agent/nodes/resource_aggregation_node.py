# -*- coding: utf-8 -*-
"""
资源汇总节点

将所有工具调用结果汇总为统一的资源文本。
严格对应流程图中的"资源汇总"阶段。

输入：tool_results 字典
输出：aggregated_all_resource 统一文本
"""

from travel_agent.nodes import with_node_error_handler, NODE_RESOURCE_AGG
from travel_agent.state import TravelAgentState


# 工具名 → 中文名映射（用于汇总时的标题）
TOOL_NAME_ZH = {
    "weather": "天气信息",
    "traffic": "交通信息",
    "scenic": "景点推荐",
    "food": "美食推荐",
    "hotel": "住宿推荐",
    "luggage": "行李穿搭",
    "fun": "趣玩活动",
}


def _format_resource_section(tool_name: str, content: str) -> str:
    """
    格式化单个工具结果为资源段落

    Args:
        tool_name: 工具英文标识
        content: 工具返回内容

    Returns:
        格式化后的文本段落
    """
    zh_name = TOOL_NAME_ZH.get(tool_name, tool_name)
    return f"\n======{zh_name}======\n{content}"


@with_node_error_handler(NODE_RESOURCE_AGG)
def aggregate_resources(state: TravelAgentState) -> dict:
    """
    LangGraph 节点：资源汇总

    将 tool_results 中的所有工具结果汇总为统一的资源文本。
    同时合并历史缓存中的资源作为补充。

    Args:
        state: 包含 tool_results 的状态

    Returns:
        汇总后的资源文本
    """
    tool_results = state.tool_results

    if not tool_results:
        print("[资源汇总] 无工具结果可汇总")
        return {"aggregated_all_resource": ""}

    # 汇总所有工具结果
    parts = ["========出行基础资料========"]

    for tool_name, result in tool_results.items():
        if result:
            section = _format_resource_section(tool_name, result)
            parts.append(section)

    # 合并历史缓存作为补充
    destination = ""
    if state.extracted_params:
        destination = state.extracted_params.get("目的地", "")

    if destination:
        cached = state.get_cached_resource(destination)
        if cached:
            for cache_key, cache_value in cached.items():
                # 跳过当前已有的结果
                if cache_key not in tool_results and cache_key != "cached_tools":
                    section = _format_resource_section(cache_key.replace("_result", ""), cache_value)
                    parts.append(section)

    aggregated = "\n".join(parts)

    # 统一落盘到 SQLite
    if destination:
        state.flush_cache_to_disk(destination)

    print(f"[资源汇总] 完成，共 {len(parts) - 1} 个资源段落")
    print(f"  资源总长度: {len(aggregated)} 字符")

    return {
        "aggregated_all_resource": aggregated,
    }
