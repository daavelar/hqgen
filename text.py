from __future__ import annotations

from pathlib import Path

from PIL import ImageDraw, ImageFont


FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "/Library/Fonts/Arial.ttf",
]

FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = FONT_BOLD_CANDIDATES if bold else FONT_CANDIDATES

    for font_path in candidates:
        if Path(font_path).exists():
            return ImageFont.truetype(font_path, size=size)

    return ImageFont.load_default()


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = text.split()

    if not words:
        return []

    lines: list[str] = []
    current_line = words[0]

    for word in words[1:]:
        candidate = f"{current_line} {word}"

        if text_width(draw, candidate, font) <= max_width:
            current_line = candidate
            continue

        lines.append(current_line)
        current_line = word

    lines.append(current_line)

    return split_long_lines(draw, lines, font, max_width)


def split_long_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    wrapped: list[str] = []

    for line in lines:
        if text_width(draw, line, font) <= max_width:
            wrapped.append(line)
            continue

        chunk = ""

        for character in line:
            candidate = f"{chunk}{character}"

            if text_width(draw, candidate, font) <= max_width:
                chunk = candidate
                continue

            if chunk:
                wrapped.append(chunk)

            chunk = character

        if chunk:
            wrapped.append(chunk)

    return wrapped


def text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)

    return right - left


def text_height(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
) -> int:
    _, top, _, bottom = draw.textbbox((0, 0), text, font=font)

    return bottom - top

