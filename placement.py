from __future__ import annotations

from dataclasses import dataclass

from PIL import ImageDraw, ImageFont

try:
    from .models import RenderOptions
    from .text import text_height, wrap_text
except ImportError:
    from models import RenderOptions
    from text import text_height, wrap_text


@dataclass(frozen=True)
class Rect:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    @property
    def center_x(self) -> int:
        return (self.x1 + self.x2) // 2

    @property
    def center_y(self) -> int:
        return (self.y1 + self.y2) // 2

    def intersects(self, other: Rect) -> bool:
        return self.x1 < other.x2 and self.x2 > other.x1 and self.y1 < other.y2 and self.y2 > other.y1

    def intersection_area(self, other: Rect) -> int:
        x_overlap = max(0, min(self.x2, other.x2) - max(self.x1, other.x1))
        y_overlap = max(0, min(self.y2, other.y2) - max(self.y1, other.y1))

        return x_overlap * y_overlap


@dataclass(frozen=True)
class TextPlacement:
    rect: Rect
    lines: list[str]


def place_narration(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    options: RenderOptions,
    protected_rects: list[Rect] | None = None,
    occupied: list[Rect] | None = None,
) -> TextPlacement | None:
    return choose_text_placement(
        draw=draw,
        text=text,
        font=font,
        candidates=narration_candidates(options),
        occupied=occupied or [],
        protected_rects=protected_rects or [],
        options=options,
        max_lines=5,
        preferred_index=0,
        speaker_face=None,
    )


def place_dialogue(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    options: RenderOptions,
    occupied: list[Rect],
    index: int,
    protected_rects: list[Rect] | None = None,
    speaker_face: Rect | None = None,
) -> TextPlacement | None:
    return choose_text_placement(
        draw=draw,
        text=text,
        font=font,
        candidates=dialogue_candidates(options, index),
        occupied=occupied,
        protected_rects=protected_rects or [],
        options=options,
        max_lines=4,
        preferred_index=0,
        speaker_face=speaker_face if options.bubble_anchor_aware else None,
    )


def choose_text_placement(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    candidates: list[Rect],
    occupied: list[Rect],
    protected_rects: list[Rect],
    options: RenderOptions,
    max_lines: int,
    preferred_index: int,
    speaker_face: Rect | None,
) -> TextPlacement | None:
    best_score: float | None = None
    best_placement: TextPlacement | None = None

    for index, candidate in enumerate(candidates):
        placement = fit_text_in_candidate(draw, text, font, candidate, options, max_lines)

        if not placement:
            continue

        if any(placement.rect.intersects(rect) for rect in occupied):
            continue

        if any(placement.rect.intersects(rect) for rect in protected_rects):
            continue

        score = placement_score(
            placement.rect,
            options,
            index,
            preferred_index,
            speaker_face,
        )

        if best_score is None or score < best_score:
            best_score = score
            best_placement = placement

    return best_placement


def fit_text_in_candidate(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    candidate: Rect,
    options: RenderOptions,
    max_lines: int,
) -> TextPlacement | None:
    text_padding_x = options.text_safe_margin
    text_padding_y = max(6, options.text_safe_margin - round(8 * options.font_scale))
    max_text_width = candidate.width - (text_padding_x * 2)
    minimum_text_width = max(54, round(120 * options.font_scale))

    if max_text_width <= minimum_text_width:
        return None

    lines = wrap_text(draw, text, font, max_text_width)[:max_lines]

    if not lines:
        return None

    line_height = text_height(draw, "Ag", font) + max(4, round(9 * options.font_scale))
    box_height = (len(lines) * line_height) + (text_padding_y * 2)

    if box_height > candidate.height:
        return None

    return TextPlacement(
        rect=Rect(
            x1=candidate.x1,
            y1=candidate.y1,
            x2=candidate.x2,
            y2=candidate.y1 + box_height,
        ),
        lines=lines,
    )


def placement_score(
    rect: Rect,
    options: RenderOptions,
    index: int,
    preferred_index: int,
    speaker_face: Rect | None,
) -> float:
    score = abs(index - preferred_index) * 100.0

    if options.avoid_center_subject:
        center_overlap = protected_subject_area(options).intersection_area(rect) / max(1, rect.area)
        score += center_overlap * 5000.0

    if speaker_face is not None:
        score += anchor_side_penalty(rect, speaker_face, options) * 200.0

    return score


def anchor_side_penalty(rect: Rect, speaker_face: Rect, options: RenderOptions) -> float:
    page_center = options.page_width / 2
    face_on_left = speaker_face.center_x < page_center
    rect_on_left = rect.center_x < page_center

    if face_on_left == rect_on_left:
        return 1.0

    return 0.0


def narration_candidates(options: RenderOptions) -> list[Rect]:
    padding = options.padding
    side_width = int((options.page_width - (padding * 2)) * options.caption_max_width_ratio)
    max_height = int(options.panel_height * 0.32)
    bottom_strip_height = int(options.panel_height * 0.18)

    candidates = [
        Rect(padding, padding, options.page_width - padding, padding + max_height),
        Rect(padding, padding, padding + side_width, padding + max_height),
        Rect(options.page_width - padding - side_width, padding, options.page_width - padding, padding + max_height),
        Rect(padding, int(options.panel_height * 0.58), padding + side_width, int(options.panel_height * 0.9)),
        Rect(
            options.page_width - padding - side_width,
            int(options.panel_height * 0.58),
            options.page_width - padding,
            int(options.panel_height * 0.9),
        ),
        Rect(
            padding,
            options.panel_height - padding - bottom_strip_height,
            options.page_width - padding,
            options.panel_height - padding,
        ),
    ]

    if not options.avoid_center_subject:
        return candidates

    return [
        candidates[0],
        candidates[5],
        candidates[1],
        candidates[2],
        candidates[4],
        candidates[3],
    ]


def dialogue_candidates(options: RenderOptions, index: int) -> list[Rect]:
    padding = options.padding
    bubble_width = int((options.page_width - (padding * 2)) * options.bubble_max_width_ratio)
    candidate_height = int(options.panel_height * 0.22)

    columns_x = _candidate_columns(options, bubble_width)
    rows_y = _candidate_rows(options, candidate_height)

    candidates: list[Rect] = []

    for row_y in rows_y:
        if index % 2 == 0:
            column_order = columns_x
        else:
            column_order = list(reversed(columns_x))

        for column_x in column_order:
            x1 = column_x
            x2 = column_x + bubble_width
            y1 = row_y
            y2 = min(options.panel_height - padding, row_y + candidate_height)

            if y2 - y1 < int(candidate_height * 0.6):
                continue

            candidates.append(Rect(x1, y1, x2, y2))

    return candidates


def _candidate_columns(options: RenderOptions, bubble_width: int) -> list[int]:
    padding = options.padding
    left = padding
    right = options.page_width - padding - bubble_width
    middle = (options.page_width - bubble_width) // 2
    columns = [left, right]

    if middle > left and middle + bubble_width < options.page_width - padding:
        columns.append(middle)

    return columns


def _candidate_rows(options: RenderOptions, candidate_height: int) -> list[int]:
    padding = options.padding
    top = max(padding, int(options.panel_height * 0.06))
    bottom_limit = options.panel_height - padding - int(candidate_height * 0.6)

    if bottom_limit <= top:
        return [top]

    return [
        top,
        int(options.panel_height * 0.22),
        int(options.panel_height * 0.40),
        int(options.panel_height * 0.58),
        int(options.panel_height * 0.74),
        bottom_limit,
    ]


def protected_subject_area(options: RenderOptions) -> Rect:
    width = int(options.page_width * options.center_subject_width_ratio)
    height = int(options.panel_height * options.center_subject_height_ratio)
    x1 = (options.page_width - width) // 2
    y1 = int(options.panel_height * 0.18)

    return Rect(x1, y1, x1 + width, y1 + height)
