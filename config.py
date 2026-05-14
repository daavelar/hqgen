from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class S3Settings:
    bucket: str
    region_name: str | None = None
    prefix: str = "generated-stories"
    endpoint_url: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None
    session_token: str | None = None
    public_base_url: str | None = None
    return_presigned_urls: bool = False
    presigned_expiration_seconds: int = 3600
    acl: str | None = None
    use_path_style: bool = False


def get_s3_settings() -> S3Settings:
    bucket = env_value("AWS_BUCKET", "AWS_BUCKET_NAME", "AWS_S3_BUCKET", "S3_BUCKET", "S3_BUCKET_NAME")

    if not bucket:
        raise RuntimeError(
            "Missing S3 bucket. Set AWS_BUCKET, AWS_BUCKET_NAME, AWS_S3_BUCKET, S3_BUCKET, or S3_BUCKET_NAME."
        )

    return S3Settings(
        bucket=bucket,
        region_name=env_value("AWS_DEFAULT_REGION", "AWS_REGION", "S3_REGION"),
        prefix=env_value("S3_PREFIX", "AWS_S3_PREFIX") or "generated-stories",
        endpoint_url=env_value(
            "AWS_ENDPOINT_URL",
            "AWS_S3_ENDPOINT_URL",
            "S3_ENDPOINT_URL",
            "AWS_ENDPOINT",
            "S3_ENDPOINT",
        ),
        access_key_id=env_value("AWS_ACCESS_KEY_ID", "AWS_KEY", "S3_ACCESS_KEY_ID"),
        secret_access_key=env_value("AWS_SECRET_ACCESS_KEY", "AWS_SECRET", "S3_SECRET_ACCESS_KEY"),
        session_token=env_value("AWS_SESSION_TOKEN", "S3_SESSION_TOKEN"),
        public_base_url=env_value(
            "S3_PUBLIC_BASE_URL",
            "AWS_S3_PUBLIC_URL",
            "CLOUDFRONT_URL",
            "AWS_URL",
        ),
        return_presigned_urls=env_bool("S3_RETURN_PRESIGNED_URLS", default=False),
        presigned_expiration_seconds=env_int("S3_PRESIGNED_EXPIRATION_SECONDS", default=3600),
        acl=env_value("S3_ACL", "AWS_S3_ACL"),
        use_path_style=env_bool("AWS_USE_PATH_STYLE_ENDPOINT", default=False),
    )


def env_value(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)

        if value is not None and value.strip() != "":
            return value.strip()

    return None


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default
