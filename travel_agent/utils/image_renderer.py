# -*- coding: utf-8 -*-
"""
行程图片渲染器 — 将行程 Markdown 文本渲染为 PNG / PDF

使用 Pillow 绘制，模拟小红书卡片风格。
支持彩色 emoji 渲染（Segoe UI Emoji 字体 + embedded_color）。
"""

import io
import re
import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

# ── 常量 ──────────────────────────────────────────
_IMG_WIDTH = 800
_PADDING = 40
_BG_COLOR = (255, 255, 255, 255)
_TEXT_COLOR = "#1F2329"
_SECONDARY_COLOR = "#646A73"
_ACCENT_COLOR = "#3370FF"
_DIVIDER_COLOR = "#E5E6EB"
_TAG_BG = "#F2F3F5"

# 字体路径（Windows 微软雅黑）
_FONT_PATHS = [
    "C:\\Windows\\Fonts\\msyh.ttc",    # 微软雅黑
    "C:\\Windows\\Fonts\\msyhbd.ttc",   # 微软雅黑粗体
    "C:\\Windows\\Fonts\\simhei.ttf",   # 黑体（备用）
]
# Emoji 字体路径（Windows Segoe UI Emoji）
_EMOJI_FONT_PATH = "C:\\Windows\\Fonts\\seguiemj.ttf"

# 字体缓存
_font_cache: dict[str, ImageFont.FreeTypeFont] = {}


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """
    加载指定大小的中文字体

    Args:
        size: 字体大小
        bold: 是否使用粗体

    Returns:
        PIL 字体对象
    """
    key = f"{'bold' if bold else 'normal'}_{size}"
    if key in _font_cache:
        return _font_cache[key]

    path_idx = 1 if bold else 0
    for path in _FONT_PATHS[path_idx:] + _FONT_PATHS:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _font_cache[key] = font
                return font
            except Exception:
                continue
    font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def _load_emoji_font(size: int) -> ImageFont.FreeTypeFont:
    """
    加载 Emoji 字体（Segoe UI Emoji）

    Args:
        size: 字体大小

    Returns:
        PIL Emoji 字体对象
    """
    key = f"emoji_{size}"
    if key in _font_cache:
        return _font_cache[key]

    if os.path.exists(_EMOJI_FONT_PATH):
        try:
            font = ImageFont.truetype(_EMOJI_FONT_PATH, size)
            _font_cache[key] = font
            return font
        except Exception:
            pass

    return _load_font(size)


def _is_emoji(char: str) -> bool:
    """
    检测字符是否为 emoji 或彩色符号

    Args:
        char: 单个字符

    Returns:
        是否为 emoji
    """
    cp = ord(char)
    return (
        0x1F000 <= cp <= 0x1FAFF   # emoji 主范围
        or 0x2600 <= cp <= 0x27BF  # 杂项符号 & 装饰符号
        or 0x2B00 <= cp <= 0x2BFF  # 箭头
        or 0x2300 <= cp <= 0x23FF  # 技术符号（⌚⏰等）
        or cp in (0x00A9, 0x00AE, 0x2122, 0x2139, 0x2194, 0x2195,
                  0x2196, 0x2197, 0x2198, 0x2199, 0x21A9, 0x21AA,
                  0x231A, 0x231B, 0x2328, 0x23CF, 0x23ED, 0x23EE,
                  0x23EF, 0x23F0, 0x23F1, 0x23F2, 0x23F3, 0x24C2,
                  0x25AA, 0x25AB, 0x25B6, 0x25C0, 0x25FB, 0x25FC,
                  0x25FD, 0x25FE, 0x3030, 0x303D, 0x3297, 0x3299)
    )


def _char_width(draw: ImageDraw.ImageDraw, char: str, font: ImageFont.FreeTypeFont) -> int:
    """
    计算单个字符的渲染宽度

    Args:
        draw: PIL 绘图对象
        char: 字符
        font: 字体对象

    Returns:
        字符宽度（像素）
    """
    bbox = draw.textbbox((0, 0), char, font=font)
    return bbox[2] - bbox[0]


def _draw_text_with_emoji(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str = _TEXT_COLOR,
    emoji_font: Optional[ImageFont.FreeTypeFont] = None,
) -> None:
    """
    混合渲染文本（中文用普通字体，emoji 用 Segoe UI Emoji 彩色字体）

    Args:
        draw: PIL 绘图对象
        xy: 起始坐标 (x, y)
        text: 待渲染文本
        font: 常规字体
        fill: 文字颜色（仅对非 emoji 字符生效）
        emoji_font: emoji 字体（None 时自动加载同尺寸）
    """
    x, y = xy
    size = font.size if hasattr(font, 'size') else 14
    if emoji_font is None:
        emoji_font = _load_emoji_font(size)

    for char in text:
        if _is_emoji(char):
            draw.text((x, y), char, font=emoji_font, embedded_color=True)
            w = _char_width(draw, char, emoji_font)
        else:
            draw.text((x, y), char, font=font, fill=fill)
            w = _char_width(draw, char, font)
        x += w


def _text_width_mixed(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    emoji_font: Optional[ImageFont.FreeTypeFont] = None,
) -> int:
    """
    计算混合文本的总宽度（中文 + emoji）

    Args:
        draw: PIL 绘图对象
        text: 待计算文本
        font: 常规字体
        emoji_font: emoji 字体

    Returns:
        文本总宽度（像素）
    """
    size = font.size if hasattr(font, 'size') else 14
    if emoji_font is None:
        emoji_font = _load_emoji_font(size)

    total = 0
    for char in text:
        if _is_emoji(char):
            total += _char_width(draw, char, emoji_font)
        else:
            total += _char_width(draw, char, font)
    return total


def _strip_markdown(text: str) -> str:
    """
    去除 Markdown 标记，保留纯文本

    Args:
        text: 包含 Markdown 标记的文本

    Returns:
        去除标记后的纯文本
    """
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    return text


def _is_divider(line: str) -> bool:
    """
    判断是否为分隔线行

    Args:
        line: 文本行

    Returns:
        是否为分隔线
    """
    stripped = line.strip()
    return stripped.startswith("──") or stripped.startswith("---") or stripped.startswith("══")


def _is_tag_line(line: str) -> bool:
    """
    判断是否为话题标签行

    Args:
        line: 文本行

    Returns:
        是否为标签行
    """
    stripped = line.strip()
    return stripped.startswith("#") and stripped.count("#") >= 2


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    emoji_font: Optional[ImageFont.FreeTypeFont] = None,
) -> list[str]:
    """
    文本自动换行（支持中英文 + emoji 混合）

    Args:
        draw: PIL 绘图对象
        text: 待换行文本
        font: 常规字体
        max_width: 最大宽度（像素）
        emoji_font: emoji 字体

    Returns:
        换行后的文本列表
    """
    size = font.size if hasattr(font, 'size') else 14
    if emoji_font is None:
        emoji_font = _load_emoji_font(size)

    lines = []
    current = ""

    for char in text:
        test = current + char
        w = _text_width_mixed(draw, test, font, emoji_font)
        if w > max_width and current:
            lines.append(current)
            current = char
        else:
            current = test

    if current:
        lines.append(current)

    return lines if lines else [""]


def _parse_line_type(line: str) -> str:
    """
    识别行类型

    Args:
        line: 原始文本行

    Returns:
        行类型：title / subtitle / divider / tag / body
    """
    stripped = line.strip()
    if _is_divider(stripped):
        return "divider"
    if _is_tag_line(stripped):
        return "tag"
    if stripped.startswith("# ") or stripped.startswith("## "):
        return "title"
    if stripped.startswith("📅 Day") or stripped.startswith("📍 ") or stripped.startswith("🚀"):
        return "subtitle"
    return "body"


def _render_to_image(markdown_text: str) -> Image.Image:
    """
    将行程 Markdown 文本渲染为 PIL 图片对象（公共渲染逻辑）

    Args:
        markdown_text: 行程 Markdown 文本

    Returns:
        PIL RGB 图片对象
    """
    if not markdown_text or not markdown_text.strip():
        markdown_text = "暂无行程内容"

    # 预处理：去除 Markdown 标记
    raw_lines = markdown_text.split("\n")
    lines = [_strip_markdown(line.rstrip()) for line in raw_lines]

    # 字体
    font_title = _load_font(22, bold=True)
    font_subtitle = _load_font(17, bold=True)
    font_body = _load_font(14, bold=False)
    font_small = _load_font(12, bold=False)
    emoji_title = _load_emoji_font(22)
    emoji_subtitle = _load_emoji_font(17)
    emoji_body = _load_emoji_font(14)
    emoji_small = _load_emoji_font(12)

    content_width = _IMG_WIDTH - _PADDING * 2

    # 临时绘图对象（用于宽度计算）
    tmp_img = Image.new("RGBA", (1, 1), _BG_COLOR)
    tmp_draw = ImageDraw.Draw(tmp_img)

    # 第一遍：计算总高度
    total_height = _PADDING

    for line in lines:
        stripped = line.strip()
        if not stripped:
            total_height += 8
            continue

        line_type = _parse_line_type(stripped)

        if line_type == "divider":
            total_height += 16
        elif line_type == "title":
            text = stripped.lstrip("# ").strip()
            wrapped = _wrap_text(tmp_draw, text, font_title, content_width, emoji_title)
            total_height += len(wrapped) * 30 + 8
        elif line_type == "subtitle":
            wrapped = _wrap_text(tmp_draw, stripped, font_subtitle, content_width, emoji_subtitle)
            total_height += len(wrapped) * 26 + 6
        elif line_type == "tag":
            total_height += 24
        else:
            wrapped = _wrap_text(tmp_draw, stripped, font_body, content_width, emoji_body)
            total_height += len(wrapped) * 22 + 4

    total_height += _PADDING

    # 创建图片（RGBA 模式，支持彩色 emoji）
    img = Image.new("RGBA", (_IMG_WIDTH, total_height), _BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 第二遍：绘制
    y = _PADDING

    for line in lines:
        stripped = line.strip()
        if not stripped:
            y += 8
            continue

        line_type = _parse_line_type(stripped)

        if line_type == "divider":
            draw.line(
                [(_PADDING, y + 8), (_IMG_WIDTH - _PADDING, y + 8)],
                fill=_DIVIDER_COLOR,
                width=1,
            )
            y += 16

        elif line_type == "title":
            text = stripped.lstrip("# ").strip()
            wrapped = _wrap_text(draw, text, font_title, content_width, emoji_title)
            for wl in wrapped:
                _draw_text_with_emoji(draw, (_PADDING, y), wl, font_title, _TEXT_COLOR, emoji_title)
                y += 30
            y += 8

        elif line_type == "subtitle":
            wrapped = _wrap_text(draw, stripped, font_subtitle, content_width, emoji_subtitle)
            for wl in wrapped:
                _draw_text_with_emoji(draw, (_PADDING, y), wl, font_subtitle, _ACCENT_COLOR, emoji_subtitle)
                y += 26
            y += 6

        elif line_type == "tag":
            text = stripped
            tw = _text_width_mixed(draw, text, font_small, emoji_small)
            draw.rounded_rectangle(
                [_PADDING, y, _PADDING + tw + 16, y + 24],
                radius=4,
                fill=_TAG_BG,
            )
            _draw_text_with_emoji(draw, (_PADDING + 8, y + 4), text, font_small, _SECONDARY_COLOR, emoji_small)
            y += 24

        else:
            wrapped = _wrap_text(draw, stripped, font_body, content_width, emoji_body)
            for wl in wrapped:
                _draw_text_with_emoji(draw, (_PADDING, y), wl, font_body, _TEXT_COLOR, emoji_body)
                y += 22
            y += 4

    return img.convert("RGB")


def render_markdown_to_png(markdown_text: str) -> bytes:
    """
    将行程 Markdown 渲染为 PNG 图片

    Args:
        markdown_text: 行程 Markdown 文本

    Returns:
        PNG 图片字节数据
    """
    img = _render_to_image(markdown_text)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_markdown_to_pdf(markdown_text: str) -> bytes:
    """
    将行程 Markdown 渲染为 PDF 文档（复用图片渲染，支持彩色 emoji）

    Args:
        markdown_text: 行程 Markdown 文本

    Returns:
        PDF 文档字节数据
    """
    img = _render_to_image(markdown_text)
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=150.0)
    return buf.getvalue()
