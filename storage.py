from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import boto3
from botocore.config import Config as BotoConfig
from PIL import Image

try:
    from .config import S3Settings
except ImportError:
    from config import S3Settings


PNG_CONTENT_TYPE = "image/png"


@dataclass(frozen=True)
class UploadedImage:
    filename: str
    key: str
    bucket: str
    content_type: str
    url: str | None


class S3ImageStorage:
    def __init__(self, settings: S3Settings) -> None:
        self.settings = settings
        client_kwargs: dict[str, str] = {}

        if settings.region_name:
            client_kwargs["region_name"] = settings.region_name

        if settings.endpoint_url:
            client_kwargs["endpoint_url"] = settings.endpoint_url

        if settings.access_key_id and settings.secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.access_key_id
            client_kwargs["aws_secret_access_key"] = settings.secret_access_key

        if settings.session_token:
            client_kwargs["aws_session_token"] = settings.session_token

        if settings.use_path_style:
            client_kwargs["config"] = BotoConfig(s3={"addressing_style": "path"})

        self.client = boto3.client("s3", **client_kwargs)

    def upload_images(self, story_id: str, images: list[tuple[str, Image.Image]]) -> list[UploadedImage]:
        return [self.upload_image(story_id, filename, image) for filename, image in images]

    def upload_image(self, story_id: str, filename: str, image: Image.Image) -> UploadedImage:
        key = self.object_key(story_id, filename)
        body = image_to_png_bytes(image)
        put_kwargs: dict[str, str | bytes] = {
            "Bucket": self.settings.bucket,
            "Key": key,
            "Body": body,
            "ContentType": PNG_CONTENT_TYPE,
        }

        if self.settings.acl:
            put_kwargs["ACL"] = self.settings.acl

        self.client.put_object(**put_kwargs)

        return UploadedImage(
            filename=filename,
            key=key,
            bucket=self.settings.bucket,
            content_type=PNG_CONTENT_TYPE,
            url=self.object_url(key),
        )

    def object_key(self, story_id: str, filename: str) -> str:
        prefix = self.settings.prefix.strip("/")

        if prefix:
            return f"{prefix}/{story_id}/{filename}"

        return f"{story_id}/{filename}"

    def object_url(self, key: str) -> str | None:
        if self.settings.public_base_url:
            return f"{self.settings.public_base_url.rstrip('/')}/{key}"

        if not self.settings.return_presigned_urls:
            return None

        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.settings.bucket, "Key": key},
            ExpiresIn=self.settings.presigned_expiration_seconds,
        )


def image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)

    return buffer.getvalue()
