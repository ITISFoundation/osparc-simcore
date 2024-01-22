from pydantic import validator

from .base import BaseCustomSettings


class S3Settings(BaseCustomSettings):
    S3_SECURE: bool = False
    S3_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_ACCESS_TOKEN: str | None = None
    S3_BUCKET_NAME: str
    S3_REGION: str = "us-east-1"

    @validator("S3_ENDPOINT", pre=True)
    @classmethod
    def ensure_scheme(cls, v: str, values) -> str:
        if not v.startswith("http"):
            scheme = "https" if values.get("S3_SECURE") else "http"
            return f"{scheme}://{v}"
        return v
