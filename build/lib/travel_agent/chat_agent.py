
# -*- coding: utf-8 -*-
"""
ChatAgent — 对话式旅行助手

架构说明：
    本模块作为 LangGraph 全链路的前置对话路由层，
    负责将用户自然语言输入分类为具体意图，
    然后调用对应工具或触发完整行程规划流程。

支持的意图动作：
    - query_weather    : 查询天气
    - query_scenic     : 查询景点
    - query_food       : 查询美食
    - query_hotel      : 查询酒店
    - query_traffic    : 查询交通路线
    - query_luggage    : 查询行李穿搭
    - query_fun        : 查询趣玩
    - book_ticket      : 预订门票
    - full_plan        : 启动完整行程规划
    - optimize_plan    : 行程优化调整
    - general_chat     : 通用闲聊/追问
"""

import json
import re
import traceback
from typing import Optional

from pydantic import BaseModel, Field
from openai import OpenAI

from config import settings
from travel_agent.conversation_memory import ConversationMemory
from travel_agent.cache_manager import get_qa_cache, save_qa_cache
from travel_agent.nodes.output_node import OutputRenderService
from travel_agent.nodes.constants import (
    ACTION_LABELS,
    CITY_REQUIRED_ACTIONS,
    INTENT_KEYWORDS as SHARED_INTENT_KEYWORDS,
    CITY_NAMES,
    check_degrade,
    TEMPLATE_WEATHER,
    TEMPLATE_SCENIC,
    TEMPLATE_FOOD,
    TEMPLATE_HOTEL,
    TEMPLATE_TRAFFIC,
    TEMPLATE_LUGGAGE,
    TEMPLATE_FUN,
)


# ========== 1. 意图分类 Schema ==========
class ChatIntent(BaseModel):
    """用户聊天意图分类结果"""

    model_config = {"populate_by_name": True, "extra": "ignore"}

    action: str = Field(
        alias="intent",
        description=(
            "意图动作，可选值："
            "query_weather/query_scenic/query_food/query_hotel/"
            "query_traffic/query_luggage/query_fun/book_ticket/"
            "full_plan/optimize_plan/general_chat"
        )
    )
    confidence: float = Field(default=0.8, description="置信度 0-1")
    city: str = Field(default="", description="提取的城市名，无则空字符串")
    days: str = Field(default="", description="提取的天数，无则空字符串")
    crowd: str = Field(default="", description="提取的人群，无则空字符串")
    query: str = Field(default="", description="提取的核心查询/需求描述")
    current_location: str = Field(default="", description="用户当前所在城市（通过定位获取），无则空字符串")


# ========== 2. ChatAgent 主体 ==========
class ChatAgent:
    """对话式旅行助手

    职责：
        1. 轻量意图分类（规则引擎 → LLM 兜底）
        2. 工具分发（意图 → 工具调用）
        3. 会话上下文累积
        4. 完整行程规划触发

    使用：
        agent = ChatAgent()
        response = agent.chat(user_input, context_dict)

    共享常量：ACTION_LABELS / CITY_REQUIRED_ACTIONS / INTENT_KEYWORDS / check_degrade
    均从 nodes.constants 导入，与 intent_node.py 保持一致。
    """

    # 兼容旧代码的类属性引用（指向共享常量）
    ACTION_LABELS = ACTION_LABELS
    CITY_REQUIRED_ACTIONS = CITY_REQUIRED_ACTIONS

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL
        )
        self.model_name = settings.LLM_MODEL_NAME
        self._classifier_prompt = self._build_classifier_prompt()
        # 会话记忆管理器（滑动窗口 + 摘要压缩）
        self.memory = ConversationMemory(window_size=10, keep_recent=4)

    # ---------- 规则引擎兜底 ----------

    @classmethod
    def _rule_fallback(cls, user_input: str) -> ChatIntent | None:
        """
        规则引擎兜底：当 LLM 分类为 general_chat 但输入含明确工具意图时覆盖

        使用 SHARED_INTENT_KEYWORDS（来自 constants.py）与 intent_node.py 保持一致。

        Args:
            user_input: 用户输入文本

        Returns:
            ChatIntent 或 None（无需覆盖）
        """
        text = user_input.lower()
        best_intent = ""
        best_score = 0

        for intent, keywords in SHARED_INTENT_KEYWORDS.items():
            hit = sum(1 for kw in keywords if kw.lower() in text)
            if hit > best_score:
                best_score = hit
                best_intent = intent

        if best_score == 0:
            return None

        # 提取城市
        city = ""
        for c in CITY_NAMES:
            if c.lower() in text:
                city = c
                break

        # 提取天数
        days = ""
        for pat in [r"(\d+)\s*天", r"(\d+)\s*日", r"(\d+)\s*晚"]:
            m = re.search(pat, user_input)
            if m:
                days = m.group(1)
                break

        return ChatIntent(
            action=best_intent,
            city=city,
            days=days,
            crowd="",
            query="",
            current_location="",
        )

    def _render_tool_reply(
        self,
        template_type: str,
        tool_result: str,
        city: str = "",
        days: str = "",
        **extra_context
    ) -> str:
        """使用专用模板渲染工具查询结果，替代通用 tool_reply_prompt

        Args:
            template_type: 模板类型常量（如 TEMPLATE_HOTEL）
            tool_result: 工具返回的原始文本
            city: 当前城市上下文
            days: 当前天数上下文
            **extra_context: 模板额外需要的字段（如 traffic 的 start_location/destination）

        Returns:
            按专用模板渲染后的文案；渲染失败时返回原始工具结果
        """
        if not tool_result:
            return tool_result
        try:
            context = {
                "city": city or "未指定",
                "days": days or "3",
                "crowd": "",
            }
            # 根据模板类型注入对应的工具数据字段
            if template_type == TEMPLATE_WEATHER:
                context["weather_data"] = tool_result
            elif template_type == TEMPLATE_SCENIC:
                context["scenic_data"] = tool_result
            elif template_type == TEMPLATE_FOOD:
                context["food_data"] = tool_result
            elif template_type == TEMPLATE_HOTEL:
                context["hotel_data"] = tool_result
            elif template_type == TEMPLATE_TRAFFIC:
                context["traffic_data"] = tool_result
            elif template_type == TEMPLATE_LUGGAGE:
                # plan_luggage 返回的文本已包含天气+穿搭综合信息
                context["weather_data"] = tool_result
                context["season"] = self._infer_season()
            elif template_type == TEMPLATE_FUN:
                context["fun_data"] = tool_result
                context["weather_data"] = ""
            context.update(extra_context)
            return OutputRenderService().render(template_type, context)
        except Exception:
            return tool_result

    @staticmethod
    def _infer_season() -> str:
        """根据当前月份推断季节描述（用于行李穿搭模板）"""
        from datetime import datetime
        month = datetime.now().month
        if month in (3, 4, 5):
            return "春季（3-5月）：建议轻薄外套+长袖"
        elif month in (6, 7, 8):
            return "夏季（6-8月）：建议短袖+防晒用品"
        elif month in (9, 10, 11):
            return "秋季（9-11月）：建议长袖+薄外套"
        else:
            return "冬季（12-2月）：建议羽绒服+保暖内衣"

    # ---------- 问答缓存辅助方法 ----------

    _CACHEABLE_INTENTS = {
        "query_weather", "query_scenic", "query_food", "query_hotel",
        "query_traffic", "query_luggage", "query_fun",
    }

    @staticmethod
    def _get_cache_city(intent: ChatIntent, context: dict) -> str:
        """从意图和上下文中提取用于缓存关联的城市名"""
        return (
            intent.city
            or context.get("city", "")
            or context.get("current_city", "")
            or context.get("current_location", "")
            or ""
        )

    def _try_get_cached_reply(
        self, user_input: str, intent: ChatIntent, context: dict
    ) -> Optional[str]:
        """
        尝试命中问答缓存

        仅对可缓存的工具类意图生效；general_chat/full_plan 等不缓存。
        """
        if intent.action not in self._CACHEABLE_INTENTS:
            return None
        city = self._get_cache_city(intent, context)
        return get_qa_cache(user_input, city or None, intent.action)

    def _save_reply_to_cache(
        self, user_input: str, intent: ChatIntent, context: dict, answer: str
    ) -> None:
        """将最终回复保存到问答缓存"""
        if intent.action not in self._CACHEABLE_INTENTS or not answer:
            return
        city = self._get_cache_city(intent, context)
        save_qa_cache(user_input, city or None, intent.action, answer)

    # ---------- 初始化私有方法 ----------

    @staticmethod
    def _build_classifier_prompt() -> str:
        """构建意图分类提示词"""
        return """你是旅行助手的意图分类器。根据用户输入，判断最匹配的动作类型，并提取关键参数。

必须返回如下 JSON 格式（字段名完全一致）：
{
  "action": "动作类型",
  "city": "城市名",
  "days": "天数",
  "crowd": "人群",
  "query": "需求摘要",
  "current_location": "当前所在城市"
}

action 可选值：
- query_weather：查询某个城市的天气、气温、天气预报
- query_scenic：查询某个城市的景点、景区、公园
- query_food：查询某个城市的美食、餐厅
- query_hotel：查询某个城市的酒店、民宿
- query_traffic：查询交通路线、地铁、打车、公交
- query_luggage：查询行李穿搭、打包建议
- query_fun：查询某个城市的趣玩活动
- book_ticket：预订某个城市的门票
- full_plan：规划行程、安排旅行、制定攻略、几天行程、帮我规划
- optimize_plan：优化行程、调整行程
- general_chat：普通聊天、打招呼、常识问题、非工具类问题

分类规则：
1. 常识性问题、地理知识、闲聊，即使提到地点，也归为 general_chat
2. query_weather 无需城市名即可归类（用户问天气如"最近天气""气温"等均归为 query_weather，城市缺失时后续用定位兜底）
3. query_scenic/query_food/query_hotel/query_fun 尽量包含城市名，无城市名时也可归类
4. 用户提到"规划行程""帮我安排""攻略"等词时归为 full_plan

参数提取规则：
- city：从用户输入中提取城市名（如"上海""杭州""成都"），无则填空字符串
- days：提取天数数字（如"3""5"），无则填空字符串
- crowd：提取人群（如"亲子""情侣""朋友"），无则填空字符串
- query：提取除城市名之外的**核心搜索关键词**，用于 POI 搜索。必须去除"查询""查""找""推荐""有哪些""有什么""一下""帮我""请问"等通用词。例如用户说"查询成都酒店"应提取"酒店"；"成都火锅推荐"应提取"火锅"；无额外关键词时填空字符串
- current_location：用户当前所在城市（如用户说"我在上海"或"我人在杭州"），无则填空字符串

只输出纯 JSON，不要 markdown 代码块标记。"""

    # ---------- 搜索关键词清洗 ----------

    @staticmethod
    def _clean_search_keyword(query: str, city: str, action: str) -> str:
        """
        从 query 中提取干净的 POI 搜索关键词

        去除城市名、通用查询词和标点，保留真正的搜索关键词。
        清洗后为空时返回对应意图的默认关键词。

        Args:
            query: LLM 提取的 query 或用户原始输入
            city: 已提取的城市名，用于从 query 中剔除
            action: 意图动作，决定停用词和默认词

        Returns:
            清洗后的搜索关键词
        """
        if not query:
            query = ""

        defaults = {
            "query_hotel": "酒店",
            "query_scenic": "景点",
            "query_food": "美食",
            "query_fun": "休闲娱乐",
        }

        # 各意图通用停用词
        stopwords = {
            "query_hotel": [
                "查询", "查", "找", "搜索", "酒店", "住宿",
                "推荐", "有哪些", "有什么", "一下", "帮我", "给我", "我想", "知道",
                "请问", "的", "了", "吗", "呢", "吧", "啊",
            ],
            "query_scenic": [
                "查询", "查", "找", "搜索", "景点", "景区", "风景", "旅游", "游玩",
                "推荐", "有哪些", "有什么", "一下", "帮我", "给我", "我想", "知道",
                "请问", "的", "了", "吗", "呢", "吧", "啊",
            ],
            "query_food": [
                "查询", "查", "找", "搜索", "美食", "餐厅", "好吃的", "吃饭", "吃",
                "推荐", "有哪些", "有什么", "一下", "帮我", "给我", "我想", "知道",
                "请问", "的", "了", "吗", "呢", "吧", "啊",
            ],
            "query_fun": [
                "查询", "查", "找", "搜索", "趣玩", "活动", "好玩", "玩",
                "推荐", "有哪些", "有什么", "一下", "帮我", "给我", "我想", "知道",
                "请问", "的", "了", "吗", "呢", "吧", "啊",
            ],
        }

        text = query.strip()

        # 去除城市名
        if city and city in text:
            text = text.replace(city, "")

        # 去除停用词
        for sw in stopwords.get(action, []):
            text = text.replace(sw, "")

        # 去除标点符号
        text = re.sub(r"[？?！!。，,、；;：:\.\"'\"'()（）\[\]【】]", "", text)

        # 合并多余空格
        text = re.sub(r"\s+", " ", text).strip()

        return text if text else defaults.get(action, "")

    # ---------- 核心公有方法 ----------

    def classify_intent(self, user_input: str) -> ChatIntent:
        """
        对用户输入进行意图分类

        流程：LLM 分类 → 规则引擎兜底（当 LLM 分类为 general_chat 但输入含明确工具意图时覆盖）

        Args:
            user_input: 用户自然语言输入

        Returns:
            ChatIntent 分类结果
        """
        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self._classifier_prompt},
                    {"role": "user", "content": user_input}
                ],
                response_format=ChatIntent,
                max_tokens=500,
                temperature=0.2
            )
            result = response.choices[0].message.parsed

            # 规则引擎兜底：LLM 分类为 general_chat，但输入含明确工具意图关键词时覆盖
            if result.action == "general_chat":
                rule_based = self._rule_fallback(user_input)
                if rule_based:
                    print(f"[意图兜底] LLM 分类为 general_chat，规则引擎覆盖为 {rule_based.action}")
                    result = rule_based

            return result

        except Exception as e:
            # 分类失败时降级为 general_chat
            import logging
            logging.getLogger(__name__).error(f"[意图分类失败] {type(e).__name__}: {e}", exc_info=True)
            return ChatIntent(
                action="general_chat",
                confidence=0.3,
                city="",
                days="",
                crowd="",
                query=user_input
            )

    def chat(
        self,
        user_input: str,
        context: Optional[dict] = None,
        chat_history: Optional[list] = None,
        session_summary: Optional[str] = None
    ) -> dict:
        """
        处理用户聊天输入，返回响应

        Args:
            user_input: 用户输入文本
            context: 累积的会话上下文 {city, days, crowd, ...}
            chat_history: 聊天历史 [{role, content}, ...]，用于多轮记忆
            session_summary: 会话级摘要（由记忆管理器维护）

        Returns:
            dict: {
                intent: ChatIntent,
                response_text: str,
                tool_result: str,
                updated_context: dict,
                is_full_plan: bool,
                new_summary: Optional[str],   # 新摘要（若有更新）
                updated_history: list          # 更新后的历史（含本轮）
            }
        """
        if context is None:
            context = {}

        # 将 chat_history 和 summary 存入 context 供 handler 使用
        if chat_history:
            context["chat_history"] = chat_history
        if session_summary:
            context["session_summary"] = session_summary

        # 1. 意图分类
        intent = self.classify_intent(user_input)

        # 2. 合并上下文（分类结果优先）
        merged = self._merge_context(intent, context)

        # 2.5 降级逻辑：使用共享 check_degrade（来自 constants.py）
        # - query_weather 永不降级（可通过定位兜底或引导用户指定城市）
        # - 其他 CITY_REQUIRED_ACTIONS 意图，无城市且无定位时降级
        intent.action = check_degrade(
            intent.action,
            city=merged.get("city", ""),
            current_location=merged.get("current_location", "")
        )

        # 3. 尝试命中问答缓存（按城市+意图+相似度）
        cached_reply = self._try_get_cached_reply(user_input, intent, merged)
        if cached_reply is not None:
            # 缓存命中：直接返回缓存结果，不再调用工具
            response_text = cached_reply
            tool_result = "[cache_hit]"
        else:
            # 3.1 路由到对应处理
            handler = self._get_handler(intent.action)
            response_text, tool_result = handler(intent, merged, user_input)
            # 3.2 缓存本次最终回复
            self._save_reply_to_cache(user_input, intent, merged, response_text)

        # 4. 判断是否触发完整规划
        is_full_plan = intent.action == "full_plan" and merged.get("city")

        # 5. 更新对话历史（加入本轮）
        new_user_msg = {"role": "user", "content": user_input}
        new_ai_msg = {"role": "assistant", "content": response_text}
        updated_history = (chat_history or []) + [new_user_msg, new_ai_msg]

        # 6. 检查是否触发摘要压缩
        new_summary = session_summary
        if self.memory.should_summarize(updated_history):
            new_summary, updated_history = self.memory.compress(
                updated_history, existing_summary=session_summary
            )

        return {
            "intent": intent,
            "response_text": response_text,
            "tool_result": tool_result,
            "updated_context": merged,
            "is_full_plan": is_full_plan,
            "action_label": ACTION_LABELS.get(intent.action, "未知"),
            "new_summary": new_summary,
            "updated_history": updated_history
        }

    def chat_stream(
        self,
        user_input: str,
        context: Optional[dict] = None,
        chat_history: Optional[list] = None,
        session_summary: Optional[str] = None
    ):
        """
        流式版 chat：逐步 yield 文本片段

        Yields:
            ("delta", str)  — 增量文本片段
            ("meta", dict)   — 最终元信息（intent/updated_context/等）
        """
        if context is None:
            context = {}
        if chat_history:
            context["chat_history"] = chat_history
        if session_summary:
            context["session_summary"] = session_summary

        # 1. 意图分类（非流式，快速完成）
        intent = self.classify_intent(user_input)
        merged = self._merge_context(intent, context)
        # 降级逻辑：使用共享 check_degrade（来自 constants.py）
        intent.action = check_degrade(
            intent.action,
            city=merged.get("city", ""),
            current_location=merged.get("current_location", "")
        )

        action_label = ACTION_LABELS.get(intent.action, "未知")
        is_full_plan = intent.action == "full_plan" and merged.get("city")

        # 2. 尝试命中问答缓存（按城市+意图+相似度）
        cached_reply = self._try_get_cached_reply(user_input, intent, merged)
        if cached_reply is not None:
            # 缓存命中：直接输出完整缓存文本
            yield ("delta", cached_reply)
            yield ("meta_ready", None)
            return

        # 3. 路由：判断是否需要 LLM 流式输出
        if intent.action == "general_chat":
            # 闲聊：直接 LLM 流式输出
            yield from self._stream_chat(intent, merged, user_input)
        elif intent.action == "query_weather":
            # 天气查询：优先使用城市名或定位兜底，无则引导用户指定城市
            weather_city = merged.get("city", "") or merged.get("current_city", "") or merged.get("current_location", "")
            if not weather_city:
                # 无城市无定位，引导用户指定城市
                yield ("delta", "✨ 想帮你查天气呢🌤️ 不过还没告诉我具体是哪个城市哦📍\n告诉我【目的地】后，我马上为你更新【近日天气】📊")
            else:
                yield from self._stream_tool_reply(intent, merged, user_input, action_label)
        elif intent.action in ("query_scenic", "query_food",
                                 "query_hotel", "query_traffic", "query_luggage",
                                 "query_fun"):
            # 工具查询：先执行工具（非流式），再 LLM 美化（流式）
            yield from self._stream_tool_reply(intent, merged, user_input, action_label)
        else:
            # 引导类（full_plan/optimize_plan/book_ticket）：非流式
            handler = self._get_handler(intent.action)
            response_text, tool_result = handler(intent, merged, user_input)
            yield ("delta", response_text)

        # 4. 更新对话历史 + 摘要
        # 注意：实际 response_text 需要由调用方累积，这里用占位
        # 调用方应在收到 meta 时传入完整的 response_text
        yield ("meta_ready", None)

    def _stream_chat(self, intent, context, raw_input):
        """流式闲聊回复"""
        city = context.get("city", "")
        days = context.get("days", "")
        current_location = context.get("current_location", "")
        current_location_detail = context.get("current_location_detail", "")
        chat_history = context.get("chat_history", [])
        session_summary = context.get("session_summary")

        system_prompt = (
            "你是 Travel Agent 旅行助手，一个友好、专业的 AI 旅行顾问。\n\n"
            "重要规则：\n"
            "1. 当用户问非旅行相关问题时，请正常聊天回复\n"
            "2. 回复简洁自然，不要过长\n"
            "3. 必须用小红书种草笔记风格：短句为主、一句一行、适当用emoji装饰、"
            "重要信息用【】或**加粗**突出、语气亲切自然、文末可加1-2个话题标签\n"
            "4. 若系统消息中包含[历史摘要]，请基于摘要内容回答，保持记忆连续性"
        )
        context_hint = ""
        # 定位信息：让 AI 知道用户当前位置
        if current_location or current_location_detail:
            location_display = current_location_detail or current_location
            context_hint += f"\n\n【用户当前位置】{location_display}"
        # 旅行上下文
        if city:
            context_hint += f"\n\n当前对话上下文：用户正在关注{city}的旅行"
        if days:
            context_hint += f"，计划玩{days}天"

        messages = self.memory.build_llm_messages(
            system_prompt=system_prompt + context_hint,
            history_messages=chat_history,
            summary=session_summary,
            user_input=raw_input
        )

        try:
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=800,
                temperature=0.7,
                stream=True
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield ("delta", chunk.choices[0].delta.content)
        except Exception:
            yield ("delta", "✨ 抱歉，我暂时无法回复，请稍后再试～")

    def _stream_tool_reply(self, intent, context, raw_input, action_label):
        """流式工具查询专用模板渲染回复"""
        city = context.get("city", "")
        days = context.get("days", "")
        action = intent.action

        # 意图到专用模板的映射
        action_template_map = {
            "query_weather": TEMPLATE_WEATHER,
            "query_scenic": TEMPLATE_SCENIC,
            "query_food": TEMPLATE_FOOD,
            "query_hotel": TEMPLATE_HOTEL,
            "query_traffic": TEMPLATE_TRAFFIC,
            "query_luggage": TEMPLATE_LUGGAGE,
            "query_fun": TEMPLATE_FUN,
        }
        template_type = action_template_map.get(action)

        # 先执行工具（非流式）
        tool_text = self._execute_tool_only(intent, context, raw_input)
        if not tool_text:
            yield ("delta", "抱歉，未能获取到相关信息。")
            return

        # 未匹配到专用模板时，保持原有兜底
        if not template_type:
            yield ("delta", tool_text)
            return

        # 构建模板上下文
        template_context = {
            "city": city or "未指定",
            "days": days or "3",
            "crowd": "",
        }
        if template_type == TEMPLATE_WEATHER:
            template_context["weather_data"] = tool_text
        elif template_type == TEMPLATE_SCENIC:
            template_context["scenic_data"] = tool_text
        elif template_type == TEMPLATE_FOOD:
            template_context["food_data"] = tool_text
        elif template_type == TEMPLATE_HOTEL:
            template_context["hotel_data"] = tool_text
        elif template_type == TEMPLATE_TRAFFIC:
            template_context["traffic_data"] = tool_text
            destination = intent.query or ""
            if not destination:
                m = re.search(
                    r'(?:去|到|前往|想去)(.+?)(?:帮我|怎么|的交通|的路线|规划路线|路线规划|出行|坐车|坐地铁|坐公交|打车|自驾|$)',
                    raw_input
                )
                if m:
                    destination = m.group(1).strip()
            template_context["start_location"] = (
                context.get("current_location", "")
                or context.get("current_city", "")
                or "当前位置"
            )
            template_context["destination"] = destination
        elif template_type == TEMPLATE_LUGGAGE:
            template_context["weather_data"] = tool_text
            template_context["season"] = self._infer_season()
        elif template_type == TEMPLATE_FUN:
            template_context["fun_data"] = tool_text
            template_context["weather_data"] = ""

        # 流式模板渲染，同时累积完整回复用于缓存
        full_response = ""
        try:
            for chunk in OutputRenderService().render_stream(template_type, template_context):
                if chunk:
                    full_response += chunk
                    yield ("delta", chunk)
        except Exception:
            # 降级：直接返回工具原始结果
            full_response = tool_text
            yield ("delta", tool_text)

        # 缓存本次最终回复
        if full_response:
            self._save_reply_to_cache(raw_input, intent, context, full_response)

    def _execute_tool_only(self, intent, context, raw_input) -> str:
        """只执行工具，不做美化（供流式美化使用）

        使用新 @tool 工具的 invoke 直接调用；交通查询需从自然语言提取
        出发地/目的地，走 agent 循环自主调工具。
        """
        city = context.get("city", "")
        days = context.get("days", "3")
        action = intent.action

        try:
            if action == "query_weather":
                from tools import query_weather
                # 天气查询：目的地优先，未识别到城市时用出发地（定位）兜底
                # 优先使用 current_city（城市名），其次使用 current_location（地址）
                weather_city = city or context.get("current_city", "") or context.get("current_location", "")
                if not weather_city:
                    return "请告诉我您想查询哪个城市的天气？"
                return str(query_weather.invoke({"city": weather_city}))
            elif action == "query_scenic":
                from tools import search_scenic
                keywords = self._clean_search_keyword(intent.query, city, action)
                return str(search_scenic.invoke({"city": city, "keyword": keywords}))
            elif action == "query_food":
                from tools import search_food
                taste = self._clean_search_keyword(intent.query, city, action)
                return str(search_food.invoke({"city": city, "taste_demand": taste}))
            elif action == "query_hotel":
                from tools import search_poi
                keyword = self._clean_search_keyword(intent.query, city, action)
                return str(search_poi.invoke({"city": city, "poi_type": "hotel", "keyword": keyword}))
            elif action == "query_luggage":
                from tools import plan_luggage
                return str(plan_luggage.invoke({"city": city, "travel_days": days}))
            elif action == "query_fun":
                from tools import search_poi
                keyword = self._clean_search_keyword(intent.query, city, action)
                return str(search_poi.invoke({"city": city, "poi_type": "fun", "keyword": keyword}))
            elif action == "query_traffic":
                # 交通查询：直接提取参数 invoke 工具，不走 run_branch_agent
                from tools import query_traffic_route
                # 从 context 获取定位信息（出发地）
                loc_lng = context.get("current_location_lng", "")
                loc_lat = context.get("current_location_lat", "")
                loc_city = context.get("current_location", "")
                loc_detail = context.get("current_location_detail", "")

                # 打印定位信息（调试用）
                if loc_lng or loc_city:
                    print(f"\n[聊天-交通查询] 收到定位信息：")
                    print(f"  当前城市：{loc_city}")
                    print(f"  详细地址：{loc_detail}")
                    print(f"  经纬度：{loc_lng},{loc_lat}")

                # 从用户输入中提取目的地（"去XXX" / "到XXX"）
                end_address = intent.query or ""
                if not end_address:
                    # 正则提取：去/到 后面的地址（到句尾或"帮我"/"怎么"等词前）
                    m = re.search(r'(?:去|到|前往|想去)(.+?)(?:帮我|怎么|的交通|的路线|规划路线|路线规划|出行|坐车|坐地铁|坐公交|打车|自驾|$)', raw_input)
                    if m:
                        end_address = m.group(1).strip()
                    else:
                        return '请告诉我您想去的目的地，例如"我要去文殊院怎么坐车"'

                # 城市参数：优先用户指定城市，其次定位城市
                traffic_city = city or loc_city or ""

                # 直接 invoke 工具
                invoke_params = {
                    "end_address": end_address,
                    "city": traffic_city,
                }
                # 有定位时注入经纬度，启用距离分级规划
                if loc_lng and loc_lat:
                    invoke_params["start_lng"] = loc_lng
                    invoke_params["start_lat"] = loc_lat
                    invoke_params["start_address"] = loc_city or "当前位置"
                elif loc_city:
                    invoke_params["start_address"] = loc_city

                print(f"[聊天-交通查询] 工具参数: {invoke_params}")
                return str(query_traffic_route.invoke(invoke_params))
        except Exception as e:
            return f"工具调用失败：{str(e)}"
        return ""

    # ---------- 工具路由分发 ----------

    def _get_handler(self, action: str):
        """根据动作返回对应的处理函数"""
        handlers = {
            "query_weather": self._handle_weather,
            "query_scenic": self._handle_scenic,
            "query_food": self._handle_food,
            "query_hotel": self._handle_hotel,
            "query_traffic": self._handle_traffic,
            "query_luggage": self._handle_luggage,
            "query_fun": self._handle_fun,
            "book_ticket": self._handle_ticket,
            "full_plan": self._handle_full_plan,
            "optimize_plan": self._handle_optimize,
            "general_chat": self._handle_chat,
        }
        return handlers.get(action, self._handle_chat)

    # ---------- 各处理函数 ----------

    def _handle_weather(
        self, intent: ChatIntent, context: dict, raw_input: str
    ) -> tuple[str, str]:
        """处理天气查询 — 复用 _execute_tool_only 调用 @tool，再做小红书美化

        城市获取优先级：用户明确指定 > 定位城市名(current_city) > 定位地址(current_location) > 引导用户指定
        """
        city = context.get("city", "")
        location_city = context.get("current_city", "") or context.get("current_location", "")

        # 优先使用用户指定城市，其次使用定位兜底
        weather_city = city or location_city
        if not weather_city:
            return (
                "✨ 想帮你查天气呢🌤️ 不过还没告诉我具体是哪个城市哦📍\n"
                "告诉我【目的地】后，我马上为你更新【近日天气】📊\n"
                "顺便还能帮你搭配出行穿搭和行程建议✈️",
                ""
            )

        tool_text = self._execute_tool_only(intent, context, raw_input)
        if not tool_text:
            return f"抱歉，未能查询到 {weather_city} 的天气信息", ""
        reply = self._render_tool_reply(
            TEMPLATE_WEATHER, tool_text, weather_city, context.get("days", "")
        )
        return reply, tool_text

    def _handle_scenic(
        self, intent: ChatIntent, context: dict, raw_input: str
    ) -> tuple[str, str]:
        """处理景点查询 — 复用 _execute_tool_only 调用 @tool，再做小红书美化"""
        city = context.get("city", "")
        if not city:
            return ("请问您想查询哪个城市的景点？", "")

        tool_text = self._execute_tool_only(intent, context, raw_input)
        if not tool_text:
            return f"抱歉，未能查询到 {city} 的景点信息", ""
        reply = self._render_tool_reply(
            TEMPLATE_SCENIC, tool_text, city, context.get("days", "")
        )
        return reply, tool_text

    def _handle_food(
        self, intent: ChatIntent, context: dict, raw_input: str
    ) -> tuple[str, str]:
        """处理美食查询 — 复用 _execute_tool_only 调用 @tool，再做小红书美化"""
        city = context.get("city", "")
        if not city:
            return ("请问您想查询哪个城市的美食？", "")

        tool_text = self._execute_tool_only(intent, context, raw_input)
        if not tool_text:
            return f"抱歉，未能查询到 {city} 的美食信息", ""
        reply = self._render_tool_reply(
            TEMPLATE_FOOD, tool_text, city, context.get("days", "")
        )
        return reply, tool_text

    def _handle_hotel(
        self, intent: ChatIntent, context: dict, raw_input: str
    ) -> tuple[str, str]:
        """处理酒店查询 — 复用 _execute_tool_only 调用 @tool，再做小红书美化"""
        city = context.get("city", "")
        if not city:
            return ("请问您想查询哪个城市的酒店？", "")

        tool_text = self._execute_tool_only(intent, context, raw_input)
        if not tool_text:
            return f"抱歉，未能查询到 {city} 的酒店信息", ""
        reply = self._render_tool_reply(
            TEMPLATE_HOTEL, tool_text, city, context.get("days", "")
        )
        return reply, tool_text

    def _handle_traffic(
        self, intent: ChatIntent, context: dict, raw_input: str
    ) -> tuple[str, str]:
        """处理交通查询 — 复用 _execute_tool_only 调用 @tool，再用交通专用模板渲染"""
        tool_text = self._execute_tool_only(intent, context, raw_input)
        if not tool_text:
            return ("抱歉，未能查询到交通路线信息，请补充出发地和目的地", "")

        # 提取目的地与出发地，供 traffic_template 使用
        destination = intent.query or ""
        if not destination:
            m = re.search(
                r'(?:去|到|前往|想去)(.+?)(?:帮我|怎么|的交通|的路线|规划路线|路线规划|出行|坐车|坐地铁|坐公交|打车|自驾|$)',
                raw_input
            )
            if m:
                destination = m.group(1).strip()
        start_location = (
            context.get("current_location", "")
            or context.get("current_city", "")
            or "当前位置"
        )

        reply = self._render_tool_reply(
            TEMPLATE_TRAFFIC,
            tool_text,
            context.get("city", ""),
            context.get("days", ""),
            start_location=start_location,
            destination=destination,
        )
        return reply, tool_text

    def _handle_luggage(
        self, intent: ChatIntent, context: dict, raw_input: str
    ) -> tuple[str, str]:
        """处理行李穿搭查询 — 复用 _execute_tool_only 调用 @tool，再做小红书美化"""
        city = context.get("city", "")
        days = context.get("days", "3")
        if not city:
            return ("请问您要去哪个城市旅行？", "")

        tool_text = self._execute_tool_only(intent, context, raw_input)
        if not tool_text:
            return f"抱歉，未能生成 {city} 的行李穿搭方案", ""
        reply = self._render_tool_reply(
            TEMPLATE_LUGGAGE, tool_text, city, days
        )
        return reply, tool_text

    def _handle_fun(
        self, intent: ChatIntent, context: dict, raw_input: str
    ) -> tuple[str, str]:
        """处理趣玩查询 — 复用 _execute_tool_only 调用 @tool，再用趣玩专用模板渲染"""
        city = context.get("city", "")
        if not city:
            return ("请问您想查询哪个城市的趣玩活动？", "")

        tool_text = self._execute_tool_only(intent, context, raw_input)
        if not tool_text:
            return f"抱歉，未能查询到 {city} 的趣玩活动", ""
        reply = self._render_tool_reply(
            TEMPLATE_FUN, tool_text, city, context.get("days", "")
        )
        return reply, tool_text

    def _handle_ticket(
        self, intent: ChatIntent, context: dict, raw_input: str
    ) -> tuple[str, str]:
        """处理门票预订 — 小红书风格回复"""
        city = context.get("city", "")
        if not city:
            return ("请问您想预订哪个城市的门票呀？🎫", "")

        return (
            f"✨ 已记录您的订票需求\n\n"
            f"📍 目的地：【{city}】\n"
            f"📝 需求：{intent.query}\n\n"
            f"⚠️ 门票预订功能正在开发中，敬请期待～\n\n"
            f"#{city}门票 #出行准备",
            ""
        )

    def _handle_full_plan(
        self, intent: ChatIntent, context: dict, raw_input: str
    ) -> tuple[str, str]:
        """处理完整行程规划请求 — 小红书风格引导"""
        city = context.get("city", "")
        days = context.get("days", "")

        if not city:
            return ("✨ 好呀，帮你规划行程！先告诉我目的地城市吧？📍", "")
        if not days:
            return (f"✨ 去【{city}】很棒！打算玩几天呢？📅", "")

        # 信息齐全，提示即将调用规划
        crowd = context.get("crowd", "")
        msg = f"✨ 收到！马上为你规划【{city}】{days}天的行程"
        if crowd:
            msg += f"（{crowd}）"
        msg += "，稍等一下哦～⏳"
        return msg, ""

    def _handle_optimize(
        self, intent: ChatIntent, context: dict, raw_input: str
    ) -> tuple[str, str]:
        """处理行程优化请求 — 小红书风格引导"""
        city = context.get("city", "")
        if not city:
            return ("先告诉我目的地城市，才能帮你优化行程哦～📍", "")

        optimize_desc = intent.query or raw_input
        return (
            f"✨ 好的，帮你优化【{city}】的行程\n"
            f"📌 重点关注：{optimize_desc}\n"
            f"正在重新规划，稍等～⏳",
            ""
        )

    def _handle_chat(
        self, intent: ChatIntent, context: dict, raw_input: str
    ) -> tuple[str, str]:
        """处理通用聊天/追问 — 调用 LLM 进行自然对话（带历史摘要）"""
        city = context.get("city", "")
        days = context.get("days", "")
        current_location = context.get("current_location", "")
        current_location_detail = context.get("current_location_detail", "")
        chat_history = context.get("chat_history", [])
        session_summary = context.get("session_summary")

        # 构建系统提示词：旅行助手角色，小红书风格回复
        system_prompt = (
            "你是 Travel Agent 旅行助手，一个友好、专业的 AI 旅行顾问。\n\n"
            "你的核心能力：\n"
            "- 查询天气、景点、美食、酒店、交通等信息\n"
            "- 规划完整的旅行行程\n"
            "- 提供行李穿搭建议\n"
            "- 推荐趣玩活动\n\n"
            "重要规则：\n"
            "1. 当用户问非旅行相关问题时（如你是谁、讲个笑话等），请正常聊天回复\n"
            "2. 在闲聊中适时引导用户回到旅行话题\n"
            "3. 回复简洁自然，不要过长\n"
            "4. 必须用小红书种草笔记风格回复：短句为主、一句一行、适当用emoji装饰、"
            "重要信息用【】或**加粗**突出、语气亲切自然像朋友推荐、文末可加1-2个话题标签\n"
            "5. 若系统消息中包含[历史摘要]，请基于摘要内容回答，保持记忆连续性"
        )

        # 加入当前对话上下文（包含定位信息）
        context_hint = ""
        # 定位信息：让 AI 知道用户当前位置
        if current_location or current_location_detail:
            location_display = current_location_detail or current_location
            context_hint += f"\n\n【用户当前位置】{location_display}"
        # 旅行上下文
        if city:
            context_hint += f"\n\n当前对话上下文：用户正在关注{city}的旅行"
        if days:
            context_hint += f"，计划玩{days}天"

        # 使用记忆管理器构建 LLM messages（系统提示 + 摘要 + 历史 + 当前）
        messages = self.memory.build_llm_messages(
            system_prompt=system_prompt + context_hint,
            history_messages=chat_history,
            summary=session_summary,
            user_input=raw_input
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=800,
                temperature=0.7
            )
            reply = response.choices[0].message.content.strip()
            return reply, ""
        except Exception as e:
            # LLM 调用失败时，降级为小红书风格引导
            if city and days:
                return (
                    f"✨ 关于【{city}】{days}天的旅行，还想了解什么呀？\n\n"
                    f"☀️ 天气怎么样？\n"
                    f"🏞️ 有什么景点推荐？\n"
                    f"😋 有什么好吃的？\n"
                    f"🗺️ 帮我规划完整行程\n\n"
                    f"#{city}旅游 #出行攻略",
                    ""
                )
            return (
                "✨ 你好呀！我是旅行小助手 🌍\n\n"
                "可以问我：\n"
                "☀️ 「杭州最近天气怎么样？」\n"
                "😋 「成都有什么好吃的？」\n"
                "🗺️ 「帮我规划三天上海行程」\n"
                "👨‍👩‍👧 「北京亲子游推荐」\n\n"
                "想去哪里旅行呢？📍"
            )

    # ---------- 内部工具方法 ----------

    @staticmethod
    def _merge_context(intent: ChatIntent, context: dict) -> dict:
        """合并分类结果到上下文（分类结果优先覆盖）"""
        merged = dict(context)

        if intent.city:
            merged["city"] = intent.city
        if intent.days:
            # 标准化天数
            day_str = intent.days.replace("天", "").strip()
            if day_str.isdigit():
                merged["days"] = day_str
        if intent.crowd:
            merged["crowd"] = intent.crowd
        if intent.current_location:
            merged["current_location"] = intent.current_location

        return merged

    @staticmethod
    def reset_context() -> dict:
        """返回空的上下文模板"""
        return {
            "city": "",
            "days": "",
            "crowd": "",
            "query": "",
            "travel_time": "",
            "style": "简约干货",
            "current_location": "",
        }