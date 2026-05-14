from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont

try:
    from .faces import assign_speaker_faces, detect_faces, inflate_faces
    from .models import Dialogue, RenderOptions, SceneImage, ScenePanel
    from .placement import Rect, fit_text_in_candidate, place_dialogue, place_narration
    from .text import load_font, text_height, wrap_text
except ImportError:
    from faces import assign_speaker_faces, detect_faces, inflate_faces
    from models import Dialogue, RenderOptions, SceneImage, ScenePanel
    from placement import Rect, fit_text_in_candidate, place_dialogue, place_narration
    from text import load_font, text_height, wrap_text


PANEL_BORDER_RADIUS = 26
TEXT_BOX_RADIUS = 18
BASE_PANEL_WIDTH = 800
BASE_PANEL_HEIGHT = 980
DIALOGUE_BASE_FONT_SIZE = 19
NARRATION_BASE_FONT_SIZE = DIALOGUE_BASE_FONT_SIZE


def render_panel(scene: ScenePanel, options: RenderOptions) -> Image.Image:
    panel, face_rects = prepare_panel_context(scene, options)
    draw = ImageDraw.Draw(panel, "RGBA")

    draw.rounded_rectangle(
        (0, 0, options.page_width - 1, options.panel_height - 1),
        radius=scaled_size(options, PANEL_BORDER_RADIUS, minimum=10),
        outline=(255, 255, 255, 80),
        width=3,
    )

    occupied = render_narrations(draw, scene.narrations, options, face_rects)
    render_dialogues(draw, scene.dialogues, options, occupied, face_rects)

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
        draw=draw,
        placement=placement,
        font=font,
        options=options,
        fill_box=(0, 0, 0, 170),
        text_color=(255, 255, 255, 245),
    )

    return [placement.rect]


def render_dialogues(
    draw: ImageDraw.ImageDraw,
    dialogues: list[Dialogue],
    options: RenderOptions,
    occupied: list[Rect],
    face_rects: list[Rect],
) -> None:
    if not dialogues:
        return

    speaker_face_map = assign_speaker_faces(face_rects, len(dialogues[:4]))

    for index, dialogue in enumerate(dialogues[:4]):
        label = f"{dialogue.character}: " if dialogue.character else ""
        full_text = f"{label}{dialogue.content}"
        speaker_face = speaker_face_map.get(index)

        placement, font, font_size = find_text_placement(
            lambda font: place_dialogue(
                draw,
                full_text,
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
                text=full_text,
                options=options,
                occupied=occupied,
            )

        if not placement or not font:
            continue

        bold_font = load_font(font_size, bold=True)

        draw_dialogue_box(
            draw=draw,
            placement=placement,
            font=font,
            bold_font=bold_font,
            options=options,
            character=dialogue.character,
        )

        occupied.append(placement.rect)


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
    draw: ImageDraw.ImageDraw,
    placement,
    font: ImageFont.ImageFont,
    options: RenderOptions,
    fill_box: tuple[int, int, int, int],
    text_color: tuple[int, int, int, int],
) -> None:
    line_height = text_height(draw, "Ag", font) + scaled_size(options, 9, minimum=4)
    x1 = placement.rect.x1
    y1 = placement.rect.y1
    x2 = placement.rect.x2
    y2 = placement.rect.y2

    draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=scaled_size(options, TEXT_BOX_RADIUS, minimum=7),
        fill=fill_box,
    )

    for index, line in enumerate(placement.lines):
        draw.text(
            (x1 + options.text_safe_margin, y1 + scaled_size(options, 14, minimum=5) + (index * line_height)),
            line,
            font=font,
            fill=text_color,
        )


def draw_dialogue_box(
    draw: ImageDraw.ImageDraw,
    placement,
    font: ImageFont.ImageFont,
    bold_font: ImageFont.ImageFont,
    options: RenderOptions,
    character: str | None,
) -> None:
    line_height = text_height(draw, "Ag", font) + scaled_size(options, 9, minimum=4)
    x1 = placement.rect.x1
    y1 = placement.rect.y1
    x2 = placement.rect.x2
    y2 = placement.rect.y2

    draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=scaled_size(options, TEXT_BOX_RADIUS, minimum=7),
        fill=(255, 255, 255, 235),
    )

    for index, line in enumerate(placement.lines):
        draw_dialogue_line(
            draw=draw,
            line=line,
            character=character,
            x=x1 + options.text_safe_margin,
            y=y1 + scaled_size(options, 14, minimum=5) + (index * line_height),
            font=font,
            bold_font=bold_font,
        )


def draw_dialogue_line(
    draw: ImageDraw.ImageDraw,
    line: str,
    character: str | None,
    x: int,
    y: int,
    font: ImageFont.ImageFont,
    bold_font: ImageFont.ImageFont,
) -> None:
    if character and line.startswith(f"{character}:"):
        label = f"{character}:"
        draw.text((x, y), label, font=bold_font, fill=(11, 18, 32, 255))
        label_width = draw.textlength(label, font=bold_font)
        draw.text((x + label_width + 6, y), line[len(label) :].lstrip(), font=font, fill=(11, 18, 32, 255))

        return

    draw.text((x, y), line, font=font, fill=(11, 18, 32, 255))


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
