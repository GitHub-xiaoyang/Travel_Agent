# -*- coding: utf-8 -*-
"""
异常兜底节点

当任一节点发生异常时，生成友好的错误提示给用户。
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel

from travel_agent.nodes import with_node_error_handler, NODE_FALLBACK
from travel_agent.prompt_templates.prompt_loader import FALLBACK_PROMPT, render_template
from travel_agent.state import IntentInfo, TravelAgentState


class ErrorType(Enum):
    """错误类型枚举"""
    LLM_API_ERROR = "大模型接口异常"
    JSON_PARSE_FAILED = "JSON解析失败"
    TOKEN_OVER_LIMIT = "Token超出上限"
    RESOURCE_MISS = "资源缺失"
    BUSINESS_PARAM_ERROR = "入参字段缺失"
    UNKNOWN = "未知系统异常"


class FallbackInput(BaseModel):
    """兜底节点入参"""
    error_raw: str
    error_stack: str
    error_type: ErrorType
    current_step: str
    user_original_query: str
    intent_info: Optional[IntentInfo] = None


class FallbackResult(BaseModel):
    """兜底节点结果"""
    user_tip: str
    dev_log: str
    error_category: str
    fix_suggest: str


class FallbackNode:
    """异常兜底业务逻辑类"""

    def build_tip_content(self, args: FallbackInput) -> tuple[str, str]:
        """根据错误类型生成用户文案和修复建议"""
        err_type = args.error_type
        city = args.intent_info.destination if args.intent_info else ""

        mapping = {
            ErrorType.LLM_API_ERROR: (
                "调用AI规划接口失败，暂时无法生成旅行方案",
                "1. 检查网络；2. 确认大模型密钥正常；3. 稍后重试"
            ),
            ErrorType.JSON_PARSE_FAILED: (
                "行程数据解析出错，AI返回格式异常",
                "重新发起规划；若频繁报错，可简化出行需求"
            ),
            ErrorType.TOKEN_OVER_LIMIT: (
                "景点、美食参考内容太多超出长度限制",
                "缩短出行天数，或精简游玩需求"
            ),
            ErrorType.RESOURCE_MISS: (
                f"{city}的景点、天气、美食资源获取不全",
                "更换目的地，或明确补充出行时间"
            ),
            ErrorType.BUSINESS_PARAM_ERROR: (
                "出行关键信息缺失（城市/天数/人群不全）",
                "重新描述需求，明确写清：去哪、玩几天、出行人群"
            ),
        }

        if err_type in mapping:
            return mapping[err_type]
        return "行程服务出现未知故障", "重试一次；持续报错可反馈技术人员"

    def run(self, args: FallbackInput) -> FallbackResult:
        """执行兜底处理"""
        user_tip, fix_suggest = self.build_tip_content(args)
        final_user_text = render_template(
            FALLBACK_PROMPT,
            current_step=args.current_step,
            error_type_desc=args.error_type.value,
            user_tip=user_tip,
            fix_suggest=fix_suggest
        )
        return FallbackResult(
            user_tip=final_user_text.strip(),
            dev_log=f"【报错节点】{args.current_step}\n【原始报错】{args.error_raw}\n【完整堆栈】\n{args.error_stack}",
            error_category=args.error_type.value,
            fix_suggest=fix_suggest
        )


def judge_error_type(exc: Exception, err_msg: str) -> ErrorType:
    """根据报错内容自动归类异常类型"""
    err_lower = err_msg.lower()

    if any(k in err_lower for k in ["401", "api key", "429", "rate limit", "timeout", "connect"]):
        return ErrorType.LLM_API_ERROR
    if "json" in err_lower and ("parse" in err_lower or "validate" in err_lower):
        return ErrorType.JSON_PARSE_FAILED
    if "token" in err_lower and ("exceed" in err_lower or "max token" in err_lower):
        return ErrorType.TOKEN_OVER_LIMIT
    if "resource" in err_lower or "景点" in err_lower:
        return ErrorType.RESOURCE_MISS
    if "keyerror" in err_lower or "missing" in err_lower or "travel_days" in err_lower:
        return ErrorType.BUSINESS_PARAM_ERROR
    return ErrorType.UNKNOWN


# 全局单例
_fallback_service = FallbackNode()


@with_node_error_handler(NODE_FALLBACK)
def run_fallback(state: TravelAgentState) -> dict:
    """
    LangGraph 节点：异常兜底处理

    当节点异常或任务为空时被调用。
    无实际异常时生成友好提示而非"未知系统异常"。
    """
    # 无实际异常（如任务为空被路由到 fallback）
    if not state.has_exception and not state.error_msg:
        city = state.intent_info.destination if state.intent_info else ""
        tip = "抱歉，暂时无法理解您的需求\n\n"
        tip += "💡您可以尝试这样描述：\n"
        tip += '- "查询成都天气"\n'
        tip += '- "我想去杭州玩3天"\n'
        tip += '- "成都到北京交通路线"\n'
        if city:
            tip += f"\n已识别目的地：{city}，请补充出行天数等信息"
        return {
            "final_travel_document": tip,
            "dev_error_log": "路由到fallback但无实际异常（可能任务提取为空）",
            "is_fallback": True,
        }

    err_type = judge_error_type(Exception(), state.error_msg)
    fallback_input = FallbackInput(
        error_raw=state.error_msg,
        error_stack=state.error_trace,
        error_type=err_type,
        current_step=state.error_step,
        user_original_query=state.user_query_origin or state.user_input,
        intent_info=state.intent_info
    )
    result = _fallback_service.run(fallback_input)

    # 只返回需更新的字段（dict）
    return {
        "final_travel_document": result.user_tip,
        "dev_error_log": result.dev_log,
        "is_fallback": True,
    }