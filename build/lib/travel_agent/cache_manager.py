# -*- coding: utf-8 -*-
"""
长期记忆存储管理器（SQLite）

将城市资源缓存和对话历史持久化到 SQLite 数据库，
支持跨会话复用已查询的城市资源，以及同一会话内的记忆累积。

数据库位置：{项目根}/data/travel_memory.db

表结构：
    city_resources  — 城市资源缓存（按城市+资源key隔离）
    chat_history    — 对话历史长期记忆（按会话隔离）
"""

import sqlite3
import threading
import json
import re
import difflib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# 数据库路径（项目根/data/travel_memory.db）
_DB_PATH = Path(__file__).parent.parent / "data" / "travel_memory.db"

# 线程锁（防止并行节点同时写入冲突）
_write_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    """获取 SQLite 连接（启用外键、行工厂、busy_timeout）"""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # WAL 模式提升并发读写性能
    conn.execute("PRAGMA busy_timeout=5000")  # 写锁等待 5 秒，避免立即报 locked
    return conn


def _serialize_value(value) -> str:
    """
    将任意值序列化为可存入 SQLite 的字符串

    字符串直接返回；list/dict/bool/int 等序列化为 JSON。

    Args:
        value: 待序列化的值

    Returns:
        字符串形式（可直接存入 SQLite TEXT 列）
    """
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _deserialize_value(value: str):
    """
    尝试将存储的字符串反序列化为原始类型

    字符串形式的 JSON 会恢复为 list/dict 等；普通文本保持原样。

    Args:
        value: SQLite 中存储的字符串

    Returns:
        原始值（可能是 str/list/dict/bool 等）
    """
    if not isinstance(value, str):
        return value
    # 尝试 JSON 反序列化（恢复 list/dict 等结构）
    if value.startswith(("[", "{", "true", "false")):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value
    return value


def _init_db() -> None:
    """初始化数据库表"""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS city_resources (
            city           TEXT NOT NULL,
            resource_key   TEXT NOT NULL,
            resource_value TEXT NOT NULL,
            updated_at     TEXT,
            PRIMARY KEY (city, resource_key)
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS qa_cache (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            query_text       TEXT NOT NULL,
            normalized_query TEXT NOT NULL,
            city             TEXT,
            intent           TEXT NOT NULL,
            answer           TEXT NOT NULL,
            created_at       TEXT NOT NULL,
            expire_at        TEXT NOT NULL,
            hit_count        INTEGER DEFAULT 0,
            UNIQUE (city, intent, normalized_query)
        );

        CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id);
        CREATE INDEX IF NOT EXISTS idx_city ON city_resources(city);
        CREATE INDEX IF NOT EXISTS idx_qa_lookup ON qa_cache(city, intent, normalized_query);
        CREATE INDEX IF NOT EXISTS idx_qa_expire ON qa_cache(expire_at);
    """)
    conn.commit()
    conn.close()


# 模块加载时初始化
_init_db()


# ========== 城市资源缓存 CRUD ==========


def update_city_cache(city: str, resources: dict) -> None:
    """
    增量更新单个城市的缓存并落盘

    非 str 类型的值（如 list/dict）会自动序列化为 JSON 字符串存储。
    使用 try-finally 确保连接关闭，避免锁泄漏。

    Args:
        city: 城市名
        resources: 该城市的资源字典 {resource_key: resource_value}
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _write_lock:
        conn = _get_conn()
        try:
            for key, value in resources.items():
                conn.execute(
                    """INSERT INTO city_resources (city, resource_key, resource_value, updated_at)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(city, resource_key)
                       DO UPDATE SET resource_value=excluded.resource_value, updated_at=excluded.updated_at""",
                    (city, key, _serialize_value(value), now)
                )
            conn.commit()
        finally:
            conn.close()


def get_city_cache(city: str) -> Optional[dict]:
    """
    获取单个城市的缓存资源

    存储时序列化的值会自动反序列化恢复为原始类型（list/dict 等）。

    Args:
        city: 城市名

    Returns:
        城市资源字典，不存在则返回 None
    """
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT resource_key, resource_value FROM city_resources WHERE city=?",
            (city,)
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return None
    return {row["resource_key"]: _deserialize_value(row["resource_value"]) for row in rows}


def load_all_cache() -> dict[str, dict[str, str]]:
    """
    加载所有城市缓存

    Returns:
        {城市: {资源key: 资源value}}
    """
    conn = _get_conn()
    rows = conn.execute(
        "SELECT city, resource_key, resource_value FROM city_resources"
    ).fetchall()
    conn.close()

    cache: dict[str, dict[str, str]] = {}
    for row in rows:
        city = row["city"]
        if city not in cache:
            cache[city] = {}
        cache[city][row["resource_key"]] = row["resource_value"]
    return cache


def clear_cache() -> None:
    """清空所有城市资源缓存"""
    with _write_lock:
        conn = _get_conn()
        conn.execute("DELETE FROM city_resources")
        conn.commit()
        conn.close()


def remove_city_cache(city: str) -> None:
    """删除指定城市的缓存"""
    with _write_lock:
        conn = _get_conn()
        conn.execute("DELETE FROM city_resources WHERE city=?", (city,))
        conn.commit()
        conn.close()


# ========== 对话历史长期记忆 CRUD ==========


def save_chat_message(session_id: str, role: str, content: str) -> None:
    """
    保存单条对话消息到长期记忆

    Args:
        session_id: 会话ID
        role: 消息角色（user/assistant）
        content: 消息内容
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _write_lock:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO chat_history (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now)
        )
        conn.commit()
        conn.close()


def save_chat_batch(session_id: str, messages: list[dict]) -> None:
    """
    批量保存对话消息（增量保存，跳过已存在的）

    Args:
        session_id: 会话ID
        messages: 消息列表 [{role, content}, ...]
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _write_lock:
        conn = _get_conn()
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if not content:
                continue
            # 去重：检查是否已存在相同 session+role+content
            exists = conn.execute(
                "SELECT 1 FROM chat_history WHERE session_id=? AND role=? AND content=? LIMIT 1",
                (session_id, role, content)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO chat_history (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                    (session_id, role, content, now)
                )
        conn.commit()
        conn.close()


def load_chat_history(session_id: str, limit: int = 50) -> list[dict]:
    """
    加载指定会话的对话历史

    Args:
        session_id: 会话ID
        limit: 最大返回条数

    Returns:
        消息列表 [{role, content, created_at}, ...]
    """
    conn = _get_conn()
    rows = conn.execute(
        "SELECT role, content, created_at FROM chat_history WHERE session_id=? ORDER BY id ASC LIMIT ?",
        (session_id, limit)
    ).fetchall()
    conn.close()
    return [{"role": row["role"], "content": row["content"],
             "created_at": row["created_at"]} for row in rows]


def clear_chat_history(session_id: str) -> None:
    """清空指定会话的对话历史"""
    with _write_lock:
        conn = _get_conn()
        conn.execute("DELETE FROM chat_history WHERE session_id=?", (session_id,))
        conn.commit()
        conn.close()


# ========== 问答结果缓存（按城市+意图+相似度匹配）==========


def _normalize_query(query: str) -> str:
    """
    归一化查询文本，用于相似度匹配

    去除多余空格、标点符号和常见语气词，保留核心关键词。
    """
    # 统一小写并去除首尾空格
    text = query.lower().strip()
    # 去除标点符号
    text = re.sub(r"[？?！!。，,、；;：:\.\"'\"'()（）\[\]【】]", "", text)
    # 去除常见语气词与无意义词（中文无词边界，直接全局替换）
    text = re.sub(r"(怎么样|怎么|怎样|吗|呢|吧|啊|嗯|请问|一下|查询|查一下|给我|帮我|我想知道|告诉我|推荐|有哪些|有什么)", "", text)
    # 合并多余空格
    text = re.sub(r"\s+", "", text)
    return text


def _compute_similarity(a: str, b: str) -> float:
    """计算两段文本的相似度，返回 0~1 之间的浮点数"""
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _get_ttl_hours(intent: str) -> int:
    """根据意图类型返回缓存有效期（小时）"""
    if intent == "query_weather":
        return 3
    return 24


def save_qa_cache(query: str, city: Optional[str], intent: str, answer: str) -> None:
    """
    保存问答结果到缓存

    天气类缓存 3 小时，其他缓存 1 天。同一 (city, intent, normalized_query)
    已存在时会覆盖为最新结果。

    Args:
        query: 用户原始问题
        city: 关联城市（可能为 None）
        intent: 意图类型
        answer: 最终返回给用户的答案文本
    """
    now = datetime.now()
    ttl = _get_ttl_hours(intent)
    expire = now + timedelta(hours=ttl)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    expire_str = expire.strftime("%Y-%m-%d %H:%M:%S")
    normalized = _normalize_query(query)

    with _write_lock:
        conn = _get_conn()
        try:
            # 清理过期缓存，避免脏数据堆积
            conn.execute("DELETE FROM qa_cache WHERE expire_at <= ?", (now_str,))
            # 先删除同 city+intent+normalized_query 的旧记录，再插入新记录
            conn.execute(
                "DELETE FROM qa_cache WHERE city = ? AND intent = ? AND normalized_query = ?",
                (city or "", intent, normalized)
            )
            conn.execute(
                """INSERT INTO qa_cache (query_text, normalized_query, city, intent, answer, created_at, expire_at, hit_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                (query, normalized, city or "", intent, answer, now_str, expire_str)
            )
            conn.commit()
        finally:
            conn.close()


def get_qa_cache(query: str, city: Optional[str], intent: str,
                 similarity_threshold: float = 0.9) -> Optional[str]:
    """
    按城市+意图+相似度查找缓存答案

    先在相同 (city, intent) 下查找未过期的缓存记录，再使用 difflib
    计算 normalized query 的相似度，达到阈值则返回缓存答案并增加命中计数。

    Args:
        query: 当前用户问题
        city: 关联城市
        intent: 意图类型
        similarity_threshold: 相似度阈值（默认 0.9）

    Returns:
        缓存的答案文本；未命中或已过期则返回 None
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    normalized = _normalize_query(query)
    target_city = city or ""

    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT id, query_text, normalized_query, answer, expire_at
               FROM qa_cache
               WHERE city = ? AND intent = ? AND expire_at > ?
               ORDER BY created_at DESC""",
            (target_city, intent, now_str)
        ).fetchall()
    finally:
        conn.close()

    for row in rows:
        sim = _compute_similarity(normalized, row["normalized_query"])
        if sim >= similarity_threshold:
            # 命中：更新命中次数
            with _write_lock:
                conn = _get_conn()
                try:
                    conn.execute(
                        "UPDATE qa_cache SET hit_count = hit_count + 1 WHERE id = ?",
                        (row["id"],)
                    )
                    conn.commit()
                finally:
                    conn.close()
            return row["answer"]
    return None


def clear_qa_cache(city: Optional[str] = None, intent: Optional[str] = None) -> None:
    """
    清空问答缓存

    Args:
        city: 仅清空指定城市的缓存；为 None 时清空全部
        intent: 仅清空指定意图的缓存；为 None 时忽略
    """
    with _write_lock:
        conn = _get_conn()
        try:
            sql = "DELETE FROM qa_cache WHERE 1=1"
            params = []
            if city is not None:
                sql += " AND city = ?"
                params.append(city)
            if intent is not None:
                sql += " AND intent = ?"
                params.append(intent)
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()
