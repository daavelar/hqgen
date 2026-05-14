from __future__ import annotations

from typing import Any

from PIL import Image

try:
    from .placement import Rect
except ImportError:
    from placement import Rect


_face_detector: Any | None = None
_face_detector_failed: bool = False


def detect_faces(image: Image.Image, min_confidence: float = 0.5) -> list[Rect]:
    detector = _get_detector(min_confidence)

    if detector is None:
        return []

    try:
        import numpy as np

        rgb_array = np.array(image.convert("RGB"))
        results = detector.process(rgb_array)
    except Exception:
        return []

    if not getattr(results, "detections", None):
        return []

    width, height = image.size
    face_rects: list[Rect] = []

    for detection in results.detections:
        rect = _detection_to_rect(detection, width, height)

        if rect is not None:
            face_rects.append(rect)

    return face_rects


def inflate_rect(rect: Rect, margin_px: int, bounds: Rect) -> Rect:
    return Rect(
        x1=max(bounds.x1, rect.x1 - margin_px),
        y1=max(bounds.y1, rect.y1 - margin_px),
        x2=min(bounds.x2, rect.x2 + margin_px),
        y2=min(bounds.y2, rect.y2 + margin_px),
    )


def inflate_faces(face_rects: list[Rect], image_size: tuple[int, int], margin_ratio: float) -> list[Rect]:
    width, height = image_size
    bounds = Rect(0, 0, width, height)
    inflated: list[Rect] = []

    for face in face_rects:
        margin_px = round(max(face.width, face.height) * margin_ratio)
        inflated.append(inflate_rect(face, margin_px, bounds))

    return inflated


def assign_speaker_faces(face_rects: list[Rect], dialogue_count: int) -> dict[int, Rect]:
    if not face_rects or dialogue_count <= 0:
        return {}

    sorted_faces = sorted(face_rects, key=lambda rect: rect.x1)
    assignments: dict[int, Rect] = {}

    for index in range(dialogue_count):
        if index < len(sorted_faces):
            assignments[index] = sorted_faces[index]
            continue

        assignments[index] = sorted_faces[index % len(sorted_faces)]

    return assignments


def _get_detector(min_confidence: float) -> Any | None:
    global _face_detector, _face_detector_failed

    if _face_detector_failed:
        return None

    if _face_detector is not None:
        return _face_detector

    try:
        import mediapipe as mp

        _face_detector = mp.solutions.face_detection.FaceDetection(
            model_selection=1,
            min_detection_confidence=min_confidence,
        )
        return _face_detector
    except Exception:
        _face_detector_failed = True
        return None


def _detection_to_rect(detection: Any, image_width: int, image_height: int) -> Rect | None:
    try:
        bbox = detection.location_data.relative_bounding_box
    except AttributeError:
        return None

    x1 = max(0, round(bbox.xmin * image_width))
    y1 = max(0, round(bbox.ymin * image_height))
    x2 = min(image_width, round((bbox.xmin + bbox.width) * image_width))
    y2 = min(image_height, round((bbox.ymin + bbox.height) * image_height))

    if x2 <= x1 or y2 <= y1:
        return None

    return Rect(x1=x1, y1=y1, x2=x2, y2=y2)
