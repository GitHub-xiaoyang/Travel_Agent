from travel_agent.graph.router import (
    route_after_intent,
    route_after_task_param,
    route_after_tool_calls,
    route_after_resource_agg,
    route_after_template_analysis,
)
from travel_agent.graph.builder import build_travel_agent_graph, get_compiled_graph
from travel_agent.graph.mermaid import generate_mermaid, save_mermaid_html, get_graph_summary

from travel_agent.errors import (
    ErrorLevel,
    TravelAgentError,
    LLMError, LLMAPIError, LLMRateLimitError, LLMTimeoutError, LLMParseError,
    ToolError, ToolTimeoutError, ToolRateLimitError,
    BusinessError, InputValidationError, ResourceNotFoundError,
    CacheError, classify_exception,
)
from travel_agent.retry import (
    with_llm_retry, with_tool_retry, with_retry,
)

__all__ = [
    # 路由函数（新流程）
    "route_after_intent",
    "route_after_task_param",
    "route_after_tool_calls",
    "route_after_resource_agg",
    "route_after_template_analysis",
    # Graph 构建
    "build_travel_agent_graph",
    "get_compiled_graph",
    # 可视化
    "generate_mermaid",
    "save_mermaid_html",
    "get_graph_summary",
    # 异常分级
    "ErrorLevel",
    "TravelAgentError",
    "LLMError", "LLMAPIError", "LLMRateLimitError", "LLMTimeoutError", "LLMParseError",
    "ToolError", "ToolTimeoutError", "ToolRateLimitError",
    "BusinessError", "InputValidationError", "ResourceNotFoundError",
    "CacheError", "classify_exception",
    # 重试
    "with_llm_retry", "with_tool_retry", "with_retry",
]


def main() -> None:
    """CLI 入口占位"""
    print("Hello from travel-agent!")
    print("启动 Streamlit 前端请运行: streamlit run streamlit_app.py")
