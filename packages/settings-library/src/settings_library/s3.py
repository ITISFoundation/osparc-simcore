from typing import Optional

from .base import BaseCustomSettings
from pydantic import validator


class S3Settings(BaseCustomSettings):
    S3_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_ACCESS_TOKEN: Optional[str] = None
    S3_BUCKET_NAME: str
    S3_SECURE: bool = False

    @validator("S3_ENDPOINT", pre=True)
    @classmethod
    def ensure_scheme(cls, v: str, values) -> str:
        if not v.startswith("http"):
            scheme = "https" if values.get("S3_SECURE") else "http"
            return f"{scheme}://{v}"
        return v
