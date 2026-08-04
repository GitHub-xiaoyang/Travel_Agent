# -*- coding: utf-8 -*-
"""
会话记忆管理器（滑动窗口 + LLM 摘要压缩）

策略：
    1. 短期窗口：保留最近 N 条原始对话（默认 10 条）
    2. 摘要压缩：超过窗口时，把旧消息交给 LLM 摘要
    3. 最终上下文：[摘要消息] + [最近 N-1 条] + [新消息]
    4. 摘要也会累积（旧摘要参与下次摘要压缩）

优点：
    - Token 不会无限膨胀
    - 关键信息（如用户偏好、宠物、历史行程）通过摘要保留
    - 摘要消息用 system role 标注，不会与真实对话混淆
"""

from typing import Optional
from openai import OpenAI

from config import settings


# 默认参数
DEFAULT_WINDOW_SIZE = 10       # 窗口大小：超过则触发摘要
DEFAULT_KEEP_RECENT = 4        # 摘要后保留最近几条原始对话


class ConversationMemory:
    """会话级记忆管理器：滑动窗口 + LLM 摘要压缩"""

    def __init__(
        self,
        window_size: int = DEFAULT_WINDOW_SIZE,
        keep_recent: int = DEFAULT_KEEP_RECENT
    ):
        """
        初始化记忆管理器

        Args:
            window_size: 触发摘要的消息阈值
            keep_recent: 摘要后保留的原始对话条数
        """
        self.window_size = window_size
        self.keep_recent = keep_recent
        self.llm_client = OpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL
        )
        self.model_name = settings.LLM_MODEL_NAME

    def should_summarize(self, messages: list[dict]) -> bool:
        """判断是否需要触发摘要"""
        return len(messages) > self.window_size

    def summarize(self, messages_to_compress: list[dict]) -> Optional[str]:
        """
        调用 LLM 对历史消息做摘要

        Args:
            messages_to_compress: 待压缩的旧消息列表

        Returns:
            摘要文本；失败返回 None
        """
        if not messages_to_compress:
            return None

        # 拼接对话文本
        conv_text = self._format_messages(messages_to_compress)

        prompt = (
            "请将以下对话历史压缩为一段简洁的摘要，重点保留：\n"
            "1. 用户的个人信息（姓名、偏好、宠物、家庭等）\n"
            "2. 已讨论过的旅行相关决策（目的地、天数、人群、行程）\n"
            "3. 用户明确提出的需求或约束\n"
            "4. 助手给出的重要建议\n\n"
            "要求：\n"
            "- 控制在 200 字以内\n"
            "- 用第三人称陈述\n"
            "- 保留所有关键事实，不要编造\n\n"
            "对话历史：\n"
            f"{conv_text}"
        )

        try:
            resp = self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.3
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return None

    def compress(
        self,
        all_messages: list[dict],
        existing_summary: Optional[str] = None
    ) -> tuple[Optional[str], list[dict]]:
        """
        压缩对话历史：旧消息 → 摘要 + 最近 N 条

        Args:
            all_messages: 完整的对话历史 [{role, content}, ...]
            existing_summary: 已有的旧摘要（若有，参与新摘要）

        Returns:
            (new_summary, kept_messages)
            - new_summary: 新摘要文本（失败则为 None）
            - kept_messages: 保留的最近 N 条原始消息
        """
        # 待压缩部分 = 旧摘要(若有) + 超出窗口的消息
        to_compress = []
        if existing_summary:
            to_compress.append({
                "role": "system",
                "content": f"[历史摘要] {existing_summary}"
            })
        to_compress.extend(all_messages[:-self.keep_recent])

        # 保留部分 = 最近 N 条
        kept = all_messages[-self.keep_recent:]

        new_summary = self.summarize(to_compress)
        if new_summary:
            new_summary = f"[历史摘要] {new_summary}"

        return new_summary, kept

    def build_llm_messages(
        self,
        system_prompt: str,
        history_messages: list[dict],
        summary: Optional[str],
        user_input: str
    ) -> list[dict]:
        """
        构建发送给 LLM 的完整 messages 列表

        结构：
            [system_prompt, (summary_msg), ...history, user_input]

        Args:
            system_prompt: 系统提示词
            history_messages: 最近的原始历史消息
            summary: 历史摘要（若有）
            user_input: 当前用户输入

        Returns:
            LLM messages 列表
        """
        msgs = [{"role": "system", "content": system_prompt}]

        # 摘要放在 system 之后、历史之前
        if summary:
            msgs.append({"role": "system", "content": summary})

        # 历史对话
        msgs.extend(history_messages)

        # 当前用户输入
        msgs.append({"role": "user", "content": user_input})

        return msgs

    @staticmethod
    def _format_messages(messages: list[dict]) -> str:
        """将消息列表格式化为可读文本"""
        lines = []
        role_map = {"user": "用户", "assistant": "助手", "system": "系统"}
        for msg in messages:
            role = role_map.get(msg.get("role", ""), msg.get("role", ""))
            lines.append(f"{role}: {msg.get('content', '')}")
        return "\n".join(lines)
