from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .models import RenderOptions
    from .renderer import render_story_file, render_story_file_to_scene_images
except ImportError:
    from models import RenderOptions
    from renderer import render_story_file, render_story_file_to_scene_images


def main() -> None:
    args = parse_args()
    options = RenderOptions(
        layout_mode=args.mode,
        page_width=args.width,
        panel_height=args.panel_height,
        page_height=args.page_height,
        classic_panels_per_page=args.panels_per_page,
        theme_dark=not args.light,
        avoid_center_subject=not args.allow_center_text,
        caption_max_width_ratio=args.caption_width_ratio,
        bubble_max_width_ratio=args.bubble_width_ratio,
        text_safe_margin=args.text_safe_margin,
        face_detection_enabled=not args.disable_face_detection,
        bubble_anchor_aware=not args.disable_anchor_aware,
        debug_faces=args.debug_faces,
    )
    output_dir = args.output_dir

    if output_dir is None:
        output_dir = args.input.parent / "output" if args.scene_images else Path("output")

    if args.scene_images:
        saved_paths = render_story_file_to_scene_images(args.input, output_dir, options=options)
    else:
        saved_paths = render_story_file(args.input, output_dir, options=options)

    if not saved_paths:
        print("No images were generated. Check if the input JSON contains scenes[].")
        return

    for saved_path in saved_paths:
        print(saved_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render MakeStory API JSON into comic PNG pages.")
    parser.add_argument("input", nargs="?", default="input.json", type=Path, help="Path to MakeStory API JSON.")
    parser.add_argument(
        "--output-dir",
        default=None,
        type=Path,
        help="Directory where page_1.png, page_2.png, ... will be saved, or where the story folder is created with --scene-images. Defaults to output for pages and <input-dir>/output for scene images.",
    )
    parser.add_argument(
        "--scene-images",
        action="store_true",
        help="Save each scene as one PNG under <output-dir>/<story_id>/ instead of composing pages.",
    )
    parser.add_argument("--mode", choices=["webtoon", "classic"], default="webtoon", help="Comic layout mode.")
    parser.add_argument("--width", default=800, type=int, help="Output page width in pixels.")
    parser.add_argument("--panel-height", default=980, type=int, help="Single panel height in pixels.")
    parser.add_argument("--page-height", default=1200, type=int, help="Classic page height in pixels.")
    parser.add_argument("--panels-per-page", choices=[2, 3, 4], default=4, type=int, help="Panels per classic page.")
    parser.add_argument("--light", action="store_true", help="Use a light page background.")
    parser.add_argument(
        "--allow-center-text",
        action="store_true",
        help="Allow text boxes to overlap the likely central subject area.",
    )
    parser.add_argument(
        "--caption-width-ratio",
        default=0.55,
        type=float,
        help="Maximum narration caption width as a ratio of the panel width.",
    )
    parser.add_argument(
        "--bubble-width-ratio",
        default=0.38,
        type=float,
        help="Maximum dialogue bubble width as a ratio of the panel width.",
    )
    parser.add_argument("--text-safe-margin", default=22, type=int, help="Internal padding for captions and bubbles.")
    parser.add_argument(
        "--disable-face-detection",
        action="store_true",
        help="Skip MediaPipe face detection (text placement falls back to the static center heuristic).",
    )
    parser.add_argument(
        "--disable-anchor-aware",
        action="store_true",
        help="Do not bias dialogue bubbles toward the side opposite the speaker's face.",
    )
    parser.add_argument(
        "--debug-faces",
        action="store_true",
        help="Draw detected face bounding boxes on top of each panel for inspection.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    main()

