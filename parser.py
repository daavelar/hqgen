from __future__ import annotations

from collections.abc import Mapping
from typing import Any

try:
    from .models import Dialogue, SceneImage, ScenePanel
except ImportError:
    from models import Dialogue, SceneImage, ScenePanel


def parse_story_scenes(story_json: Mapping[str, Any]) -> list[ScenePanel]:
    scenes = story_json.get("scenes")

    if not isinstance(scenes, list):
        return []

    return [parse_scene(scene) for scene in scenes if isinstance(scene, Mapping)]


def parse_scene(scene: Mapping[str, Any]) -> ScenePanel:
    return ScenePanel(
        scene_id=scene.get("id"),
        narrations=parse_narrations(scene.get("narrations")),
        dialogues=parse_dialogues(scene.get("dialogues")),
        image=parse_image(scene.get("image")),
    )


def parse_narrations(raw_narrations: Any) -> list[str]:
    if not isinstance(raw_narrations, list):
        return []

    narrations: list[str] = []

    for narration in raw_narrations:
        if not isinstance(narration, Mapping):
            continue

        content = normalize_text(narration.get("content"))

        if content:
            narrations.append(content)

    return narrations


def parse_dialogues(raw_dialogues: Any) -> list[Dialogue]:
    if not isinstance(raw_dialogues, list):
        return []

    dialogues: list[Dialogue] = []

    for dialogue in raw_dialogues:
        if not isinstance(dialogue, Mapping):
            continue

        content = normalize_text(dialogue.get("content"))

        if not content:
            continue

        dialogues.append(
            Dialogue(
                character=normalize_text(dialogue.get("character")),
                content=content,
            )
        )

    return dialogues


def parse_image(raw_image: Any) -> SceneImage | None:
    if not isinstance(raw_image, Mapping):
        return None

    return SceneImage(
        image_url=normalize_text(raw_image.get("image_url")),
        image_status=normalize_text(raw_image.get("image_status")),
        content=normalize_text(raw_image.get("content")),
    )


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()

    if normalized == "":
        return None

    return normalized

