from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


LayoutMode = Literal["webtoon", "classic"]


@dataclass(frozen=True)
class Dialogue:
    character: str | None
    content: str


@dataclass(frozen=True)
class SceneImage:
    image_url: str | None
    image_status: str | None
    content: str | None = None


@dataclass(frozen=True)
class ScenePanel:
    scene_id: int | str | None
    narrations: list[str]
    dialogues: list[Dialogue]
    image: SceneImage | None


@dataclass(frozen=True)
class RenderOptions:
    layout_mode: LayoutMode = "webtoon"
    page_width: int = 800
    panel_height: int = 980
    page_height: int = 1200
    padding: int = 28
    gutter: int = 28
    classic_panels_per_page: int = 4
    theme_dark: bool = True
    image_timeout_seconds: int = 12
    avoid_center_subject: bool = True
    caption_max_width_ratio: float = 0.55
    bubble_max_width_ratio: float = 0.38
    text_safe_margin: int = 22
    center_subject_width_ratio: float = 0.56
    center_subject_height_ratio: float = 0.78
    font_scale: float = 1.0
    face_detection_enabled: bool = True
    face_safety_margin_ratio: float = 0.12
    face_detection_confidence: float = 0.5
    bubble_anchor_aware: bool = True
    shrink_retry_steps: tuple[float, ...] = (1.0, 0.85, 0.72)
    debug_faces: bool = False

