# -*- coding: utf-8 -*-
"""
Graph 构建器模块（重构版）

新流程拓扑（严格按用户流程图）：
  用户输入 → 意图解析 → 任务+参数提取 → 工具调用(并行) → 资源汇总 → 模板分析 → 输出结果

节点连接顺序：
  START → intent_node → task_param_node → tool_calls_node
  → resource_aggregation_node → template_analysis_node → output_node → END
  任意节点异常 → fallback_node → END
"""

from langgraph.graph import StateGraph, START, END

from travel_agent.graph.router import (
    route_after_intent,
    route_after_task_param,
    route_after_tool_calls,
    route_after_resource_agg,
    route_after_template_analysis,
)
from travel_agent.nodes.constants import (
    NODE_FALLBACK,
    NODE_INTENT,
    NODE_TASK_PARAM,
    NODE_TOOL_CALLS,
    NODE_RESOURCE_AGG,
    NODE_TEMPLATE_ANALYSIS,
)
from travel_agent.nodes.fallback_node import run_fallback
from travel_agent.nodes.intent_node import parse_intent
from travel_agent.nodes.task_param_node import extract_tasks_and_params
from travel_agent.nodes.tool_calls_node import execute_tool_calls
from travel_agent.nodes.resource_aggregation_node import aggregate_resources
from travel_agent.nodes.template_analysis_node import analyze_template
from travel_agent.state import TravelAgentState


def _register_nodes(graph: StateGraph) -> None:
    """按新流程注册所有业务节点（不含 output_node，输出渲染由前端流式处理）"""
    # Step 1: 意图解析
    graph.add_node(NODE_INTENT, parse_intent)
    # Step 2: 任务+参数提取
    graph.add_node(NODE_TASK_PARAM, extract_tasks_and_params)
    # Step 3: 工具调用（并行）
    graph.add_node(NODE_TOOL_CALLS, execute_tool_calls)
    # Step 4: 资源汇总
    graph.add_node(NODE_RESOURCE_AGG, aggregate_resources)
    # Step 5: 模板分析
    graph.add_node(NODE_TEMPLATE_ANALYSIS, analyze_template)
    # 异常兜底
    graph.add_node(NODE_FALLBACK, run_fallback)


def _configure_edges(graph: StateGraph) -> None:
    """按新流程配置所有边（结束于模板分析，输出渲染由前端流式处理）"""

    # ===== Step 0: 入口 =====
    graph.add_edge(START, NODE_INTENT)

    # ===== Step 1→2: 意图解析 → 任务+参数提取 =====
    graph.add_conditional_edges(
        NODE_INTENT,
        route_after_intent,
        {NODE_TASK_PARAM: NODE_TASK_PARAM, NODE_FALLBACK: NODE_FALLBACK}
    )

    # ===== Step 2→3: 任务+参数提取 → 工具调用 =====
    graph.add_conditional_edges(
        NODE_TASK_PARAM,
        route_after_task_param,
        {NODE_TOOL_CALLS: NODE_TOOL_CALLS, NODE_FALLBACK: NODE_FALLBACK}
    )

    # ===== Step 3→4: 工具调用 → 资源汇总 =====
    graph.add_conditional_edges(
        NODE_TOOL_CALLS,
        route_after_tool_calls,
        {NODE_RESOURCE_AGG: NODE_RESOURCE_AGG, NODE_FALLBACK: NODE_FALLBACK}
    )

    # ===== Step 4→5: 资源汇总 → 模板分析 =====
    graph.add_conditional_edges(
        NODE_RESOURCE_AGG,
        route_after_resource_agg,
        {NODE_TEMPLATE_ANALYSIS: NODE_TEMPLATE_ANALYSIS, NODE_FALLBACK: NODE_FALLBACK}
    )

    # ===== Step 5→END: 模板分析 → END（前端拿到 template_type 后自行流式渲染）=====
    graph.add_conditional_edges(
        NODE_TEMPLATE_ANALYSIS,
        route_after_template_analysis,
        [END, NODE_FALLBACK]
    )

    # ===== 异常兜底 =====
    graph.add_edge(NODE_FALLBACK, END)


def build_travel_agent_graph() -> StateGraph:
    """构建旅行 Agent LangGraph（新流程：7 阶段串行拓扑）"""
    graph = StateGraph(TravelAgentState)
    _register_nodes(graph)
    _configure_edges(graph)
    return graph


def get_compiled_graph():
    """获取编译后的 Graph 实例"""
    return build_travel_agent_graph().compile()


# LangGraph 平台部署入口：已编译的 Graph 实例
agent = get_compiled_graph()
