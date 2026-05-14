from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from PIL import Image

try:
    from .layout import classic_panel_size, compose_pages
    from .models import RenderOptions
    from .panels import render_panel
    from .parser import parse_story_scenes
except ImportError:
    from layout import classic_panel_size, compose_pages
    from models import RenderOptions
    from panels import render_panel
    from parser import parse_story_scenes


def render_story_to_pages(story_json: dict[str, Any], options: RenderOptions | None = None) -> list[Image.Image]:
    render_options = options or RenderOptions()
    panel_options = panel_render_options(render_options)
    scenes = parse_story_scenes(story_json)
    panel_images = [render_panel(scene, panel_options) for scene in scenes]

    return compose_pages(panel_images, render_options)


def render_story_to_scene_images(story_json: dict[str, Any], options: RenderOptions | None = None) -> list[tuple[str, Image.Image]]:
    render_options = options or RenderOptions()
    panel_options = panel_render_options(render_options)
    scenes = parse_story_scenes(story_json)

    return [
        (scene_image_name(index, scene.scene_id), render_panel(scene, panel_options))
        for index, scene in enumerate(scenes, start=1)
    ]


def panel_render_options(options: RenderOptions) -> RenderOptions:
    if options.layout_mode != "classic":
        return options

    panel_width, panel_height = classic_panel_size(options)
    font_scale = min(panel_width / options.page_width, panel_height / options.panel_height)
    spacing_scale = max(0.42, font_scale)

    return replace(
        options,
        page_width=panel_width,
        panel_height=panel_height,
        padding=max(10, round(options.padding * spacing_scale)),
        gutter=max(8, round(options.gutter * spacing_scale)),
        text_safe_margin=max(9, round(options.text_safe_margin * spacing_scale)),
        caption_max_width_ratio=max(options.caption_max_width_ratio, 0.55),
        bubble_max_width_ratio=max(options.bubble_max_width_ratio, 0.44),
        font_scale=max(0.46, font_scale),
    )


def story_folder_name(story_json: dict[str, Any]) -> str:
    meta = story_json.get("meta")
    if isinstance(meta, dict) and meta.get("story_id") is not None:
        return safe_path_part(str(meta["story_id"]))

    story = story_json.get("story")
    if isinstance(story, dict) and story.get("id") is not None:
        return safe_path_part(str(story["id"]))

    return "unknown-story"


def scene_image_name(index: int, scene_id: int | str | None) -> str:
    if scene_id is None:
        return f"scene_{index:03d}.png"

    return f"scene_{index:03d}_id_{safe_path_part(str(scene_id))}.png"


def safe_path_part(value: str) -> str:
    normalized = "".join(character if character.isalnum() or character in ("-", "_") else "-" for character in value)
    normalized = normalized.strip("-_")

    return normalized or "unknown"


def render_story_file(
    input_path: str | Path,
    output_dir: str | Path,
    options: RenderOptions | None = None,
) -> list[Path]:
    input_file = Path(input_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    with input_file.open("r", encoding="utf-8") as handle:
        story_json = json.load(handle)

    pages = render_story_to_pages(story_json, options=options)
    saved_paths: list[Path] = []

    for index, page in enumerate(pages, start=1):
        page_path = destination / f"page_{index}.png"
        page.save(page_path, format="PNG", optimize=True)
        saved_paths.append(page_path)

    return saved_paths


def render_story_file_to_scene_images(
    input_path: str | Path,
    output_dir: str | Path,
    options: RenderOptions | None = None,
) -> list[Path]:
    input_file = Path(input_path)
    destination_root = Path(output_dir)

    with input_file.open("r", encoding="utf-8") as handle:
        story_json = json.load(handle)

    destination = destination_root / story_folder_name(story_json)
    destination.mkdir(parents=True, exist_ok=True)

    scene_images = render_story_to_scene_images(story_json, options=options)
    saved_paths: list[Path] = []

    for filename, image in scene_images:
        scene_path = destination / filename
        image.save(scene_path, format="PNG", optimize=True)
        saved_paths.append(scene_path)

    return saved_paths

