from __future__ import annotations

from typing import Any, Literal

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from .config import get_s3_settings
    from .models import RenderOptions
    from .renderer import render_story_to_pages, render_story_to_scene_images, story_folder_name
    from .storage import S3ImageStorage, UploadedImage
except ImportError:
    from config import get_s3_settings
    from models import RenderOptions
    from renderer import render_story_to_pages, render_story_to_scene_images, story_folder_name
    from storage import S3ImageStorage, UploadedImage


app = FastAPI(title="HQGen API", version="1.0.0")


class RenderOptionsPayload(BaseModel):
    layout_mode: Literal["webtoon", "classic"] | None = None
    page_width: int | None = Field(default=None, gt=0)
    panel_height: int | None = Field(default=None, gt=0)
    page_height: int | None = Field(default=None, gt=0)
    padding: int | None = Field(default=None, ge=0)
    gutter: int | None = Field(default=None, ge=0)
    classic_panels_per_page: int | None = Field(default=None, ge=2, le=4)
    theme_dark: bool | None = None
    image_timeout_seconds: int | None = Field(default=None, gt=0)
    avoid_center_subject: bool | None = None
    caption_max_width_ratio: float | None = Field(default=None, gt=0, le=1)
    bubble_max_width_ratio: float | None = Field(default=None, gt=0, le=1)
    text_safe_margin: int | None = Field(default=None, ge=0)
    center_subject_width_ratio: float | None = Field(default=None, gt=0, le=1)
    center_subject_height_ratio: float | None = Field(default=None, gt=0, le=1)
    font_scale: float | None = Field(default=None, gt=0)


class RenderRequest(BaseModel):
    story: dict[str, Any]
    options: RenderOptionsPayload | None = None


class UploadedImageResponse(BaseModel):
    filename: str
    key: str
    bucket: str
    content_type: str
    url: str | None


class RenderResponse(BaseModel):
    story_id: str
    mode: Literal["pages", "scenes"]
    files: list[UploadedImageResponse]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/render",
    response_model=RenderResponse,
    summary="Compose into page images",
    description=(
        "Stacks panels into full pages. In webtoon mode this is typically **one very tall image**. "
        "For **one file per scene**, use POST /render/scenes instead."
    ),
)
def render_pages(request: RenderRequest) -> RenderResponse:
    story_id = story_folder_name(request.story)
    options = build_render_options(request.options)
    pages = render_story_to_pages(request.story, options=options)

    if not pages:
        raise HTTPException(status_code=422, detail="No images were generated. Check if the JSON contains scenes[].")

    images = [(f"page_{index}.png", image) for index, image in enumerate(pages, start=1)]
    uploaded_images = upload_images(story_id, images)

    return render_response(story_id=story_id, mode="pages", uploaded_images=uploaded_images)


@app.post(
    "/render/scenes",
    response_model=RenderResponse,
    summary="One image per scene",
    description="Renders each scene as its own PNG (recommended for tall / webtoon-style readers).",
)
def render_scenes(request: RenderRequest) -> RenderResponse:
    story_id = story_folder_name(request.story)
    options = build_render_options(request.options)
    scene_images = render_story_to_scene_images(request.story, options=options)

    if not scene_images:
        raise HTTPException(status_code=422, detail="No images were generated. Check if the JSON contains scenes[].")

    uploaded_images = upload_images(story_id, scene_images)

    return render_response(story_id=story_id, mode="scenes", uploaded_images=uploaded_images)


def build_render_options(payload: RenderOptionsPayload | None) -> RenderOptions:
    if payload is None:
        return RenderOptions()

    return RenderOptions(**model_data(payload))


def model_data(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)

    return model.dict(exclude_none=True)


def upload_images(story_id: str, images: list[tuple[str, Any]]) -> list[UploadedImage]:
    try:
        storage = S3ImageStorage(get_s3_settings())
        return storage.upload_images(story_id, images)
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except (BotoCoreError, ClientError) as error:
        raise HTTPException(status_code=502, detail=f"Failed to upload images to S3: {error}") from error


def render_response(story_id: str, mode: Literal["pages", "scenes"], uploaded_images: list[UploadedImage]) -> RenderResponse:
    return RenderResponse(
        story_id=story_id,
        mode=mode,
        files=[
            UploadedImageResponse(
                filename=image.filename,
                key=image.key,
                bucket=image.bucket,
                content_type=image.content_type,
                url=image.url,
            )
            for image in uploaded_images
        ],
    )
