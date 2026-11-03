from __future__ import annotations

import random
from io import BytesIO
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    from .faces import assign_speaker_faces, detect_faces, inflate_faces
    from .models import Dialogue, RenderOptions, SceneImage, ScenePanel
    from .placement import Rect, fit_text_in_candidate, place_dialogue, place_narration
    from .text import load_display_font, load_font, text_height, text_width, wrap_text
except ImportError:
    from faces import assign_speaker_faces, detect_faces, inflate_faces
    from models import Dialogue, RenderOptions, SceneImage, ScenePanel
    from placement import Rect, fit_text_in_candidate, place_dialogue, place_narration
    from text import load_display_font, load_font, text_height, text_width, wrap_text


PANEL_BORDER_RADIUS = 26
NARRATION_BOX_RADIUS = 0
BUBBLE_BOX_MAX_RADIUS = 56
BASE_PANEL_WIDTH = 800
BASE_PANEL_HEIGHT = 980
DIALOGUE_BASE_FONT_SIZE = 19
NARRATION_BASE_FONT_SIZE = DIALOGUE_BASE_FONT_SIZE
BUBBLE_FILL = (255, 255, 255, 242)
BUBBLE_OUTLINE = (18, 22, 32, 255)
DIALOGUE_TEXT_COLOR = (14, 18, 28, 255)
TAG_TEXT_COLOR = (255, 255, 255, 255)
CHARACTER_TAG_PALETTE = [
    (214, 40, 57),
    (33, 118, 174),
    (45, 149, 98),
    (155, 81, 224),
    (224, 122, 33),
    (193, 41, 130),
    (38, 137, 137),
    (120, 94, 60),
]


def render_panel(scene: ScenePanel, options: RenderOptions) -> Image.Image:
    panel, face_rects = prepare_panel_context(scene, options)
    draw = ImageDraw.Draw(panel, "RGBA")

    draw.rounded_rectangle(
        (0, 0, options.page_width - 1, options.panel_height - 1),
        radius=scaled_size(options, PANEL_BORDER_RADIUS, minimum=10),
        outline=(255, 255, 255, 80),
        width=3,
    )

    occupied = render_narrations(panel, draw, scene.narrations, options, face_rects)
    render_dialogues(panel, draw, scene.dialogues, options, occupied, face_rects, scene.scene_id)

    if options.debug_faces:
        draw_face_debug(draw, face_rects)

    return panel


def prepare_panel_context(scene: ScenePanel, options: RenderOptions) -> tuple[Image.Image, list[Rect]]:
    panel = create_panel_background(scene.image, options)

    if not options.face_detection_enabled:
        return panel, []

    raw_faces = detect_faces(panel, min_confidence=options.face_detection_confidence)

    if not raw_faces:
        return panel, []

    return panel, inflate_faces(raw_faces, panel.size, options.face_safety_margin_ratio)


def create_panel_background(image: SceneImage | None, options: RenderOptions) -> Image.Image:
    if image and image.image_status == "generated" and image.image_url:
        loaded_image = load_scene_image(image.image_url, options.image_timeout_seconds)

        if loaded_image:
            return crop_cover(loaded_image, (options.page_width, options.panel_height))

    return create_placeholder(image, options)


def load_scene_image(image_url: str, timeout_seconds: int) -> Image.Image | None:
    try:
        if image_url.startswith(("http://", "https://")):
            request = Request(
                image_url,
                headers={
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    "User-Agent": "Mozilla/5.0 (compatible; MakeStoryHQRenderer/1.0)",
                },
            )

            with urlopen(request, timeout=timeout_seconds) as response:
                return Image.open(BytesIO(response.read())).convert("RGB")

        local_path = Path(image_url).expanduser()

        if local_path.exists():
            return Image.open(local_path).convert("RGB")
    except (OSError, URLError, TimeoutError, ValueError):
        return None

    return None


def crop_cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_width, target_height = size
    image_width, image_height = image.size
    scale = max(target_width / image_width, target_height / image_height)
    resized_size = (round(image_width * scale), round(image_height * scale))
    resized = image.resize(resized_size, Image.Resampling.LANCZOS)
    left = (resized.width - target_width) // 2
    top = (resized.height - target_height) // 2

    return resized.crop((left, top, left + target_width, top + target_height))


def create_placeholder(image: SceneImage | None, options: RenderOptions) -> Image.Image:
    background = Image.new("RGB", (options.page_width, options.panel_height), (18, 24, 38))
    draw = ImageDraw.Draw(background, "RGBA")
    title_font = load_font(scaled_size(options, 34, minimum=18), bold=True)
    body_font = load_font(scaled_size(options, 22, minimum=12))
    title = "Image not available"
    subtitle = image.content if image and image.content else "MakeStory scene without generated image"
    center_x = options.page_width // 2
    center_y = options.panel_height // 2

    for offset in range(0, options.panel_height, 18):
        alpha = max(10, 70 - offset // 8)
        draw.line((0, offset, options.page_width, offset + options.page_width), fill=(88, 99, 255, alpha), width=3)

    placeholder_box_height = scaled_size(options, 220, minimum=110)
    draw.rounded_rectangle(
        (
            options.padding,
            center_y - (placeholder_box_height // 2),
            options.page_width - options.padding,
            center_y + (placeholder_box_height // 2),
        ),
        radius=scaled_size(options, 30, minimum=12),
        fill=(8, 13, 26, 185),
        outline=(255, 255, 255, 45),
        width=2,
    )

    draw_centered_text(draw, title, center_x, center_y - scaled_size(options, 42, minimum=20), title_font, (255, 255, 255, 245))

    for index, line in enumerate(wrap_text(draw, subtitle, body_font, options.page_width - 160)[:3]):
        draw_centered_text(
            draw,
            line,
            center_x,
            center_y + scaled_size(options, 16, minimum=8) + (index * scaled_size(options, 32, minimum=16)),
            body_font,
            (203, 213, 225, 240),
        )

    return background


def render_narrations(
    panel: Image.Image,
    draw: ImageDraw.ImageDraw,
    narrations: list[str],
    options: RenderOptions,
    face_rects: list[Rect],
) -> list[Rect]:
    if not narrations:
        return []

    text = " ".join(narrations)
    placement, font, _ = find_text_placement(
        lambda font: place_narration(draw, text, font, options, protected_rects=face_rects),
        base_size=NARRATION_BASE_FONT_SIZE,
        minimum=9,
        bold=False,
        options=options,
    )

    if not placement or not font:
        return []

    draw_text_box(
        panel=panel,
        draw=draw,
        placement=placement,
        font=font,
        options=options,
        fill_box=(0, 0, 0, 200),
        text_color=(255, 255, 255, 245),
        radius=NARRATION_BOX_RADIUS,
        shadow_offset=(4, 6),
        shadow_blur=8,
        shadow_alpha=170,
    )

    return [placement.rect]


def render_dialogues(
    panel: Image.Image,
    draw: ImageDraw.ImageDraw,
    dialogues: list[Dialogue],
    options: RenderOptions,
    occupied: list[Rect],
    face_rects: list[Rect],
    scene_id: int | str | None,
) -> None:
    if not dialogues:
        return

    speaker_face_map = assign_speaker_faces(face_rects, len(dialogues[:4]))

    for index, dialogue in enumerate(dialogues[:4]):
        use_tag = options.character_tag_enabled and bool(dialogue.character)

        if use_tag:
            placement_text = dialogue.content
        elif dialogue.character:
            placement_text = f"{dialogue.character}: {dialogue.content}"
        else:
            placement_text = dialogue.content

        speaker_face = speaker_face_map.get(index)

        placement, font, font_size = find_text_placement(
            lambda font: place_dialogue(
                draw,
                placement_text,
                font,
                options,
                occupied,
                index,
                protected_rects=face_rects,
                speaker_face=speaker_face,
            ),
            base_size=DIALOGUE_BASE_FONT_SIZE,
            minimum=9,
            bold=False,
            options=options,
        )

        if not placement:
            placement, font, font_size = bottom_bar_fallback(
                draw=draw,
                text=placement_text,
                options=options,
                occupied=occupied,
            )

        if not placement or not font:
            continue

        bold_font = load_font(font_size, bold=True)
        rect = jitter_rect(placement.rect, options, occupied, face_rects, scene_id, index)

        draw_dialogue_box(
            panel=panel,
            draw=draw,
            rect=rect,
            lines=placement.lines,
            font=font,
            bold_font=bold_font,
            options=options,
            character=dialogue.character if use_tag else None,
            inline_character=dialogue.character if (not use_tag and dialogue.character) else None,
            font_size=font_size,
            speaker_face=speaker_face,
        )

        occupied.append(rect)


def jitter_rect(
    rect: Rect,
    options: RenderOptions,
    occupied: list[Rect],
    face_rects: list[Rect],
    scene_id: int | str | None,
    index: int,
) -> Rect:
    magnitude = scaled_size(options, options.position_jitter_px, minimum=0)

    if magnitude <= 0:
        return rect

    rng = random.Random(f"{scene_id}:{index}:{rect.x1}:{rect.y1}")
    offset_x = rng.randint(-magnitude, magnitude)
    offset_y = rng.randint(-magnitude, magnitude)

    offset_x = max(options.padding - rect.x1, min(options.page_width - options.padding - rect.x2, offset_x))
    offset_y = max(options.padding - rect.y1, min(options.panel_height - options.padding - rect.y2, offset_y))

    moved = Rect(rect.x1 + offset_x, rect.y1 + offset_y, rect.x2 + offset_x, rect.y2 + offset_y)

    if any(moved.intersects(other) for other in occupied):
        return rect

    if any(moved.intersects(other) for other in face_rects):
        return rect

    return moved


def find_text_placement(
    placer,
    base_size: int,
    minimum: int,
    bold: bool,
    options: RenderOptions,
):
    last_font = None
    last_size = scaled_size(options, base_size, minimum=minimum)

    for scale in options.shrink_retry_steps:
        size = scaled_size(options, round(base_size * scale), minimum=minimum)
        font = load_font(size, bold=bold)
        last_font = font
        last_size = size
        placement = placer(font)

        if placement:
            return placement, font, size

    return None, last_font, last_size


def bottom_bar_fallback(
    draw: ImageDraw.ImageDraw,
    text: str,
    options: RenderOptions,
    occupied: list[Rect],
):
    padding = options.padding
    strip_height = int(options.panel_height * 0.22)
    candidate = Rect(
        x1=padding,
        y1=options.panel_height - padding - strip_height,
        x2=options.page_width - padding,
        y2=options.panel_height - padding,
    )

    for scale in options.shrink_retry_steps:
        size = scaled_size(options, round(DIALOGUE_BASE_FONT_SIZE * scale), minimum=9)
        font = load_font(size, bold=False)
        placement = fit_text_in_candidate(draw, text, font, candidate, options, max_lines=4)

        if not placement:
            continue

        if any(placement.rect.intersects(rect) for rect in occupied):
            continue

        return placement, font, size

    return None, None, scaled_size(options, DIALOGUE_BASE_FONT_SIZE, minimum=9)


def draw_text_box(
    panel: Image.Image,
    draw: ImageDraw.ImageDraw,
    placement,
    font: ImageFont.ImageFont,
    options: RenderOptions,
    fill_box: tuple[int, int, int, int],
    text_color: tuple[int, int, int, int],
    radius: int,
    shadow_offset: tuple[int, int] = (3, 5),
    shadow_blur: int = 6,
    shadow_alpha: int = 150,
) -> None:
    line_height = text_height(draw, "Ag", font) + scaled_size(options, 9, minimum=4)
    x1 = placement.rect.x1
    y1 = placement.rect.y1
    x2 = placement.rect.x2
    y2 = placement.rect.y2
    scaled_radius = scaled_size(options, radius, minimum=0) if radius > 0 else 0

    paint_drop_shadow(
        panel=panel,
        rect=(x1, y1, x2, y2),
        radius=scaled_radius,
        offset=shadow_offset,
        blur=shadow_blur,
        alpha=shadow_alpha,
    )

    if scaled_radius > 0:
        draw.rounded_rectangle((x1, y1, x2, y2), radius=scaled_radius, fill=fill_box)
    else:
        draw.rectangle((x1, y1, x2, y2), fill=fill_box)

    for index, line in enumerate(placement.lines):
        draw.text(
            (x1 + options.text_safe_margin, y1 + scaled_size(options, 14, minimum=5) + (index * line_height)),
            line,
            font=font,
            fill=text_color,
        )


def draw_dialogue_box(
    panel: Image.Image,
    draw: ImageDraw.ImageDraw,
    rect: Rect,
    lines: list[str],
    font: ImageFont.ImageFont,
    bold_font: ImageFont.ImageFont,
    options: RenderOptions,
    character: str | None,
    inline_character: str | None,
    font_size: int,
    speaker_face: Rect | None,
) -> None:
    line_height = text_height(draw, "Ag", font) + scaled_size(options, 9, minimum=4)
    tag_height = scaled_size(options, font_size + 12, minimum=14) if character else 0
    top_reserve = (tag_height // 2) if character else 0

    x1 = rect.x1
    y1 = max(options.padding, rect.y1 - top_reserve)
    x2 = rect.x2
    y2 = rect.y2
    box_height = y2 - y1
    box_width = x2 - x1
    radius = min(
        scaled_size(options, BUBBLE_BOX_MAX_RADIUS, minimum=12),
        box_height // 2,
        box_width // 2,
    )

    paint_drop_shadow(
        panel=panel,
        rect=(x1, y1, x2, y2),
        radius=radius,
        offset=(3, 6),
        blur=8,
        alpha=130,
    )

    if options.bubble_tail_enabled and speaker_face is not None:
        draw_bubble_tail(draw, Rect(x1, y1, x2, y2), speaker_face, options)

    draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=radius,
        fill=BUBBLE_FILL,
        outline=BUBBLE_OUTLINE,
        width=max(1, options.bubble_outline_width),
    )

    if options.bubble_tail_enabled and speaker_face is not None:
        draw_bubble_tail(draw, Rect(x1, y1, x2, y2), speaker_face, options, fill_only=True)

    text_top = y1 + top_reserve + scaled_size(options, 12, minimum=5)

    for index, line in enumerate(lines):
        draw_dialogue_line(
            draw=draw,
            line=line,
            inline_character=inline_character,
            x=x1 + options.text_safe_margin,
            y=text_top + (index * line_height),
            font=font,
            bold_font=bold_font,
        )

    if character:
        draw_character_tag(draw, character, x1, y1, options, font_size)


def draw_bubble_tail(
    draw: ImageDraw.ImageDraw,
    rect: Rect,
    target: Rect,
    options: RenderOptions,
    fill_only: bool = False,
) -> None:
    target_x = target.center_x
    target_y = target.center_y
    delta_x = target_x - rect.center_x
    delta_y = target_y - rect.center_y
    base_half = scaled_size(options, 16, minimum=6)
    tail_length = scaled_size(options, 42, minimum=14)

    if abs(delta_y) >= abs(delta_x):
        edge_y = rect.y2 if delta_y >= 0 else rect.y1
        anchor_x = min(max(target_x, rect.x1 + base_half * 2), rect.x2 - base_half * 2)
        base_left = (anchor_x - base_half, edge_y)
        base_right = (anchor_x + base_half, edge_y)
        tip_y = edge_y + (tail_length if delta_y >= 0 else -tail_length)
        tip = (anchor_x + delta_x // 6, tip_y)
    else:
        edge_x = rect.x2 if delta_x >= 0 else rect.x1
        anchor_y = min(max(target_y, rect.y1 + base_half * 2), rect.y2 - base_half * 2)
        base_left = (edge_x, anchor_y - base_half)
        base_right = (edge_x, anchor_y + base_half)
        tip_x = edge_x + (tail_length if delta_x >= 0 else -tail_length)
        tip = (tip_x, anchor_y + delta_y // 6)

    draw.polygon([base_left, base_right, tip], fill=BUBBLE_FILL)

    if not fill_only:
        return

    width = max(1, options.bubble_outline_width)
    draw.line([base_left, tip], fill=BUBBLE_OUTLINE, width=width)
    draw.line([base_right, tip], fill=BUBBLE_OUTLINE, width=width)


def draw_character_tag(
    draw: ImageDraw.ImageDraw,
    character: str,
    box_x1: int,
    box_y1: int,
    options: RenderOptions,
    font_size: int,
) -> None:
    name = character.upper()
    tag_font = load_display_font(scaled_size(options, font_size + 2, minimum=11))
    padding_x = scaled_size(options, 12, minimum=5)
    text_w = text_width(draw, name, tag_font)
    text_h = text_height(draw, "Ag", tag_font)
    tag_w = text_w + (padding_x * 2)
    tag_h = text_h + scaled_size(options, 10, minimum=4)
    tag_x1 = box_x1 + scaled_size(options, 14, minimum=6)
    tag_y1 = box_y1 - (tag_h // 2)
    tag_x2 = tag_x1 + tag_w
    tag_y2 = tag_y1 + tag_h
    color = character_color(character)

    draw.rounded_rectangle(
        (tag_x1, tag_y1, tag_x2, tag_y2),
        radius=tag_h // 2,
        fill=(*color, 255),
        outline=BUBBLE_OUTLINE,
        width=max(1, options.bubble_outline_width),
    )
    draw.text(
        (tag_x1 + padding_x, tag_y1 + (tag_h - text_h) // 2 - scaled_size(options, 2, minimum=0)),
        name,
        font=tag_font,
        fill=TAG_TEXT_COLOR,
    )


def character_color(character: str) -> tuple[int, int, int]:
    index = sum(ord(char) for char in character) % len(CHARACTER_TAG_PALETTE)

    return CHARACTER_TAG_PALETTE[index]


def paint_drop_shadow(
    panel: Image.Image,
    rect: tuple[int, int, int, int],
    radius: int,
    offset: tuple[int, int],
    blur: int,
    alpha: int,
) -> None:
    if alpha <= 0:
        return

    x1, y1, x2, y2 = rect
    offset_x, offset_y = offset
    mask = Image.new("L", panel.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    shadow_box = (x1 + offset_x, y1 + offset_y, x2 + offset_x, y2 + offset_y)

    if radius > 0:
        mask_draw.rounded_rectangle(shadow_box, radius=radius, fill=alpha)
    else:
        mask_draw.rectangle(shadow_box, fill=alpha)

    if blur > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=blur))

    overlay = Image.new("RGB", panel.size, (0, 0, 0))
    panel.paste(overlay, (0, 0), mask)


def draw_dialogue_line(
    draw: ImageDraw.ImageDraw,
    line: str,
    inline_character: str | None,
    x: int,
    y: int,
    font: ImageFont.ImageFont,
    bold_font: ImageFont.ImageFont,
) -> None:
    if inline_character and line.startswith(f"{inline_character}:"):
        label = f"{inline_character}:"
        draw.text((x, y), label, font=bold_font, fill=DIALOGUE_TEXT_COLOR)
        label_width = draw.textlength(label, font=bold_font)
        draw.text((x + label_width + 6, y), line[len(label) :].lstrip(), font=font, fill=DIALOGUE_TEXT_COLOR)

        return

    draw.text((x, y), line, font=font, fill=DIALOGUE_TEXT_COLOR)


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    center_x: int,
    y: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
) -> None:
    width = draw.textlength(text, font=font)
    draw.text((center_x - (width / 2), y), text, font=font, fill=fill)


def draw_face_debug(draw: ImageDraw.ImageDraw, face_rects: list[Rect]) -> None:
    for rect in face_rects:
        draw.rectangle(
            (rect.x1, rect.y1, rect.x2, rect.y2),
            outline=(255, 64, 192, 255),
            width=3,
        )


def scaled_size(options: RenderOptions, value: int, minimum: int) -> int:
    return max(minimum, round(value * options.font_scale))
