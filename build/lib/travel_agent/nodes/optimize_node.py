# -*- coding: utf-8 -*-
"""
行程优化组件

提供行程优化的数据模型和业务逻辑类，
供 main_app 多轮循环优化功能使用。
"""

from pydantic import BaseModel
from openai import OpenAI

from config import settings
from travel_agent.nodes.schedule_node import FinalTravelSchedule, convert_schedule_to_markdown
from travel_agent.prompt_templates.prompt_loader import render_template, OPTIMIZE_PROMPT
from travel_agent.state import IntentInfo

llm_client = OpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL
)
MODEL_NAME = settings.LLM_MODEL_NAME


# ========== 入参结构体 ==========
class OptimizeInput(BaseModel):
    """行程优化节点入参"""
    origin_schedule: FinalTravelSchedule
    full_resource: str
    optimize_demand: str
    intent_info: IntentInfo


# ========== 出参结构体 ==========
class OptimizeResult(BaseModel):
    """行程优化结果"""
    new_schedule: FinalTravelSchedule
    change_summary: list[str]


class OptimizeNode:
    """行程优化业务逻辑类"""

    def build_prompt(self, args: OptimizeInput) -> str:
        """构建优化提示词"""
        return render_template(
            OPTIMIZE_PROMPT,
            crowd=args.intent_info.crowd or "普通游客",
            optimize_demand=args.optimize_demand,
            city=args.intent_info.destination,
            origin_schedule_json=args.origin_schedule.model_dump_json(indent=2),
            full_resource=args.full_resource
        )

    def run(self, args: OptimizeInput) -> OptimizeResult:
        """调用 LLM 执行行程优化"""
        prompt = self.build_prompt(args)
        try:
            resp = llm_client.beta.chat.completions.parse(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                response_format=OptimizeResult
            )
            return resp.choices[0].message.parsed
        except Exception:
            resp = llm_client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt + "\n只返回纯JSON，无任何额外内容"}]
            )
            raw = resp.choices[0].message.content.strip()
            return OptimizeResult.model_validate_json(raw)
