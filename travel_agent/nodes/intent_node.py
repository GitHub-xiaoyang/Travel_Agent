# -*- coding: utf-8 -*-
"""
意图解析节点：混合 NLU 漏斗架构

三层漏斗式意图识别，逐层筛选，兼顾效率与准确率：
  Layer 0: 快速路径（前端预填充）——跳过所有 NLU，直接执行
  Layer 1: 规则引擎（关键词+正则）——零成本、亚毫秒级，覆盖 60%+ 场景
  Layer 2: 轻量小模型（TF-IDF 相似度）——低成本、毫秒级，覆盖 20%+ 模糊场景
  Layer 3: LLM 兜底——高成本、秒级，覆盖长尾复杂场景

设计理念：
  - 规则优先：高频明确意图用规则硬匹配，避免 LLM 浪费
  - 置信度驱动：每层输出 confidence，低置信度才下钻
  - 参数提取：规则/小模型/LLM 均支持结构化参数提取
"""

import re
import math
from collections import Counter
from typing import Optional

from pydantic import BaseModel, Field
from openai import OpenAI

from config import settings
from travel_agent.retry import with_llm_retry
from travel_agent.errors import classify_exception, InputValidationError
from travel_agent.nodes import with_node_error_handler, NODE_INTENT
from travel_agent.nodes.constants import INTENT_KEYWORDS, CITY_NAMES
from travel_agent.prompt_templates.prompt_loader import render_template, INTENT_PROMPT
from travel_agent.state import TravelAgentState, IntentInfo


# ============================================================
# LLM 返回的意图解析结果（兼容原有接口）
# ============================================================
class TravelIntent(BaseModel):
    """LLM 返回的意图解析结果"""
    model_config = {"populate_by_name": True, "extra": "ignore"}

    travel_type: str = Field(default="", description="出行类型")
    crowd: str = Field(default="", description="出行人群")
    core_demand: str = Field(default="", description="用户核心诉求")
    destination: str = Field(default="", alias="city", description="目的地城市")
    travel_days: str = Field(default="", alias="days", description="出行天数")
    travel_time: str = Field(default="", description="出行时间段")
    required_tools: list[str] = Field(default_factory=list, description="需要调用的工具列表")
    confidence: float = Field(default=0.0, description="意图置信度 0-1")


# ============================================================
# 规则引擎：意图关键词 & 参数提取正则
# ============================================================

# 出行类型关键词
TRAVEL_TYPE_KEYWORDS: dict[str, list[str]] = {
    "旅游": ["旅游", "旅行", "游", "度假"],
    "商务出差": ["出差", "商务", "公务"],
    "探亲访友": ["探亲", "访友", "看朋友", "回家"],
    "公司团建": ["团建", "公司旅游", "团队建设"],
    "户外徒步": ["徒步", "登山", "爬山", "露营", "户外"],
    "周边短途": ["周边", "短途", "近郊", "一日游", "周末游"],
}

# 出行人群关键词
CROWD_KEYWORDS: dict[str, list[str]] = {
    "情侣": ["情侣", "两个人", "和对象", "和男朋友", "和女朋友"],
    "亲子带小孩": ["亲子", "带孩子", "带小孩", "小朋友", "娃娃"],
    "带老人": ["带老人", "带爸妈", "带父母", "老人"],
    "朋友多人": ["朋友", "兄弟", "姐妹", "多人", "一群"],
    "全家老小": ["全家", "一家人", "全家老小"],
}

# 出行时间段关键词
TRAVEL_TIME_KEYWORDS: dict[str, list[str]] = {
    "周末": ["周末", "周六", "周日", "双休日"],
    "五一": ["五一", "劳动节", "5月1"],
    "国庆": ["国庆", "十一", "黄金周"],
    "春节": ["春节", "过年", "寒假"],
    "暑假": ["暑假", "暑期"],
    "明天": ["明天", "明日"],
    "后天": ["后天"],
}


def _match_intent_keywords(text: str) -> list[tuple[str, int]]:
    """规则引擎：关键词匹配，返回 [(意图, 命中关键词数量), ...]"""
    text_lower = text.lower()
    scores: list[tuple[str, int]] = []
    for intent, keywords in INTENT_KEYWORDS.items():
        hit_count = sum(1 for kw in keywords if kw.lower() in text_lower)
        if hit_count > 0:
            scores.append((intent, hit_count))
    # 按命中数排序
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def _extract_city(text: str) -> str:
    """从用户输入中提取城市名（使用共享 CITY_NAMES，来自 constants.py）"""
    text_lower = text.lower()
    for city in CITY_NAMES:
        if city.lower() in text_lower:
            return city
    return ""


def _extract_days(text: str) -> str:
    """提取出行天数"""
    patterns = [
        r"(\d+)\s*天",
        r"(\d+)\s*日",
        r"(\d+)\s*晚",
        r"(\d+)\s*夜",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1)
    return ""


def _extract_travel_type(text: str) -> str:
    """提取出行类型"""
    for ttype, keywords in TRAVEL_TYPE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return ttype
    return ""


def _extract_crowd(text: str) -> str:
    """提取出行人群"""
    for crowd, keywords in CROWD_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return crowd
    return ""


def _extract_travel_time(text: str) -> str:
    """提取出行时间段"""
    for ttime, keywords in TRAVEL_TIME_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return ttime
    return ""


def _extract_core_demand(text: str, intent: str) -> str:
    """根据意图生成核心需求摘要"""
    demand_map = {
        "query_weather": "查询天气",
        "query_scenic": "查询景点",
        "query_food": "查询美食",
        "query_hotel": "查询酒店",
        "query_traffic": "查询交通路线",
        "query_luggage": "查询行李穿搭建议",
        "query_fun": "查询趣玩活动",
        "book_ticket": "预订门票",
        "full_plan": "规划完整行程",
        "optimize_plan": "优化行程方案",
    }
    return demand_map.get(intent, "")


def _infer_required_tools(intent: str, city: str) -> list[str]:
    """根据意图推断需要的工具列表"""
    if intent == "query_weather":
        return ["weather"]
    elif intent == "query_scenic":
        return ["weather", "scenic"]
    elif intent == "query_food":
        return ["weather", "food"]
    elif intent == "query_hotel":
        return ["weather"]
    elif intent == "query_traffic":
        return ["traffic"]
    elif intent == "query_luggage":
        return ["weather", "luggage"]
    elif intent == "query_fun":
        return ["weather", "fun"]
    elif intent == "full_plan":
        tools = ["weather", "scenic", "food", "luggage"]
        if not city:
            tools.append("traffic")
        return tools
    elif intent == "optimize_plan":
        return ["weather", "scenic", "food"]
    else:
        return []


# ============================================================
# Layer 1：规则引擎
# ============================================================

class RuleEngine:
    """规则引擎：基于关键词+正则的快速意图识别"""

    # 置信度阈值：低于此值则下钻到下一层
    CONFIDENCE_THRESHOLD = 0.6

    def classify(self, text: str) -> Optional[TravelIntent]:
        """
        规则分类：返回高置信度意图，低置信度返回 None

        Args:
            text: 用户输入文本

        Returns:
            TravelIntent（高置信度）或 None（需下钻）
        """
        # 0. 通用聊天/闲聊检测（优先于关键词匹配）
        chat_patterns = [
            r"^(你好|您好|hi|hello|在吗|在不在)",
            r"^(谢谢|感谢|多谢|thx)",
            r".*(哈哈|嘻嘻|呵呵|😀|😄|😂)",
            r".*(什么意思|怎么理解|解释一下)",
        ]
        for pat in chat_patterns:
            if re.match(pat, text, re.IGNORECASE):
                return TravelIntent(
                    travel_type="",
                    crowd="",
                    core_demand="闲聊",
                    destination="",
                    travel_days="",
                    travel_time="",
                    required_tools=[],
                    confidence=0.9,
                )

        # 1. 关键词匹配
        matched = _match_intent_keywords(text)

        # 兜底：无关键词命中，但有城市+时间 → 推断为 full_plan
        if not matched:
            city = _extract_city(text)
            travel_time = _extract_travel_time(text)
            if city and travel_time:
                days = _extract_days(text)
                return TravelIntent(
                    travel_type=_extract_travel_type(text) or "旅游",
                    crowd=_extract_crowd(text),
                    core_demand="规划完整行程",
                    destination=city,
                    travel_days=days,
                    travel_time=travel_time,
                    required_tools=_infer_required_tools("full_plan", city),
                    confidence=0.7,
                )
            return None

        top_intent, hit_count = matched[0]
        total_keywords = len(INTENT_KEYWORDS.get(top_intent, []))
        # 置信度计算：单次命中 ≥0.5，多次命中趋近 1.0
        # 公式：0.5 + 0.5 * (hit_count / (hit_count + 3))
        # 1次命中 ≈ 0.625, 2次 ≈ 0.75, 3次 ≈ 0.83, 5次 ≈ 0.91
        confidence = 0.5 + 0.5 * (hit_count / (hit_count + 3))

        # 2. 构建结果
        city = _extract_city(text)
        days = _extract_days(text)
        travel_type = _extract_travel_type(text)
        crowd = _extract_crowd(text)
        travel_time = _extract_travel_time(text)
        core_demand = _extract_core_demand(text, top_intent)
        required_tools = _infer_required_tools(top_intent, city)

        # 4. 参数补全：full_plan 必须有 city+days，否则降级
        if top_intent == "full_plan" and (not city or not days):
            confidence *= 0.5

        # 5. 天气查询兜底：无城市但有定位时置信度不减
        if top_intent == "query_weather" and not city:
            pass  # 允许无城市，后续用定位兜底

        # 6. 置信度判断
        if confidence < self.CONFIDENCE_THRESHOLD:
            return None

        return TravelIntent(
            travel_type=travel_type,
            crowd=crowd,
            core_demand=core_demand,
            destination=city,
            travel_days=days,
            travel_time=travel_time,
            required_tools=required_tools,
            confidence=confidence,
        )


# ============================================================
# Layer 2：轻量小模型（TF-IDF 余弦相似度）
# ============================================================

# 意图 → 典型示例句（用于构建 TF-IDF 向量）
INTENT_EXAMPLES: dict[str, list[str]] = {
    "query_weather": [
        "今天天气怎么样", "会下雨吗", "气温多少度", "天气预报",
        "穿什么衣服合适", "最近天气如何",
    ],
    "query_scenic": [
        "有什么好玩的景点", "推荐几个景区", "哪里可以游玩",
        "有什么必去的地方", "风景区推荐",
    ],
    "query_food": [
        "有什么好吃的", "推荐美食", "特色餐厅",
        "当地小吃", "美食攻略",
    ],
    "query_hotel": [
        "找个酒店", "推荐民宿", "住宿哪里好",
        "订个宾馆", "客栈推荐",
    ],
    "query_traffic": [
        "怎么坐车去", "交通路线", "地铁几号线",
        "打车多少钱", "怎么去机场", "自驾路线",
    ],
    "query_luggage": [
        "带什么衣服", "行李怎么打包", "需要带什么",
        "穿搭建议", "行李清单",
    ],
    "query_fun": [
        "有什么活动", "哪里好玩", "娱乐推荐",
        "体验项目", "休闲好去处",
    ],
    "book_ticket": [
        "怎么订门票", "预约门票", "买票",
        "预订门票",
    ],
    "full_plan": [
        "帮我规划行程", "安排一下旅行", "制定攻略",
        "几天行程怎么安排", "推荐路线",
    ],
    "optimize_plan": [
        "优化一下行程", "调整安排", "修改行程",
        "重新规划",
    ],
    "general_chat": [
        "你好", "介绍一下自己", "你是谁",
        "讲个笑话", "今天心情好",
    ],
}


class TFIDFClassifier:
    """轻量 TF-IDF 分类器：基于词频余弦相似度的意图匹配"""

    def __init__(self):
        self._build_vocab()
        self._build_vectors()

    def _build_vocab(self):
        """构建语料词汇表"""
        all_words = set()
        # 城市列表补充（使用共享 CITY_NAMES）
        self._city_words = set(CITY_NAMES)
        for examples in INTENT_EXAMPLES.values():
            for ex in examples:
                for word in self._tokenize(ex):
                    all_words.add(word)
        self._vocab = list(all_words)
        self._vocab_index = {w: i for i, w in enumerate(self._vocab)}

    def _build_vectors(self):
        """构建意图 TF-IDF 向量"""
        self._idf = {}
        doc_count = len(INTENT_EXAMPLES)

        # 计算 IDF
        for word in self._vocab:
            doc_freq = sum(
                1 for examples in INTENT_EXAMPLES.values()
                if any(word in self._tokenize(ex) for ex in examples)
            )
            self._idf[word] = math.log((doc_count + 1) / (doc_freq + 1)) + 1

        # 构建意图向量
        self._intent_vectors = {}
        for intent, examples in INTENT_EXAMPLES.items():
            vector = [0.0] * len(self._vocab)
            for example in examples:
                for word in self._tokenize(example):
                    if word in self._vocab_index:
                        idx = self._vocab_index[word]
                        tf = 1.0
                        vector[idx] += tf * self._idf.get(word, 0)
            # 归一化
            norm = math.sqrt(sum(v * v for v in vector))
            if norm > 0:
                vector = [v / norm for v in vector]
            self._intent_vectors[intent] = vector

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """简单分词：单字分词 + 词典词"""
        tokens = []
        # 2-4 字词
        for n in range(2, 5):
            for i in range(len(text) - n + 1):
                tokens.append(text[i:i + n])
        # 单字
        for ch in text:
            tokens.append(ch)
        # 过滤停用字符
        stop_chars = set("的了是在和与或我你他她它们这那个一下吗呢吧啊呀哦就都还也又只很非")
        return [t for t in tokens if not all(c in stop_chars for c in t)]

    def classify(self, text: str) -> Optional[TravelIntent]:
        """
        TF-IDF 分类：返回最相似的意图

        Args:
            text: 用户输入

        Returns:
            TravelIntent（带置信度）或 None
        """
        # 构建用户输入向量
        tokens = self._tokenize(text)
        user_vector = [0.0] * len(self._vocab)
        for token in tokens:
            if token in self._vocab_index:
                idx = self._vocab_index[token]
                user_vector[idx] += self._idf.get(token, 0)

        norm = math.sqrt(sum(v * v for v in user_vector))
        if norm == 0:
            return None
        user_vector = [v / norm for v in user_vector]

        # 余弦相似度
        best_intent = ""
        best_score = 0.0
        for intent, intent_vec in self._intent_vectors.items():
            score = sum(a * b for a, b in zip(user_vector, intent_vec))
            if score > best_score:
                best_score = score
                best_intent = intent

        # 置信度归一化
        confidence = min(1.0, best_score * 2.0)

        if confidence < 0.4:
            return None

        # 提取参数
        city = _extract_city(text)
        days = _extract_days(text)
        travel_type = _extract_travel_type(text)
        crowd = _extract_crowd(text)
        travel_time = _extract_travel_time(text)
        core_demand = _extract_core_demand(text, best_intent)
        required_tools = _infer_required_tools(best_intent, city)

        return TravelIntent(
            travel_type=travel_type,
            crowd=crowd,
            core_demand=core_demand,
            destination=city,
            travel_days=days,
            travel_time=travel_time,
            required_tools=required_tools,
            confidence=confidence,
        )


# ============================================================
# 全局单例
# ============================================================
_rule_engine = RuleEngine()
_tfidf_classifier = TFIDFClassifier()


# ============================================================
# 意图解析业务逻辑类
# ============================================================

class IntentNode:
    """意图解析业务逻辑类：混合 NLU 漏斗架构"""

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL
        )
        self.model_name = settings.LLM_MODEL_NAME
        self.rule_engine = _rule_engine
        self.tfidf = _tfidf_classifier

    @with_llm_retry(max_retries=3, base_delay=1.0)
    def _call_llm(self, prompt: str) -> TravelIntent:
        """带重试的 LLM 调用"""
        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format=TravelIntent,
                max_tokens=settings.LLM_MAX_TOKENS
            )
            return response.choices[0].message.parsed
        except Exception as e:
            raise classify_exception(e)

    def parse_intent(self, user_query: str, chat_history: list[dict] = None) -> TravelIntent:
        """
        三层漏斗意图解析

        Layer 1: 规则引擎（关键词+正则）
        Layer 2: TF-IDF 相似度
        Layer 3: LLM 兜底

        Args:
            user_query: 用户当前输入
            chat_history: 历史对话

        Returns:
            TravelIntent 对象（带 confidence 标记来源）
        """
        # ---------- Layer 1: 规则引擎 ----------
        result = self.rule_engine.classify(user_query)
        if result and result.confidence >= self.rule_engine.CONFIDENCE_THRESHOLD:
            result.core_demand = f"[规则] {result.core_demand}" if not result.core_demand.startswith("[规则") else result.core_demand
            return result

        # ---------- Layer 2: TF-IDF 相似度 ----------
        # 合并输入与最近历史对话，增强上下文感知
        context_text = user_query
        if chat_history:
            recent = chat_history[-3:]
            history_text = " ".join(
                msg.get("content", "") for msg in recent if msg.get("role") == "user"
            )
            if history_text:
                context_text = f"{history_text} {user_query}"

        result = self.tfidf.classify(context_text)
        if result and result.confidence >= 0.5:
            result.core_demand = f"[TF-IDF] {result.core_demand}" if not result.core_demand.startswith("[") else result.core_demand
            return result

        # ---------- Layer 3: LLM 兜底 ----------
        history_text = self._format_history(chat_history)
        history_section = f"\n【历史对话】\n{history_text}\n" if history_text else ""

        prompt = render_template(
            INTENT_PROMPT,
            user_query=user_query,
            history_section=history_section
        )

        llm_result = self._call_llm(prompt)
        llm_result.confidence = 0.8  # LLM 默认高置信度
        # 标记来源
        if not llm_result.core_demand.startswith("["):
            llm_result.core_demand = f"[LLM] {llm_result.core_demand}"
        return llm_result

    def _format_history(self, chat_history: list[dict] = None) -> str:
        """格式化聊天历史用于 prompt"""
        if not chat_history:
            return ""
        lines = []
        for msg in chat_history[-10:]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            lines.append(f"[{role}]: {content}")
        return "\n".join(lines)


# 全局单例
intent_service = IntentNode()


# ============================================================
# LangGraph 节点入口
# ============================================================

@with_node_error_handler(NODE_INTENT)
def parse_intent(state: TravelAgentState) -> dict:
    """LangGraph 节点：三层漏斗意图解析 + 决定工具列表"""
    user_text = state.user_input.strip()
    if not user_text:
        raise InputValidationError(
            "用户输入为空，无法解析出行意图",
            node_name=NODE_INTENT
        )

    # ---------- 打印定位信息 ----------
    if state.intent_info:
        loc = state.intent_info
        if loc.current_location or loc.current_location_lng:
            print(f"\n{'='*50}")
            print(f"[定位信息] 后端收到前端传入的定位数据：")
            print(f"  当前城市：{loc.current_location}")
            print(f"  详细地址：{loc.current_location_detail}")
            print(f"  经度：{loc.current_location_lng}")
            print(f"  纬度：{loc.current_location_lat}")
            print(f"{'='*50}\n")

    # ---------- 快速路径：前端已预填充 ----------
    if state.intent_info and state.intent_info.required_tools:
        updated_intent = state.intent_info
        print(f"[意图解析] 快速路径（前端预填充）: destination={updated_intent.destination}, tools={updated_intent.required_tools}")
        return {
            "intent_info": updated_intent,
            "chat_history": [{"role": "user", "content": user_text}],
        }

    # ---------- 三层漏斗解析 ----------
    intent_data = intent_service.parse_intent(user_text, state.chat_history)

    # 打印解析来源
    source = "LLM"
    if intent_data.core_demand.startswith("[规则"):
        source = "规则引擎"
    elif intent_data.core_demand.startswith("[TF-IDF"):
        source = "TF-IDF"
    print(f"[意图解析] 来源={source}, 置信度={intent_data.confidence:.2f}, destination={intent_data.destination}, tools={intent_data.required_tools}")

    # 保留已有定位信息
    existing_location = state.intent_info.current_location if state.intent_info else ""
    existing_location_detail = state.intent_info.current_location_detail if state.intent_info else ""
    existing_location_lng = state.intent_info.current_location_lng if state.intent_info else ""
    existing_location_lat = state.intent_info.current_location_lat if state.intent_info else ""

    new_intent = IntentInfo(
        travel_type=intent_data.travel_type,
        crowd=intent_data.crowd,
        core_demand=intent_data.core_demand,
        destination=intent_data.destination,
        travel_days=intent_data.travel_days,
        travel_time=intent_data.travel_time,
        current_location=existing_location,
        current_location_detail=existing_location_detail,
        current_location_lng=existing_location_lng,
        current_location_lat=existing_location_lat,
        required_tools=intent_data.required_tools,
    )

    return {
        "intent_info": new_intent,
        "chat_history": [{"role": "user", "content": user_text}],
    }
