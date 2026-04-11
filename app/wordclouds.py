from __future__ import annotations

import io
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

import jieba
from PIL import Image, ImageDraw, ImageFont

from app.db import get_connection
from app.errors import AppError


WORDCLOUD_VIEWS = {"clean", "raw", "auto"}
MIN_IMAGE_SIZE = 320
MAX_IMAGE_SIZE = 2000
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 720
DEFAULT_TOP_N = 80
MAX_TOP_N = 200
BACKGROUND_COLOR = "#fffaf2"
PALETTE = ("#8c3118", "#b24c2c", "#1b2230", "#36638a", "#735f32", "#54643f")
STOPWORDS = {
    "我们",
    "你们",
    "他们",
    "这个",
    "那个",
    "一个",
    "一种",
    "已经",
    "可以",
    "以及",
    "并且",
    "如果",
    "因为",
    "所以",
    "进行",
    "相关",
    "工作",
    "内容",
    "作者",
    "图片",
    "视频",
    "全文",
    "原标题",
    "点击",
    "查看",
    "网页链接",
    "http",
    "https",
    "www",
    "com",
}
FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/NotoSansSC.ttf"),
    Path("C:/Windows/Fonts/simhei.ttf"),
]


def generate_wordcloud(
    task_id: str,
    view: str = "auto",
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, Any]:
    normalized_view = view.strip().lower()
    if normalized_view not in WORDCLOUD_VIEWS:
        raise AppError(1001, "view must be one of auto, clean, raw")

    normalized_width = _normalize_int(width, "width", MIN_IMAGE_SIZE, MAX_IMAGE_SIZE)
    normalized_height = _normalize_int(height, "height", MIN_IMAGE_SIZE, MAX_IMAGE_SIZE)
    normalized_top_n = _normalize_int(top_n, "top_n", 10, MAX_TOP_N)

    source_view, texts = _load_texts(task_id, normalized_view)
    frequencies = _build_frequencies(texts)
    if not frequencies:
        raise AppError(1001, "no text available for wordcloud")

    image = Image.new("RGB", (normalized_width, normalized_height), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)
    rng = random.Random(f"{task_id}:{source_view}:{normalized_width}:{normalized_height}:{normalized_top_n}")

    placed_boxes: list[tuple[int, int, int, int]] = []
    max_frequency = frequencies[0][1]
    min_frequency = frequencies[-1][1]

    for index, (word, frequency) in enumerate(frequencies):
        font_size = _scale_font_size(frequency, max_frequency, min_frequency)
        font = _load_font(font_size)
        bbox = draw.textbbox((0, 0), word, font=font)
        word_width = bbox[2] - bbox[0]
        word_height = bbox[3] - bbox[1]
        if word_width >= normalized_width - 24 or word_height >= normalized_height - 24:
            continue

        x, y = _find_position(
            rng,
            placed_boxes,
            normalized_width,
            normalized_height,
            word_width,
            word_height,
            attempts=240 if index < 12 else 100,
        )
        if x is None or y is None:
            continue

        color = PALETTE[index % len(PALETTE)]
        draw.text((x, y), word, fill=color, font=font)
        placed_boxes.append((x - 6, y - 4, x + word_width + 6, y + word_height + 4))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return {
        "filename": f"{task_id}_{source_view}_wordcloud.png",
        "media_type": "image/png",
        "content": buffer.getvalue(),
        "view": source_view,
        "top_terms": [{"word": word, "count": count} for word, count in frequencies[:10]],
    }


def _load_texts(task_id: str, view: str) -> tuple[str, list[str]]:
    _ensure_task_exists(task_id)
    if view in {"clean", "auto"}:
        texts = _fetch_clean_texts(task_id)
        if texts:
            return "clean", texts
    if view in {"raw", "auto"}:
        texts = _fetch_raw_texts(task_id)
        if texts:
            return "raw", texts
    return ("clean" if view == "clean" else "raw"), []


def _fetch_clean_texts(task_id: str) -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT clean_news_title, clean_news_content
            FROM clean_items
            WHERE task_id = ? AND clean_status = 'clean_done'
            ORDER BY id ASC
            """,
            (task_id,),
        ).fetchall()
    return [
        part.strip()
        for row in rows
        for part in (row["clean_news_title"], row["clean_news_content"])
        if isinstance(part, str) and part.strip()
    ]


def _fetch_raw_texts(task_id: str) -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT news_title, news_content
            FROM raw_items
            WHERE task_id = ?
            ORDER BY id ASC
            """,
            (task_id,),
        ).fetchall()
    return [
        part.strip()
        for row in rows
        for part in (row["news_title"], row["news_content"])
        if isinstance(part, str) and part.strip()
    ]


def _build_frequencies(texts: list[str]) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for text in texts:
        for token in jieba.lcut(text):
            normalized = _normalize_token(token)
            if normalized is None:
                continue
            counts[normalized] += 1
    return counts.most_common(MAX_TOP_N)


def _normalize_token(token: str) -> str | None:
    token = token.strip().lower()
    if not token:
        return None
    token = re.sub(r"[^\w\u4e00-\u9fff]+", "", token)
    if not token or token in STOPWORDS:
        return None
    if token.isdigit():
        return None
    if re.fullmatch(r"[a-z0-9_]+", token):
        if len(token) < 3:
            return None
        return token
    if len(token) < 2:
        return None
    return token


def _scale_font_size(frequency: int, max_frequency: int, min_frequency: int) -> int:
    if max_frequency == min_frequency:
        return 40
    ratio = (frequency - min_frequency) / (max_frequency - min_frequency)
    return int(22 + ratio * 56)


def _find_position(
    rng: random.Random,
    placed_boxes: list[tuple[int, int, int, int]],
    width: int,
    height: int,
    word_width: int,
    word_height: int,
    attempts: int,
) -> tuple[int | None, int | None]:
    max_x = max(12, width - word_width - 12)
    max_y = max(12, height - word_height - 12)
    for _ in range(attempts):
        x = rng.randint(12, max_x)
        y = rng.randint(12, max_y)
        candidate = (x, y, x + word_width, y + word_height)
        if any(_overlaps(candidate, existing) for existing in placed_boxes):
            continue
        return x, y
    return None, None


def _overlaps(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _ensure_task_exists(task_id: str) -> None:
    with get_connection() as connection:
        row = connection.execute("SELECT 1 FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if row is None:
        raise AppError(2001)


def _normalize_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise AppError(1001, f"{field} must be an integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise AppError(1001, f"{field} must be an integer") from exc
    if normalized < minimum or normalized > maximum:
        raise AppError(1001, f"{field} must be between {minimum} and {maximum}")
    return normalized
