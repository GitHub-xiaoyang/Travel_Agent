# -*- coding: utf-8 -*-
"""
Travel Agent — 豆包风格聊天界面

启动方式：
    python -m streamlit run travel_agent/frontend/main_app.py

设计参考：豆包网页版
- 左侧边栏（浅灰色）：品牌区 + 新建对话 + 历史会话 + 底部
- 主内容区（白色）：欢迎页 / 对话气泡 / 底部输入栏
- 配色：白色底 #FFFFFF / 浅灰 #F2F3F5 / 蓝色强调 #4C6FFF
"""

import sys
import os
import uuid
import json
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import settings
import streamlit.components.v1 as components

# 共享常量：统一降级逻辑
from travel_agent.nodes.constants import check_degrade
from travel_agent.utils.image_renderer import render_markdown_to_png, render_markdown_to_pdf

# ========== 1. 页面配置（必须第一） ==========
import streamlit as st

st.set_page_config(
    page_title="Travel Agent — 智能旅行助手",
    page_icon="🧳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== 2. 全局样式 ==========
st.markdown("""
<style>
    /* ---------- 基础配色 ---------- */
    :root {
        --doubao-bg: #F2F3F5;
        --doubao-sidebar: #F7F8FA;
        --doubao-white: #FFFFFF;
        --doubao-accent: #4C6FFF;
        --doubao-accent-hover: #3D5AE6;
        --doubao-text: #1F2329;
        --doubao-text-secondary: #646A73;
        --doubao-border: #E5E6EB;
        --doubao-user-bubble: #E8F0FF;
        --doubao-ai-bubble: #F2F3F5;
        --doubao-success: #00B42A;
        --doubao-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
    }

    /* ---------- 全局 ---------- */
    .stApp {
        background-color: var(--doubao-white);
    }
    .block-container {
        padding-top: 0;
        padding-bottom: 0;
        max-width: 100% !important;
    }

    /* ---------- 侧边栏 ---------- */
    [data-testid="stSidebar"] {
        background-color: var(--doubao-sidebar);
        border-right: 1px solid var(--doubao-border);
    }
    [data-testid="stSidebar"] .block-container {
        padding-top: 12px;
    }

    /* ---------- 欢迎页 ---------- */
    .welcome-hero {
        text-align: center;
        padding: 100px 20px 32px;
    }
    .welcome-hero .logo {
        font-size: 56px;
        margin-bottom: 12px;
    }
    .welcome-hero h1 {
        font-size: 28px;
        font-weight: 700;
        color: var(--doubao-text);
        margin-bottom: 6px;
    }
    .welcome-hero p {
        font-size: 15px;
        color: var(--doubao-text-secondary);
        margin-bottom: 0;
    }

    /* ---------- 推荐卡片网格 ---------- */
    .recommend-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 10px;
        max-width: 640px;
        margin: 32px auto 0;
        padding: 0 16px;
    }
    .recommend-card {
        background: var(--doubao-white);
        border: 1px solid var(--doubao-border);
        border-radius: 12px;
        padding: 14px 16px;
        cursor: pointer;
        transition: all 0.2s;
        text-align: left;
    }
    .recommend-card:hover {
        border-color: var(--doubao-accent);
        box-shadow: var(--doubao-shadow);
        transform: translateY(-1px);
    }
    .recommend-card .title {
        font-size: 14px;
        font-weight: 600;
        color: var(--doubao-text);
        margin-bottom: 4px;
    }
    .recommend-card .desc {
        font-size: 12px;
        color: var(--doubao-text-secondary);
        line-height: 1.4;
    }

    /* ---------- 消息气泡 ---------- */
    .chat-msg {
        font-size: 15px;
        line-height: 1.6;
        margin: 4px 0;
    }
    .chat-msg-user {
        display: inline-block;
        background: #F2F3F5;
        border-radius: 16px 16px 4px 16px;
        color: var(--doubao-text);
        padding: 10px 20px;
        max-width: 70%;
        min-width: 10%;
        width: fit-content;
        word-wrap: break-word;
    }
    .chat-msg-assistant {
        background: transparent;
        color: var(--doubao-text);
        padding: 4px 0;
    }
    .chat-user-wrap {
        text-align: right;
    }
    .tool-badge-user {
        text-align: right;
    }

    /* ---------- 工具调用徽章 ---------- */
    .tool-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 3px 10px;
        background: #E8F0FF;
        color: var(--doubao-accent);
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
        margin-bottom: 8px;
    }

    /* ---------- 行程结果卡片 ---------- */
    .plan-card {
        background: linear-gradient(135deg, #FFF5F5 0%, #F0F5FF 100%);
        border: 1px solid #FFE0E0;
        border-radius: 16px;
        padding: 24px;
        margin: 16px 0;
    }
    .plan-card h2 {
        color: #E65A5A;
        margin-bottom: 12px;
    }

    /* ---------- 输入框 ---------- */
    [data-testid="stChatInput"] {
        border: 2px solid var(--doubao-border) !important;
        border-radius: 20px !important;
        padding: 8px 16px !important;
        transition: border-color 0.2s !important;
    }
    [data-testid="stChatInput"]:focus-within {
        border-color: var(--doubao-accent) !important;
        box-shadow: 0 0 0 3px rgba(76, 111, 255, 0.1) !important;
    }

    /* ---------- 按钮 ---------- */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.15s;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
    }
    .stButton[kind="primary"] > button {
        background: var(--doubao-accent);
        border: none;
    }
    .stButton[kind="primary"] > button:hover {
        background: var(--doubao-accent-hover);
    }

    /* ---------- 会话列表 ---------- */
    .session-item {
        display: flex;
        align-items: center;
        padding: 8px 12px;
        border-radius: 8px;
        cursor: pointer;
        transition: background 0.15s;
        margin-bottom: 2px;
    }
    .session-item:hover {
        background: rgba(76, 111, 255, 0.08);
    }
    .session-item.active {
        background: var(--doubao-white);
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    }
    .session-item .title {
        flex: 1;
        font-size: 14px;
        color: var(--doubao-text);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .session-item .time {
        font-size: 11px;
        color: var(--doubao-text-secondary);
    }

    /* ---------- 侧边栏分区标题 ---------- */
    .sidebar-section-title {
        font-size: 13px;
        font-weight: 600;
        color: var(--doubao-text-secondary);
        padding: 6px 4px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        cursor: pointer;
    }
    .sidebar-section-title .arrow {
        transition: transform 0.2s;
        font-size: 10px;
    }
    .sidebar-section-title .arrow.collapsed {
        transform: rotate(-90deg);
    }

    /* ---------- 滚动条 ---------- */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-thumb {
        background: #C9CDD4;
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #A9AFB8;
    }
    ::-webkit-scrollbar-track {
        background: transparent;
    }

    /* ---------- 指标卡 ---------- */
    .stMetric {
        background: var(--doubao-white);
        border-radius: 12px;
        padding: 12px;
        border: 1px solid var(--doubao-border);
    }

    /* ---------- 分隔线 ---------- */
    hr {
        border-color: var(--doubao-border);
        margin: 12px 0;
    }

    /* ---------- 对话区容器 ---------- */
    .chat-area {
        max-width: 820px;
        margin: 0 auto;
        padding: 24px 16px 120px;
    }
    .welcome-container {
        max-width: 820px;
        margin: 0 auto;
        padding: 24px 16px;
    }
</style>
""", unsafe_allow_html=True)

# ========== 3. 状态初始化 ==========
if "sessions" not in st.session_state:
    st.session_state.sessions = {}
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "chat_agent" not in st.session_state:
    from travel_agent.chat_agent import ChatAgent
    st.session_state.chat_agent = ChatAgent()
if "chat_context" not in st.session_state:
    st.session_state.chat_context = {
        "city": "", "days": "", "crowd": "",
        "query": "", "travel_time": "", "style": "简约干货"
    }
if "graph" not in st.session_state:
    from travel_agent import get_compiled_graph
    st.session_state.graph = get_compiled_graph()

# 全局定位状态（设备级，与历史会话/出行规划完全解耦）
# 只随开关操作和搜索确认改变，不随会话新建/切换/删除或规划增删而改变
if "user_location" not in st.session_state:
    st.session_state.user_location = {
        "current_location": "", "current_city": "",
        "current_location_detail": "", "current_location_lng": "",
        "current_location_lat": ""
    }

# 侧边栏折叠状态
if "collapse_history" not in st.session_state:
    st.session_state.collapse_history = False


def _render_bubble(
    content: str,
    is_user: bool = False,
    action_label: str = "",
    tool_result: str = "",
    plan_md: str = "",
    extra_html: str = ""
) -> None:
    """
    渲染聊天气泡（一次性完整 HTML，确保内容在气泡 div 内）

    Args:
        content: 气泡主要文本内容
        is_user: 是否为用户消息（右侧蓝色气泡）
        action_label: 工具/意图标签（如"天气查询"）
        tool_result: 工具返回详情（用 <details> 折叠显示）
        plan_md: 行程 Markdown（用卡片样式显示）
        extra_html: 额外 HTML 内容
    """
    bubble_class = "chat-msg-user" if is_user else "chat-msg-assistant"

    # 工具徽章
    badge_html = ""
    if action_label:
        badge_html = f'<div class="tool-badge{" tool-badge-user" if is_user else ""}">🔧 {action_label}</div>'

    # 工具返回详情（HTML details 替代 st.expander）
    tool_detail_html = ""
    if tool_result:
        tool_detail_html = f"""<details style="margin-top:8px;">
<summary style="cursor:pointer;color:#646A73;font-size:13px;">🔍 工具返回详情</summary>
<pre style="background:#F7F8FA;padding:8px 12px;border-radius:8px;font-size:12px;white-space:pre-wrap;margin-top:4px;">{tool_result}</pre>
</details>"""

    # 行程卡片
    plan_html = ""
    if plan_md:
        plan_html = f"""<div class="plan-card" style="margin-top:12px;">
{plan_md}
</div>"""

    # 完整气泡 HTML
    full_html = f"""<div class="chat-msg {bubble_class}">
{badge_html}
{content}
{tool_detail_html}
{plan_html}
{extra_html}
</div>"""

    # 用对应列渲染（用户消息外面包一层右对齐容器）
    if is_user:
        cols = st.columns([1, 4])
        with cols[1]:
            st.markdown(
                f'<div class="chat-user-wrap">{full_html}</div>',
                unsafe_allow_html=True
            )
    else:
        cols = st.columns([4, 1])
        with cols[0]:
            st.markdown(full_html, unsafe_allow_html=True)


def _stream_render(content: str, action_label: str = "", is_plan: bool = False) -> None:
    """
    流式渲染：打字机效果逐字显示内容

    Args:
        content: 要渲染的文本内容
        action_label: 意图标签（如"完整行程规划"）
        is_plan: 是否为行程卡片
    """
    import time

    # 构建 HTML 容器（与 _render_bubble 结构一致）
    badge_html = ""
    if action_label:
        badge_html = f'<div class="tool-badge">🔧 {action_label}</div>'

    if is_plan:
        # 行程卡片：显示加载动画后整体渲染
        cols = st.columns([4, 1])
        with cols[0]:
            placeholder = st.empty()
            placeholder.markdown(
                f'{badge_html}<div style="padding:20px;color:#646A73;">⏳ 正在生成行程方案…</div>',
                unsafe_allow_html=True
            )
            time.sleep(0.3)  # 轻微延迟营造流式感
            placeholder.empty()
            # 完整渲染行程卡片
            full_html = f'{badge_html}<div class="plan-card" style="margin-top:12px;">{content}</div>'
            placeholder.markdown(full_html, unsafe_allow_html=True)
    else:
        # 普通文本：逐字流式显示
        cols = st.columns([4, 1])
        with cols[0]:
            placeholder = st.empty()
            displayed = ""
            for char in content:
                displayed += char
                placeholder.markdown(
                    f'{badge_html}<div style="padding:12px;">{displayed}</div>',
                    unsafe_allow_html=True
                )
                time.sleep(0.01)  # 打字机速度
            # 最终渲染
            placeholder.empty()
            full_html = f'{badge_html}<div style="padding:12px;">{content}</div>'
            st.markdown(full_html, unsafe_allow_html=True)


def _new_session() -> str:
    """创建新会话，返回会话ID。

    定位是全局设备级状态（st.session_state.user_location），
    与会话完全解耦，此处不触碰任何定位状态。
    """
    sid = str(uuid.uuid4())[:8]
    st.session_state.sessions[sid] = {
        "id": sid,
        "title": "新对话",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "messages": [],
        "context": {
            "city": "", "days": "", "crowd": "",
            "query": "", "travel_time": "", "style": "简约干货"
        },
        "last_plan": None,  # 保存上次行程数据，支持多轮循环优化
        "last_resource_cache": {},  # 会话级资源缓存累积（同一会话内多轮复用）
        "summary": None,  # 会话级历史摘要（滑动窗口+摘要压缩）
        "raw_history": [],  # 原始对话历史 [{role, content}, ...]（供记忆管理器使用）
    }
    st.session_state.current_session_id = sid
    st.session_state.chat_context = st.session_state.sessions[sid]["context"]
    return sid


# 优化需求关键词（用于检测用户是否想优化已有行程）
_OPTIMIZE_KEYWORDS = [
    "优化", "调整", "改一下", "改改", "少走路", "省钱", "换个",
    "太累", "紧凑", "松散", "去掉", "增加", "不要", "换成",
    "太赶", "轻松", "多安排", "少安排", "重新排",
]


def _is_optimize_request(prompt: str, current: dict) -> bool:
    """检测是否为对已有行程的优化需求"""
    if not current.get("last_plan"):
        return False
    return any(kw in prompt for kw in _OPTIMIZE_KEYWORDS)


def _get_current_session() -> dict | None:
    """获取当前会话数据"""
    sid = st.session_state.current_session_id
    if sid and sid in st.session_state.sessions:
        return st.session_state.sessions[sid]
    return None


def _save_session(session: dict):
    """保存会话"""
    sid = session["id"]
    st.session_state.sessions[sid] = session


def _render_sidebar_section(title: str, icon: str, state_key: str) -> bool:
    """渲染侧边栏可折叠分区标题，返回是否展开"""
    collapsed = st.session_state[state_key]
    arrow = "▼" if not collapsed else "▶"
    btn_label = f"{icon}  {title}  {arrow}"
    if st.button(
        btn_label,
        key=f"toggle_{state_key}",
        use_container_width=True,
        help=f"点击折叠/展开 {title}"
    ):
        st.session_state[state_key] = not collapsed
        st.rerun()
    return not collapsed


def _build_location_panel_html(
    amap_key: str,
    amap_security_code: str = "",
    initial_lng=None,
    initial_lat=None,
    initial_label: str = "",
    initial_detail: str = "",
    title: str = "📍 精准定位",
    show_cancel: bool = True,
    panel_height: int = 540,
) -> str:
    """构建定位/预览面板 HTML（含地图、地址搜索、确认按钮）。

    无 initial_lng：定位流程模式（GPS 定位 + 搜索）。
    有 initial_lng：预览模式，直接渲染已保存位置，仍可搜索新地址并确认更新。
    """
    # 经纬度校验：非法则降级为定位模式
    lng_num = 0.0
    lat_num = 0.0
    has_initial = False
    if initial_lng and initial_lat:
        try:
            lng_num = float(initial_lng)
            lat_num = float(initial_lat)
            has_initial = True
        except (TypeError, ValueError):
            has_initial = False

    init_flag = "true" if has_initial else "false"

    def _js_escape(s: str) -> str:
        """转义 JS 字符串中的特殊字符，防止破坏注入。"""
        return (s or "").replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"').replace("\n", " ")

    init_label_js = _js_escape(initial_label) if has_initial else ""
    init_detail_js = _js_escape(initial_detail) if has_initial else ""
    cancel_display = "" if show_cancel else "display:none;"

    return f"""<div style="width:100%;height:{panel_height}px;font-family:sans-serif;overflow:hidden;">
            <div style="background:#fff;border-radius:10px;border:1px solid #E5E6EB;width:100%;height:100%;box-sizing:border-box;">
                <div style="padding:12px 14px 8px;border-bottom:1px solid #E5E6EB;display:flex;justify-content:space-between;align-items:center;">
                    <div style="font-size:14px;font-weight:600;color:#1F2329;">{title}</div>
                    <div id="loc_cancel" style="cursor:pointer;font-size:16px;color:#646A73;{cancel_display}">&times;</div>
                </div>
                <div style="padding:8px 10px;">
                    <input id="search_input" type="text" placeholder="🔍 搜索地址（如：平安小区）"
                        style="width:100%;padding:7px 10px;border:1px solid #E5E6EB;border-radius:6px;font-size:12px;outline:none;box-sizing:border-box;"
                        autocomplete="off">
                    <div id="search_suggestions" style="max-height:120px;overflow-y:auto;border:1px solid #E5E6EB;border-radius:6px;margin-top:3px;background:#fff;display:none;"></div>
                    <div style="font-size:10px;color:#86909C;margin-top:3px;">💡 输入地址名、小区名，点击建议定位</div>
                </div>
                <div id="loc_map" style="width:100%;height:200px;background:#F2F3F5;"></div>
                <div style="padding:8px 10px;border-top:1px solid #E5E6EB;">
                    <div id="loc_addr" style="font-size:12px;color:#1F2329;margin-bottom:3px;min-height:18px;">初始化中...</div>
                    <div id="loc_acc" style="font-size:11px;color:#646A73;margin-bottom:8px;"></div>
                    <button id="loc_confirm" style="width:100%;padding:7px;background:#C9CDD4;color:#fff;border:none;border-radius:5px;font-size:13px;font-weight:500;cursor:not-allowed;" disabled>确认位置</button>
                </div>
            </div>
        </div>
        <script>
        (function() {{
            // 确认 JS 正在执行
            document.getElementById('loc_addr').innerHTML = 'JS已执行，地图加载中...';

            var HAS_INITIAL = {init_flag};
            var INIT_LNG = {lng_num};
            var INIT_LAT = {lat_num};
            var INIT_LABEL = "{init_label_js}";
            var INIT_DETAIL = "{init_detail_js}";

            var map = null;
            var marker = null;
            var labelMarker = null;
            var locData = null;
            var currentPoiName = '';
            var autoComplete = null;
            var placeSearch = null;
            var geocoder = null;

            /**
             * 更新地图 UI：标记 + 地址标签 + 中心点
             */
            function updateUI(lng, lat, acc, addr, prov, city, dist, twn, street, number) {{
                locData = {{
                    lng: lng, lat: lat, acc: acc, addr: addr,
                    prov: prov, city: city, dist: dist, twn: twn,
                    street: street, number: number
                }};
                var displayName = currentPoiName || addr || '';
                var addrStr = addr;
                if (!addrStr) {{
                    var parts = [prov, city, dist, twn];
                    if (street) parts.push(street + (number ? number + '号' : ''));
                    addrStr = parts.filter(function(x){{return x;}}).join('');
                }}
                if (!displayName) displayName = addrStr || '当前位置';
                document.getElementById('loc_addr').innerHTML = displayName;
                document.getElementById('loc_acc').innerHTML = acc ? '精度 ±' + acc + ' 米' : '';

                if (!map) {{
                    map = new AMap.Map('loc_map', {{
                        zoom: 16, center: [lng, lat], viewMode: '2D'
                    }});
                }} else {{
                    map.setZoomAndCenter(16, [lng, lat]);
                }}
                if (marker) map.remove(marker);
                if (labelMarker) map.remove(labelMarker);
                marker = new AMap.Marker({{ position: [lng, lat], title: displayName }});
                map.add(marker);
                labelMarker = new AMap.Text({{
                    text: displayName, position: [lng, lat],
                    offset: new AMap.Pixel(0, -32),
                    style: {{
                        'background': '#fff', 'border': '1px solid #4C6FFF',
                        'border-radius': '3px', 'padding': '1px 6px',
                        'font-size': '11px', 'color': '#1F2329', 'white-space': 'nowrap'
                    }}
                }});
                map.add(labelMarker);
                var btn = document.getElementById('loc_confirm');
                // 地址未变化时置灰（预览模式下与初始位置相同），变化时启用
                var sameAsInitial = HAS_INITIAL && Math.abs(parseFloat(lng) - INIT_LNG) < 0.000001 && Math.abs(parseFloat(lat) - INIT_LAT) < 0.000001;
                if (sameAsInitial) {{
                    btn.disabled = true;
                    btn.style.background = '#C9CDD4';
                    btn.style.cursor = 'not-allowed';
                }} else {{
                    btn.disabled = false;
                    btn.style.background = '#4C6FFF';
                    btn.style.cursor = 'pointer';
                }}
                btn.innerHTML = '确认位置';
            }}

            /**
             * 逆地理编码
             */
            function reverseGeocode(lng, lat, callback) {{
                if (typeof AMap.Geocoder === 'undefined') {{ callback('', '', '', '', '', '', ''); return; }}
                if (!geocoder) geocoder = new AMap.Geocoder({{ city: '全国' }});
                geocoder.getAddress([lng, lat], function(status, result) {{
                    if (status === 'complete' && result.regeocode) {{
                        var ac = result.regeocode.addressComponent || {{}};
                        var sn = ac.streetNumber || {{}};
                        callback(result.regeocode.formattedAddress || '',
                            ac.province || '', ac.city || '', ac.district || '',
                            ac.township || '', sn.street || '', sn.number || '');
                    }} else {{
                        callback('', '', '', '', '', '', '');
                    }}
                }});
            }}

            /**
             * 处理搜索选中
             */
            function handleSearchSelect(poi) {{
                currentPoiName = poi.name || '';
                var lng = poi.location ? poi.location.lng : 0;
                var lat = poi.location ? poi.location.lat : 0;
                if (!lng || !lat) return;
                document.getElementById('loc_addr').innerHTML = '正在更新...';
                // 如果有 POI 自带的地址信息，用作降级
                var fallbackAddr = poi.address || '';
                var fallbackDistrict = poi.district || '';
                reverseGeocode(lng, lat, function(addr, p, c, d, twn, st, num) {{
                    var fullAddr = addr || fallbackAddr || currentPoiName;
                    if (currentPoiName && addr && addr.indexOf(currentPoiName) === -1) {{
                        fullAddr = currentPoiName + '(' + addr + ')';
                    }}
                    updateUI(lng, lat, 0, fullAddr, p, c, d || fallbackDistrict, twn, st, num);
                }});
            }}

            /**
             * 初始化地址搜索（定位/预览模式共用）
             * 优先使用 AMap.Autocomplete，降级使用 AMap.PlaceSearch
             */
            var searchMode = '';  // 'autocomplete' | 'placesearch'
            function initSearch() {{
                var searchInput = document.getElementById('search_input');
                var suggestionsBox = document.getElementById('search_suggestions');
                var debounceTimer = null;

                // 检查可用的搜索插件（优先 PlaceSearch，因为 Autocomplete 的 inputtips API 可能未开通）
                var hasPlaceSearch = typeof AMap.PlaceSearch !== 'undefined';
                var hasAutocomplete = typeof AMap.Autocomplete !== 'undefined' || typeof AMap.AutoComplete !== 'undefined';

                if (hasPlaceSearch) {{
                    searchMode = 'placesearch';
                    searchInput.placeholder = '🔍 输入地址或地名搜索（如：北京、平安小区）';
                }} else if (hasAutocomplete) {{
                    searchMode = 'autocomplete';
                    searchInput.placeholder = '🔍 输入地址搜索（如：平安小区）';
                }} else {{
                    searchInput.placeholder = '搜索不可用，请直接在地图上选点';
                    searchInput.disabled = true;
                    return;
                }}

                searchInput.addEventListener('input', function() {{
                    clearTimeout(debounceTimer);
                    var keyword = searchInput.value.trim();
                    if (!keyword) {{ suggestionsBox.style.display = 'none'; return; }}
                    debounceTimer = setTimeout(function() {{
                        // 立即显示搜索中状态
                        suggestionsBox.innerHTML = '<div style="padding:8px;color:#86909C;font-size:11px;text-align:center;">🔍 搜索中...</div>';
                        suggestionsBox.style.display = 'block';
                        try {{
                            if (searchMode === 'autocomplete') {{
                                // Autocomplete 模式
                                var ACtor = AMap.Autocomplete || AMap.AutoComplete;
                                if (!autoComplete) autoComplete = new ACtor({{ city: '全国', citylimit: false }});
                                autoComplete.search(keyword, function(status, result) {{
                                    if (status === 'complete' && result.tips && result.tips.length > 0) {{
                                        var html = '';
                                        var validTips = [];
                                        result.tips.forEach(function(tip) {{
                                            if (!tip.location) return;
                                            var subText = (tip.district || '') + (tip.address ? ' · ' + tip.address : '');
                                            html += '<div class="sug-item" data-idx="' + validTips.length + '" style="padding:6px 10px;cursor:pointer;border-bottom:1px solid #F2F3F5;font-size:12px;" onmouseover="this.style.background=\\'#F2F3F5\\'" onmouseout="this.style.background=\\'\\'">';
                                            html += '<div style="font-weight:500;color:#1F2329;">' + (tip.name || '未知') + '</div>';
                                            if (subText) html += '<div style="font-size:10px;color:#86909C;">' + subText + '</div>';
                                            html += '</div>';
                                            validTips.push(tip);
                                        }});
                                        suggestionsBox.innerHTML = html || '<div style="padding:8px;color:#86909C;font-size:11px;text-align:center;">未找到匹配地址</div>';
                                        suggestionsBox.style.display = 'block';
                                        var items = suggestionsBox.querySelectorAll('.sug-item');
                                        for (var i = 0; i < items.length; i++) {{
                                            (function(item, idx) {{
                                                item.addEventListener('click', function(e) {{
                                                    e.stopPropagation();
                                                    searchInput.value = validTips[idx].name;
                                                    suggestionsBox.style.display = 'none';
                                                    handleSearchSelect(validTips[idx]);
                                                }});
                                            }})(items[i], parseInt(items[i].getAttribute('data-idx')));
                                        }}
                                    }} else {{
                                        var errInfo = (result && result.info) ? result.info : '未找到';
                                        suggestionsBox.innerHTML = '<div style="padding:8px;color:#86909C;font-size:11px;text-align:center;">' + errInfo + '</div>';
                                        suggestionsBox.style.display = 'block';
                                    }}
                                }});
                            }} else {{
                                // PlaceSearch 降级模式
                                if (!placeSearch) placeSearch = new AMap.PlaceSearch({{ city: '全国', citylimit: false }});
                                placeSearch.search(keyword, function(status, result) {{
                                    if (status === 'complete' && result.poiList && result.poiList.pois && result.poiList.pois.length > 0) {{
                                        var html = '';
                                        var validPois = [];
                                        result.poiList.pois.forEach(function(poi) {{
                                            var lng = poi.location ? poi.location.lng : 0;
                                            var lat = poi.location ? poi.location.lat : 0;
                                            if (!lng || !lat) return;
                                            var subText = (poi.pname || '') + (poi.cityname ? ' · ' + poi.cityname : '') + (poi.adname ? ' · ' + poi.adname : '');
                                            if (poi.address) subText += ' · ' + poi.address;
                                            html += '<div class="sug-item" data-idx="' + validPois.length + '" style="padding:6px 10px;cursor:pointer;border-bottom:1px solid #F2F3F5;font-size:12px;" onmouseover="this.style.background=\\'#F2F3F5\\'" onmouseout="this.style.background=\\'\\'">';
                                            html += '<div style="font-weight:500;color:#1F2329;">' + (poi.name || '未知') + '</div>';
                                            if (subText) html += '<div style="font-size:10px;color:#86909C;">' + subText + '</div>';
                                            html += '</div>';
                                            validPois.push({{ name: poi.name, location: {{ lng: lng, lat: lat }}, address: poi.address, district: poi.adname }});
                                        }});
                                        suggestionsBox.innerHTML = html || '<div style="padding:8px;color:#86909C;font-size:11px;text-align:center;">未找到匹配地址</div>';
                                        suggestionsBox.style.display = 'block';
                                        var items = suggestionsBox.querySelectorAll('.sug-item');
                                        for (var i = 0; i < items.length; i++) {{
                                            (function(item, idx) {{
                                                item.addEventListener('click', function(e) {{
                                                    e.stopPropagation();
                                                    searchInput.value = validPois[idx].name;
                                                    suggestionsBox.style.display = 'none';
                                                    handleSearchSelect(validPois[idx]);
                                                }});
                                            }})(items[i], parseInt(items[i].getAttribute('data-idx')));
                                        }}
                                    }} else {{
                                        var errInfo = (result && result.info) ? result.info : '未找到匹配地址';
                                        suggestionsBox.innerHTML = '<div style="padding:8px;color:#F53F3F;font-size:11px;text-align:center;">' + errInfo + '</div>';
                                        suggestionsBox.style.display = 'block';
                                    }}
                                }});
                            }}
                        }} catch(err) {{
                            suggestionsBox.innerHTML = '<div style="padding:8px;color:#FF4D4F;font-size:11px;">' + err.message + '</div>';
                            suggestionsBox.style.display = 'block';
                        }}
                    }}, 300);
                }});
                searchInput.addEventListener('click', function(e) {{ e.stopPropagation(); }});
                document.addEventListener('click', function() {{ suggestionsBox.style.display = 'none'; }});
                searchInput.addEventListener('keydown', function(e) {{
                    if (e.key === 'Escape') suggestionsBox.style.display = 'none';
                    else if (e.key === 'Enter') {{
                        e.preventDefault();
                        var first = suggestionsBox.querySelector('.sug-item');
                        if (first) first.click();
                    }}
                }});
            }}

            /**
             * AMap 加载完成后初始化
             */
            function onAmapReady() {{
                document.getElementById('loc_addr').innerHTML = '地图加载成功！正在加载搜索插件...';
                // 显式加载搜索插件（AMap.plugin 方式比 URL 参数更可靠）
                var pluginLoaded = false;
                AMap.plugin(['AMap.Autocomplete', 'AMap.PlaceSearch', 'AMap.Geocoder', 'AMap.Geolocation'], function() {{
                    pluginLoaded = true;
                    initSearch();
                }});
                // 超时检测：5 秒内插件未加载完成，尝试直接初始化（插件可能已通过 URL 参数加载）
                setTimeout(function() {{
                    if (!pluginLoaded) {{
                        initSearch();
                    }}
                }}, 5000);
                if (HAS_INITIAL) {{
                    // 预览模式：直接渲染已保存位置，跳过 GPS 定位
                    updateUI(INIT_LNG, INIT_LAT, 0, INIT_DETAIL || INIT_LABEL, '', '', '', '', '', '');
                    document.getElementById('loc_addr').innerHTML = INIT_DETAIL || INIT_LABEL || '当前位置';
                }} else {{
                    // 定位模式：渲染默认中国地图视图（无标记），引导用户搜索或等待 GPS
                    document.getElementById('loc_addr').innerHTML = '🔍 输入地址搜索，或等待自动定位...';
                    map = new AMap.Map('loc_map', {{ zoom: 4, center: [104.0, 35.0], viewMode: '2D' }});
                    // GPS 定位延迟 2 秒执行，确保地图先渲染出来
                    setTimeout(function() {{
                        document.getElementById('loc_addr').innerHTML = '正在获取位置（可跳过用搜索）...';
                        var doGeo = function() {{
                            if (navigator.geolocation) {{
                                navigator.geolocation.getCurrentPosition(
                                    function(pos) {{
                                        var lng = pos.coords.longitude.toFixed(6);
                                        var lat = pos.coords.latitude.toFixed(6);
                                        var acc = Math.round(pos.coords.accuracy || 0);
                                        currentPoiName = '';
                                        if (AMap && AMap.Geocoder) {{
                                            reverseGeocode(lng, lat, function(addr, p, c, d, twn, st, num) {{
                                                updateUI(lng, lat, acc, addr, p, c, d, twn, st, num);
                                            }});
                                        }} else {{
                                            updateUI(lng, lat, acc, '', '', '', '', '', '', '');
                                        }}
                                    }},
                                    function(err) {{
                                        var m = 'GPS不可用';
                                        if (err.code === 1) m = '权限被拒绝';
                                        else if (err.code === 2) m = '位置不可用';
                                        else if (err.code === 3) m = '超时';
                                        document.getElementById('loc_addr').innerHTML = '<span style="color:#646A73;">' + m + '，请用搜索选择地址</span>';
                                    }},
                                    {{enableHighAccuracy: true, timeout: 8000, maximumAge: 0}}
                                );
                            }} else {{
                                document.getElementById('loc_addr').innerHTML = '<span style="color:#646A73;">请用搜索选择地址</span>';
                            }};
                        }};

                        if (typeof AMap !== 'undefined' && typeof AMap.Geolocation !== 'undefined') {{
                            var geo = new AMap.Geolocation({{
                                enableHighAccuracy: true, timeout: 8000, maximumAge: 0,
                                needAddress: true, GeoLocationFirst: true, showButton: false
                            }});
                            geo.getCurrentPosition(function(st, result) {{
                                if (st === 'complete') {{
                                    var ac = result.addressComponent || {{}};
                                    var sn = ac.streetNumber || {{}};
                                    currentPoiName = '';
                                    updateUI(
                                        result.position.lng.toFixed(6), result.position.lat.toFixed(6),
                                        Math.round(result.accuracy || 0), result.formattedAddress || '',
                                        ac.province || '', ac.city || '', ac.district || '',
                                        ac.township || '', sn.street || '', sn.number || ''
                                    );
                                }} else {{
                                    doGeo();
                                }}
                            }});
                        }} else {{
                            doGeo();
                        }}
                    }}, 2000);
                }}
                // 搜索初始化在 AMap.plugin 回调中执行（见上方）
            }}

            // 确认按钮（components.html iframe 内，用 postMessage 回传到主页面）
            document.getElementById('loc_confirm').addEventListener('click', function() {{
                if (!locData) {{
                    alert('⚠️ 请先定位或搜索地址后再确认');
                    return;
                }}
                // 置灰确认按钮，防止重复点击
                var btn = this;
                btn.disabled = true;
                btn.style.background = '#C9CDD4';
                btn.style.cursor = 'not-allowed';
                btn.innerHTML = '已确认位置';
                if (currentPoiName) locData.poi_name = currentPoiName;
                // 通过 postMessage 发送到主页面
                window.parent.postMessage({{ type: 'LOC_RESULT', data: locData }}, '*');
            }});

            // 取消按钮（仅定位流程显示）
            var cancelBtn = document.getElementById('loc_cancel');
            if (cancelBtn) {{
                cancelBtn.addEventListener('click', function() {{
                    window.parent.postMessage({{ type: 'LOC_CANCEL' }}, '*');
                }});
            }}

            // 动态加载 AMap JS（components.html iframe 内，需自行加载 AMap）
            // 安全密钥配置（解决 INVALID_USER_SCODE 错误）
            {f"window._AMapSecurityConfig = {{ securityJsCode: '{amap_security_code}' }};" if amap_security_code else ""}
            if (typeof AMap === 'undefined') {{
                var s = document.createElement('script');
                s.src = 'https://webapi.amap.com/maps?v=1.4.15&key={amap_key}&plugin=AMap.Geolocation,AMap.Autocomplete,AMap.PlaceSearch,AMap.Geocoder';
                s.onload = onAmapReady;
                s.onerror = function() {{
                    document.getElementById('loc_addr').innerHTML = '<span style="color:#F53F3F;">❌ 地图JS加载失败，请检查网络或Key配置</span>';
                }};
                document.head.appendChild(s);
            }} else {{
                onAmapReady();
            }}
        }})();
        </script>
        """


def _location_fragment():
    """定位面板：全局设备级定位状态，与会话/规划完全解耦。

    不使用 @st.fragment：fragment 内 widget 在主应用 rerun 时状态同步不可靠，
    会导致 toggle 状态丢失。普通函数确保 widget 状态跨 rerun 持久。
    """
    # ========== 先处理定位结果回传（必须在 toggle 渲染之前）==========
    amap_key = settings.AMAP_JS_API_KEY or settings.AMAP_API_KEY or ""
    query_params = st.query_params
    if "loc_result" in query_params:
        try:
            data = json.loads(query_params["loc_result"])
            city = data.get("city", "")
            prov = data.get("prov", "")
            dist = data.get("dist", "")
            twn = data.get("twn", "")
            street = data.get("street", "")
            number = data.get("number", "")
            acc = data.get("acc", 0)
            amap_addr = data.get("addr", "")
            poi_name = data.get("poi_name", "")
            lng = data.get("lng", "")
            lat = data.get("lat", "")

            if city or amap_addr or poi_name:
                short_addr = poi_name or city or amap_addr
                if not poi_name and dist and city:
                    short_addr = f"{city}{dist}"

                if poi_name:
                    detail_parts = [poi_name, city or ""]
                    if dist:
                        detail_parts.append(dist)
                    if twn:
                        detail_parts.append(twn)
                    if street:
                        street_full = street + (number + "号" if number else "")
                        detail_parts.append(street_full)
                    detail_addr = "".join(p for p in detail_parts if p)
                else:
                    detail_parts = [prov, city, dist, twn]
                    if street:
                        street_full = street + (number + "号" if number else "")
                        detail_parts.append(street_full)
                    detail_addr = "".join(p for p in detail_parts if p)
                    if not detail_addr and amap_addr:
                        detail_addr = amap_addr

                if acc:
                    detail_addr += f"（±{acc}米）"
                st.session_state.user_location["current_location"] = short_addr
                st.session_state.user_location["current_city"] = city
                st.session_state.user_location["current_location_detail"] = detail_addr
                st.session_state.user_location["current_location_lng"] = lng
                st.session_state.user_location["current_location_lat"] = lat
                # 关键：在 toggle 渲染之前就设置为 True
                st.session_state.toggle_location = True
                print(f"\n[定位回传] 定位信息已写入 user_location：")
                print(f"  current_location: {short_addr}")
                print(f"  current_city: {city}")
                print(f"  current_location_detail: {detail_addr}")
                print(f"  lng: {lng}, lat: {lat}")
                print(f"  toggle_location: True (已在 widget 渲染前设置)")
                display_msg = f"📍 {detail_addr}" if poi_name else f"精准定位成功：{detail_addr}"
                st.success(display_msg)

            st.session_state.pop("need_location", None)
            st.session_state.pop("loc_requested", None)
            if "loc_result" in st.query_params:
                del st.query_params["loc_result"]

        except Exception as e:
            st.warning(f"定位结果解析失败：{e}")
            st.session_state.pop("need_location", None)
            st.session_state.pop("loc_requested", None)
            if "loc_result" in st.query_params:
                del st.query_params["loc_result"]
    elif "loc_cancel" in query_params:
        st.session_state.pop("need_location", None)
        st.session_state.pop("loc_requested", None)
        if "loc_cancel" in st.query_params:
            del st.query_params["loc_cancel"]
        st.rerun()

    # ========== 显示当前位置（loc_result 已处理，user_location 已更新）==========
    current_loc = st.session_state.user_location.get("current_location", "")
    current_loc_detail = st.session_state.user_location.get("current_location_detail", "")
    if current_loc_detail:
        display_text = current_loc_detail
        if len(display_text) > 30:
            display_text = display_text[:28] + "…"
        st.markdown(
            f'<div style="font-size:12px;color:#4C6FFF;font-weight:600;padding:4px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="{current_loc_detail}">✅ {display_text}</div>',
            unsafe_allow_html=True
        )
    elif current_loc:
        st.markdown(
            f'<div style="font-size:13px;color:#4C6FFF;font-weight:600;padding:4px 0;">✅ {current_loc}</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div style="font-size:12px;color:#646A73;padding:4px 0;">未定位</div>',
            unsafe_allow_html=True
        )

    # ========== 定位开关（此时 toggle_location 已正确设置）==========
    if "toggle_location" not in st.session_state:
        st.session_state.toggle_location = bool(current_loc)

    def _on_toggle_location_change():
        """toggle 变更回调：同步 widget 值到 session_state，关闭时清除定位"""
        st.session_state.toggle_location = st.session_state._loc_toggle_widget
        print(f"\n[toggle回调] toggle 变更: toggle_location={st.session_state.toggle_location}")
        if not st.session_state.toggle_location:
            print(f"[toggle回调] 定位被关闭，清除 user_location")
            st.session_state.user_location["current_location"] = ""
            st.session_state.user_location["current_city"] = ""
            st.session_state.user_location["current_location_detail"] = ""
            st.session_state.user_location["current_location_lng"] = ""
            st.session_state.user_location["current_location_lat"] = ""
            st.session_state.pop("need_location", None)
            st.session_state.pop("loc_requested", None)

    # 清除 widget key，确保每次渲染都从 value 参数读取初始值
    st.session_state.pop("_loc_toggle_widget", None)
    st.toggle(
        "📍 启用定位",
        value=st.session_state.toggle_location,
        key="_loc_toggle_widget",
        on_change=_on_toggle_location_change,
        help="开启后自动获取当前精准位置（高德融合定位，精度5~30米），用于交通路线规划等功能",
    )
    loc_enabled = st.session_state.get("toggle_location", False)

    # ========== 触发定位 ==========
    if loc_enabled and not current_loc and not st.session_state.get("loc_requested"):
        st.session_state.need_location = True
        st.session_state.loc_requested = True

    # ========== postMessage 监听器（接收 iframe 回传的定位数据）==========
    st.html("""
<script>
if (!window.__loc_listener_installed) {
    window.__loc_listener_installed = true;
    window.addEventListener('message', function(e) {
        var msg = e.data || {};
        if (msg.type === 'LOC_RESULT') {
            var url = new URL(window.location.href);
            url.searchParams.set('loc_result', JSON.stringify(msg.data));
            window.location.href = url.toString();
        } else if (msg.type === 'LOC_CANCEL') {
            var url = new URL(window.location.href);
            url.searchParams.set('loc_cancel', '1');
            window.location.href = url.toString();
        }
    });
}
</script>
""", unsafe_allow_javascript=True)

    # ========== 面板渲染：定位流程 或 已定位常驻预览 ==========
    cur_lng = st.session_state.user_location.get("current_location_lng", "")
    cur_lat = st.session_state.user_location.get("current_location_lat", "")
    amap_sec = settings.AMAP_JS_SECURITY_CODE or ""
    if st.session_state.get("need_location"):
        # 定位流程面板（components.html iframe 渲染，地图状态稳定）
        html_content = _build_location_panel_html(amap_key, amap_security_code=amap_sec, panel_height=540)
        components.html(html_content, width=None, height=540)
    elif current_loc_detail and cur_lng and cur_lat:
        # 已定位常驻预览：可搜索新地址 → 地图重渲染 → 确认更新位置
        html_content = _build_location_panel_html(
            amap_key, amap_security_code=amap_sec,
            initial_lng=cur_lng,
            initial_lat=cur_lat,
            initial_label=current_loc,
            initial_detail=current_loc_detail,
            title="📍 当前位置",
            show_cancel=False,
            panel_height=400,
        )
        components.html(html_content, width=None, height=400)


# ========== 4. 侧边栏 ==========
with st.sidebar:
    # 品牌区
    st.markdown("""
    <div style="padding:8px 12px 8px;">
        <div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:26px;">🧳</span>
            <span style="font-size:17px;font-weight:700;color:#1F2329;">Travel Agent</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 新建对话
    if st.button("✨ 新对话", type="primary", use_container_width=True, key="btn_new_chat"):
        _new_session()
        # 定位是全局状态，与会话无关，此处不触碰定位
        st.rerun()

    st.markdown("---")

    # 历史会话（可折叠）
    history_expanded = _render_sidebar_section("历史对话", "📋", "collapse_history")
    if history_expanded:
        sessions = st.session_state.sessions
        if not sessions:
            st.caption("暂无历史会话")
        else:
            sorted_sessions = sorted(
                sessions.values(),
                key=lambda s: s.get("created_at", ""),
                reverse=True
            )
            for session in sorted_sessions[:30]:
                sid = session["id"]
                title = session.get("title", "新对话")
                time_str = session.get("created_at", "")
                active = sid == st.session_state.current_session_id

                col_title, col_del = st.columns([4, 1])
                with col_title:
                    if st.button(
                        f"{'● ' if active else ''}{title[:20]}",
                        key=f"session_{sid}",
                        use_container_width=True,
                        type="primary" if active else "secondary"
                    ):
                        # 定位是全局状态，与会话切换无关，此处不触碰定位
                        st.session_state.current_session_id = sid
                        st.session_state.chat_context = session.get("context", {})
                        st.rerun()
                with col_del:
                    if st.button("🗑", key=f"del_{sid}"):
                        del st.session_state.sessions[sid]
                        if active:
                            st.session_state.current_session_id = None
                        st.rerun()

    st.markdown("---")

    # ========== 定位 Fragment（无刷新定位）==========
    _location_fragment()

    # 底部信息
    st.caption("© 2026 Travel Agent")


# ========== 5. 主内容区 ==========

# 当前会话
current = _get_current_session()

# 无会话时显示欢迎页（豆包风格：聊天框非空白，含问候+推荐）
if not current:
    st.markdown('<div class="welcome-container">', unsafe_allow_html=True)

    # 顶部问候
    st.markdown("""
    <div class="welcome-hero">
        <div class="logo">🧳</div>
        <h1>有什么能帮到你的吗？</h1>
        <p>我是你的旅行助手，可以查天气、找景点美食、规划完整行程</p>
    </div>
    """, unsafe_allow_html=True)

    # 推荐卡片网格（2 列 x 3 行）
    recommendations = [
        ("查询杭州近日天气", "出行前查看目的地天气，合理准备行李"),
        ("周末想去成都旅游，有什么景点推荐吗？", "为你推荐成都热门景点与周边玩法"),
        ("北京有什么特色美食推荐", "本地人推荐的必吃美食清单"),
        ("成都金牛区酒店", "筛选性价比高、位置便利的住宿"),
        ("成都周边古镇", "1-2 天可达的古镇休闲路线"),
        ("帮我规划三天上海行程", "自动生成包含景点/美食/交通的完整行程"),
    ]
    st.markdown('<div class="recommend-grid">', unsafe_allow_html=True)
    cols_per_row = 2
    for i in range(0, len(recommendations), cols_per_row):
        row_items = recommendations[i:i + cols_per_row]
        cols = st.columns(cols_per_row)
        for j, (title, desc) in enumerate(row_items):
            with cols[j]:
                if st.button(
                    f"**{title}**\n\n{desc}",
                    key=f"rec_{i + j}",
                    use_container_width=True
                ):
                    sid = _new_session()
                    st.session_state[f"pending_prompt_{sid}"] = title
                    st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 底部聊天输入框（即使是欢迎页也能直接输入）
    prompt = st.chat_input(
        "试试问我：杭州最近天气怎么样？",
        key="welcome_chat_input"
    )
    if prompt:
        sid = _new_session()
        st.session_state[f"pending_prompt_{sid}"] = prompt
        st.rerun()

    # ========== 欢迎页定位弹窗（由 fragment 处理，此处无需重复）==========
    pass

    st.stop()


# 有会话时显示对话
st.markdown('<div class="chat-area">', unsafe_allow_html=True)

messages = current.get("messages", [])
context = current.get("context", {})
agent = st.session_state.chat_agent

# 更新全局 chat_context
st.session_state.chat_context = context

# 显示对话历史（用 _render_bubble 一次性渲染完整气泡）
for msg in messages:
    role = msg["role"]
    is_user = role == "user"
    action_label = msg.get("action_label", "")
    tool_result = msg.get("tool_result", "")
    plan_data = msg.get("full_plan_result")
    plan_md = ""
    if plan_data:
        plan_md = plan_data.get("final_travel_document", "") or plan_data.get("travel_schedule_markdown", "")

    # 先渲染气泡内容
    _render_bubble(
        content=msg["content"],
        is_user=is_user,
        action_label=action_label,
        tool_result=tool_result,
        plan_md=plan_md,
    )

    # 行程卡片的下载按钮（PNG + PDF 双格式）
    if plan_md and not is_user:
        col_a, col_b = st.columns(2)
        with col_a:
            st.download_button(
                "🖼️ 下载 PNG",
                data=render_markdown_to_png(plan_md),
                file_name=f"行程方案_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                mime="image/png",
                key=f"dl_png_{msg.get('id', '')}",
                use_container_width=True,
            )
        with col_b:
            st.download_button(
                "📄 下载 PDF",
                data=render_markdown_to_pdf(plan_md),
                file_name=f"行程方案_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf",
                key=f"dl_pdf_{msg.get('id', '')}",
                use_container_width=True,
            )

# 检查是否有待处理的欢迎页 prompt
pending_key = f"pending_prompt_{current['id']}"
pending = st.session_state.pop(pending_key, None)

# ========== 聊天页定位弹窗（由 fragment 处理，此处无需重复）==========
pass

# 用户输入
if pending:
    prompt = pending
else:
    prompt = st.chat_input(
        "试试问我：杭州最近天气怎么样？",
        key="chat_input"
    )

if prompt:
    # 标题更新
    if len(messages) == 0:
        current["title"] = prompt[:20] if len(prompt) > 20 else prompt

    # 添加用户消息
    user_msg = {
        "id": str(uuid.uuid4())[:6],
        "role": "user",
        "content": prompt,
        "avatar": "🧑"
    }
    messages.append(user_msg)
    current["messages"] = messages

    # 用户消息：右侧
    _render_bubble(content=prompt, is_user=True)

    # ===== 多轮循环优化分支 =====
    if _is_optimize_request(prompt, current):
        with st.spinner("正在优化行程..."):
            try:
                from travel_agent.nodes.optimize_node import OptimizeNode, OptimizeInput
                from travel_agent.nodes.schedule_node import convert_schedule_to_markdown

                last_plan = current["last_plan"]
                opt_input = OptimizeInput(
                    origin_schedule=last_plan["schedule_struct"],
                    full_resource=last_plan["aggregated_resource"],
                    optimize_demand=prompt,
                    intent_info=last_plan["intent_info"]
                )

                optimize_service = OptimizeNode()
                opt_result = optimize_service.run(opt_input)

                new_md = convert_schedule_to_markdown(opt_result.new_schedule)

                # 变更摘要
                change_summary = "\n".join(f"· {c}" for c in opt_result.change_summary) if opt_result.change_summary else "行程已更新"

                response_msg = {
                    "id": str(uuid.uuid4())[:6],
                    "role": "assistant",
                    "content": f"✅ 行程已优化！\n{change_summary}",
                    "avatar": "🌍",
                    "full_plan_result": {"travel_schedule_markdown": new_md},
                }

                # 更新 last_plan（支持继续多轮优化）
                current["last_plan"] = {
                    "schedule_struct": opt_result.new_schedule,
                    "aggregated_resource": last_plan["aggregated_resource"],
                    "intent_info": last_plan["intent_info"],
                    "schedule_md": new_md,
                }

                messages.append(response_msg)
                current["messages"] = messages

                # 更新原始历史（供记忆管理器使用）
                _raw = current.get("raw_history", [])
                _raw.append({"role": "user", "content": prompt})
                _raw.append({"role": "assistant", "content": response_msg["content"]})
                # 检查是否触发摘要压缩
                if agent.memory.should_summarize(_raw):
                    new_sum, _raw = agent.memory.compress(
                        _raw, existing_summary=current.get("summary")
                    )
                    if new_sum:
                        current["summary"] = new_sum
                current["raw_history"] = _raw

                _save_session(current)

                # 保存优化对话到 SQLite
                try:
                    from travel_agent.cache_manager import save_chat_batch
                    save_chat_batch(current["id"], [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": response_msg["content"]},
                    ])
                except Exception:
                    pass

                # 渲染优化结果：左侧
                _render_bubble(
                    content=response_msg["content"],
                    plan_md=new_md,
                )
                col_a, col_b = st.columns(2)
                with col_a:
                    st.download_button(
                        "🖼️ 下载 PNG",
                        data=render_markdown_to_png(new_md),
                        file_name=f"行程方案_优化_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                        mime="image/png",
                        use_container_width=True,
                    )
                with col_b:
                    st.download_button(
                        "📄 下载 PDF",
                        data=render_markdown_to_pdf(new_md),
                        file_name=f"行程方案_优化_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )

            except Exception as e:
                err_msg = {
                    "id": str(uuid.uuid4())[:6],
                    "role": "assistant",
                    "content": f"⚠️ 优化失败：{str(e)}",
                    "avatar": "🌍",
                }
                messages.append(err_msg)
                current["messages"] = messages
                _save_session(current)
                _render_bubble(content=err_msg["content"])
        st.rerun()

    # 构建 chat_history 传入 ChatAgent（保持多轮记忆）
    _chat_history = current.get("raw_history", [])

    # 先做意图分类，判断是否走完整规划
    intent = agent.classify_intent(prompt)
    merged_ctx = agent._merge_context(intent, context)
    # 注入全局定位状态（设备级），供天气兜底和交通距离分级规划使用
    # current_city: 城市名（如"成都"），用于天气查询等需要城市名的场景
    # current_location: 简短地址（如"龙泉驿区十陵街道"），用于显示
    loc_data = st.session_state.user_location
    if not merged_ctx.get("current_location"):
        merged_ctx["current_location"] = loc_data.get("current_location", "")
    merged_ctx["current_city"] = loc_data.get("current_city", "")
    merged_ctx["current_location_detail"] = loc_data.get("current_location_detail", "")
    merged_ctx["current_location_lng"] = loc_data.get("current_location_lng", "")
    merged_ctx["current_location_lat"] = loc_data.get("current_location_lat", "")

    # 打印前端定位注入情况（调试用）
    loc_dbg = merged_ctx.get("current_location", "")
    loc_lng_dbg = merged_ctx.get("current_location_lng", "")
    loc_lat_dbg = merged_ctx.get("current_location_lat", "")
    if loc_dbg or loc_lng_dbg:
        print(f"\n[前端] 定位信息已注入 merged_ctx：")
        print(f"  当前城市：{loc_dbg}")
        print(f"  详细地址：{merged_ctx.get('current_location_detail', '')}")
        print(f"  经纬度：{loc_lng_dbg},{loc_lat_dbg}")
        print(f"  意图动作：{intent.action}")
    else:
        print(f"\n[前端] 未检测到定位信息（定位未开启或未确定位置），意图动作：{intent.action}")

    # 降级逻辑：使用共享 check_degrade（来自 constants.py）
    # - query_weather 永不降级（可通过定位兜底或引导用户指定城市）
    # - 其他 CITY_REQUIRED_ACTIONS 意图，无城市且无定位时降级
    intent.action = check_degrade(
        intent.action,
        city=merged_ctx.get("city", ""),
        current_location=merged_ctx.get("current_location", "")
    )

    # ========== 缺失参数问询机制 ==========
    # full_plan 但 city/days 缺失时，主动向用户问询，不进入 graph
    if intent.action == "full_plan":
        missing_parts = []
        if not merged_ctx.get("city"):
            missing_parts.append("目的地城市")
        if not merged_ctx.get("days"):
            missing_parts.append("出行天数")
        if missing_parts:
            ask_text = f"✨ 宝子想规划行程呀～还差几个关键信息：\n\n"
            for i, p in enumerate(missing_parts, 1):
                ask_text += f"{i}. **{p}** 还没告诉我哦～\n"
            ask_text += "\n💡 例如：\"帮我规划上海3天行程\" 就可以直接开始啦～"
            with st.chat_message("assistant", avatar="🌍"):
                st.markdown(f'<div class="tool-badge">🔧 行程规划</div>',
                           unsafe_allow_html=True)
                st.markdown(ask_text)
            response_msg = {
                "id": str(uuid.uuid4())[:6],
                "role": "assistant",
                "content": ask_text,
                "tool_result": "",
                "action_label": "行程规划",
                "avatar": "🌍",
            }
            messages.append(response_msg)
            current["messages"] = messages
            _raw = current.get("raw_history", [])
            _raw.append({"role": "user", "content": prompt})
            _raw.append({"role": "assistant", "content": ask_text})
            current["raw_history"] = _raw
            _save_session(current)
            st.rerun()

    is_full_plan = intent.action == "full_plan" and merged_ctx.get("city")
    action_label = agent.ACTION_LABELS.get(intent.action, "未知")

    if is_full_plan:
        # ========== 完整规划：graph.stream 进度反馈 + output 流式渲染 ==========
        with st.chat_message("assistant", avatar="🌍"):
            if action_label:
                st.markdown(f'<div class="tool-badge">🔧 {action_label}</div>',
                           unsafe_allow_html=True)
            try:
                city = merged_ctx.get("city", "")
                days = merged_ctx.get("days", "")

                graph_chat_history = []
                for msg in messages:
                    if msg["role"] in ("user", "assistant"):
                        graph_chat_history.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })

                graph = st.session_state.graph
                # 使用用户原始输入，不覆盖为固定模板
                user_full_input = prompt

                # 合并内存缓存与磁盘缓存
                from travel_agent.cache_manager import load_all_cache
                merged_cache = {}
                merged_cache.update(current.get("last_resource_cache", {}))
                merged_cache.update(load_all_cache())

                # 预填充意图信息，让 intent_node 跳过冗余 LLM 调用（省 1 次 LLM）
                from travel_agent.state import IntentInfo
                from travel_agent.nodes.constants import (
                    TOOL_WEATHER, TOOL_SCENIC, TOOL_FOOD,
                    TOOL_LUGGAGE, TOOL_FUN, TOOL_TRAFFIC
                )
                prefilled_intent = IntentInfo(
                    destination=city,
                    travel_days=days,
                    crowd=merged_ctx.get("crowd", ""),
                    core_demand=prompt,
                    travel_type="",
                    travel_time=merged_ctx.get("travel_time", ""),
                    current_location=st.session_state.user_location.get("current_location", ""),
                    current_location_detail=st.session_state.user_location.get("current_location_detail", ""),
                    current_location_lng=st.session_state.user_location.get("current_location_lng", ""),
                    current_location_lat=st.session_state.user_location.get("current_location_lat", ""),
                    required_tools=[TOOL_WEATHER, TOOL_SCENIC, TOOL_FOOD,
                                   TOOL_LUGGAGE, TOOL_FUN, TOOL_TRAFFIC],
                )

                state_init = {
                    "user_input": user_full_input,
                    "chat_history": graph_chat_history,
                    "history_resource_cache": merged_cache,
                    "intent_info": prefilled_intent,
                }

                # graph.stream 迭代：进度反馈 + 获取最终状态
                from travel_agent.nodes.constants import NODE_DISPLAY_NAMES
                status = st.status("正在规划行程...", expanded=False)
                final_state = dict(state_init)

                # 打印后端执行前的定位信息
                loc_info = prefilled_intent
                print(f"\n{'='*60}")
                print(f"[Graph 启动] 后端开始执行行程规划")
                print(f"  用户输入: {user_full_input}")
                print(f"  目的地: {loc_info.destination}")
                print(f"  当前城市: {loc_info.current_location}")
                print(f"  详细地址: {loc_info.current_location_detail}")
                print(f"  经纬度: {loc_info.current_location_lng},{loc_info.current_location_lat}")
                print(f"  出行天数: {loc_info.travel_days}")
                print(f"  必需工具: {loc_info.required_tools}")
                print(f"{'='*60}\n")

                for mode, chunk in graph.stream(state_init, stream_mode=["updates", "values"]):
                    if mode == "updates":
                        for node_name in chunk:
                            if node_name.startswith("__"):
                                continue
                            display = NODE_DISPLAY_NAMES.get(node_name, node_name)
                            status.update(label=f"✅ {display} 完成")
                    elif mode == "values":
                        final_state = chunk

                status.update(label="✅ 行程结构生成完成，正在渲染文案...", state="complete")

                # 更新缓存
                current["last_resource_cache"] = final_state.get("history_resource_cache", {})

                # 更新聊天历史
                updated_history = final_state.get("chat_history", [])
                if updated_history:
                    existing_contents = {m["content"] for m in messages}
                    for gh in updated_history:
                        if gh.get("content") not in existing_contents:
                            messages.append({
                                "id": str(uuid.uuid4())[:6],
                                "role": gh.get("role", "assistant"),
                                "content": gh.get("content", ""),
                                "avatar": "🌍"
                            })
                            existing_contents.add(gh.get("content", ""))
                    current["messages"] = messages

                schedule_md = final_state.get("travel_schedule_markdown", "")
                schedule_struct = final_state.get("travel_schedule_struct")
                intent_info = final_state.get("intent_info")

                # 获取模板类型和上下文（用于流式渲染）
                template_type = final_state.get("selected_template", "")
                template_context = final_state.get("template_context", {})

                # 检查异常 → fallback 文案
                if final_state.get("has_exception") or final_state.get("is_fallback"):
                    response_text = final_state.get("final_travel_document", "规划过程中出现异常")
                    dev_log = final_state.get("dev_error_log", "")
                    if dev_log:
                        print(f"\n{'='*60}")
                        print(f"[Fallback 触发] 详细错误日志:")
                        print(dev_log)
                        print(f"{'='*60}\n")
                    _stream_render(content=response_text, action_label=action_label, is_plan=False)
                    final_doc = response_text
                elif template_type and template_context:
                    # ✅ 真流式：调用 stream_output 让 LLM 逐 token 生成
                    print(f"\n[流式输出] 模板类型: {template_type}")
                    print(f"  上下文字段数: {len(template_context)}")

                    from travel_agent.nodes.output_node import stream_output

                    cols_a, cols_b = st.columns([4, 1])
                    with cols_a:
                        badge_html = f'<div class="tool-badge">🔧 {action_label}</div>'
                        placeholder = st.empty()
                        placeholder.markdown(
                            f'{badge_html}<div style="padding:20px;color:#646A73;">⏳ 正在生成行程方案…</div>',
                            unsafe_allow_html=True
                        )

                        # 收集流式输出
                        chunks = []
                        for chunk in stream_output(template_type, template_context):
                            if chunk:
                                chunks.append(chunk)
                                current_text = "".join(chunks)
                                placeholder.markdown(
                                    f'{badge_html}<div class="plan-card" style="margin-top:12px;">{current_text}</div>',
                                    unsafe_allow_html=True
                                )

                        final_doc = "".join(chunks)
                        # 最终渲染
                        placeholder.empty()
                        st.markdown(
                            f'{badge_html}<div class="plan-card" style="margin-top:12px;">{final_doc}</div>',
                            unsafe_allow_html=True
                        )
                elif schedule_struct and intent_info:
                    # 兼容旧流程
                    final_doc = schedule_md
                    _stream_render(content=schedule_md, action_label=action_label, is_plan=True)
                else:
                    final_doc = "⚠️ 行程数据生成失败，请重试"
                    _stream_render(content=final_doc, action_label=action_label, is_plan=False)

                # 保存行程数据（供多轮优化使用）
                if schedule_struct:
                    current["last_plan"] = {
                        "schedule_struct": schedule_struct,
                        "aggregated_resource": final_state.get("aggregated_all_resource", ""),
                        "intent_info": intent_info,
                        "schedule_md": schedule_md,
                    }

                # 下载按钮：PNG + PDF 双格式
                download_data = final_doc or schedule_md
                if download_data and not final_state.get("has_exception") and not final_state.get("is_fallback"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.download_button(
                            "🖼️ 下载 PNG",
                            data=render_markdown_to_png(download_data),
                            file_name=f"行程方案_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                            mime="image/png",
                            key=f"dl_png_rt_{str(uuid.uuid4())[:6]}",
                            use_container_width=True,
                        )
                    with col_b:
                        st.download_button(
                            "📄 下载 PDF",
                            data=render_markdown_to_pdf(download_data),
                            file_name=f"行程方案_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf",
                            key=f"dl_pdf_rt_{str(uuid.uuid4())[:6]}",
                            use_container_width=True,
                        )

                # 缓存信息
                cache = final_state.get("history_resource_cache", {})
                if cache:
                    cache_info = ", ".join(cache.keys())
                    if cache_info:
                        st.caption(f"📦 已缓存城市：{cache_info}（下次查询更快）")

                # 行程成功时 content 留空（行程通过 plan_md 卡片渲染），避免重复显示
                response_msg = {
                    "id": str(uuid.uuid4())[:6],
                    "role": "assistant",
                    "content": "" if (final_doc or schedule_md) and not final_state.get("has_exception") and not final_state.get("is_fallback") else response_text,
                    "tool_result": "",
                    "action_label": action_label,
                    "avatar": "🌍",
                    "full_plan_result": final_state,
                }
                context = merged_ctx
                current["context"] = context

            except Exception as e:
                response_msg = {
                    "id": str(uuid.uuid4())[:6],
                    "role": "assistant",
                    "content": f"⚠️ 规划过程中遇到问题：{str(e)}",
                    "tool_result": "",
                    "action_label": action_label,
                    "avatar": "🌍",
                }
                st.markdown(response_msg["content"])
                context = merged_ctx
                current["context"] = context

        messages.append(response_msg)
        current["messages"] = messages
        _raw = current.get("raw_history", [])
        _raw.append({"role": "user", "content": prompt})
        _raw.append({"role": "assistant", "content": response_msg["content"]})
        if agent.memory.should_summarize(_raw):
            new_sum, _raw = agent.memory.compress(
                _raw, existing_summary=current.get("summary")
            )
            if new_sum:
                current["summary"] = new_sum
        current["raw_history"] = _raw
        _save_session(current)

        try:
            from travel_agent.cache_manager import save_chat_batch
            save_chat_batch(current["id"], [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response_msg["content"]},
            ])
        except Exception:
            pass

    else:
        # ========== 普通对话/工具查询：流式输出 ==========
        with st.chat_message("assistant", avatar="🌍"):
            if action_label and action_label != "闲聊":
                st.markdown(f'<div class="tool-badge">🔧 {action_label}</div>',
                           unsafe_allow_html=True)
            response_placeholder = st.empty()
            accumulated_text = ""
            # 打印聊天模式调用前的定位信息
            print(f"\n[聊天模式] 后端执行前定位检查：")
            print(f"  意图动作: {intent.action}")
            print(f"  当前城市: {merged_ctx.get('current_location', '')}")
            print(f"  详细地址: {merged_ctx.get('current_location_detail', '')}")
            print(f"  经纬度: {merged_ctx.get('current_location_lng', '')},{merged_ctx.get('current_location_lat', '')}")
            try:
                for kind, payload in agent.chat_stream(
                    prompt, merged_ctx,
                    chat_history=_chat_history,
                    session_summary=current.get("summary")
                ):
                    if kind == "delta":
                        accumulated_text += payload
                        response_placeholder.markdown(accumulated_text)
            except Exception as e:
                accumulated_text = f"抱歉，处理您的问题时遇到了错误：{str(e)}"
                response_placeholder.markdown(accumulated_text)

        response_msg = {
            "id": str(uuid.uuid4())[:6],
            "role": "assistant",
            "content": accumulated_text,
            "tool_result": "",
            "action_label": action_label,
            "avatar": "🌍",
        }
        context = merged_ctx
        current["context"] = context

        messages.append(response_msg)
        current["messages"] = messages
        _raw = current.get("raw_history", [])
        _raw.append({"role": "user", "content": prompt})
        _raw.append({"role": "assistant", "content": accumulated_text})
        if agent.memory.should_summarize(_raw):
            new_sum, _raw = agent.memory.compress(
                _raw, existing_summary=current.get("summary")
            )
            if new_sum:
                current["summary"] = new_sum
        current["raw_history"] = _raw
        _save_session(current)

        try:
            from travel_agent.cache_manager import save_chat_batch
            save_chat_batch(current["id"], [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": accumulated_text},
            ])
        except Exception:
            pass

    st.rerun()

st.markdown('</div>', unsafe_allow_html=True)
