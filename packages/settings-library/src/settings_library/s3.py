from typing import Optional

from .base import BaseCustomSettings
from functools import cached_property


class S3Settings(BaseCustomSettings):
    S3_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_ACCESS_TOKEN: Optional[str] = None
    S3_BUCKET_NAME: str
    S3_SECURE: bool = False

    @cached_property
    def endpoint(self) -> str:
        if not self.S3_ENDPOINT.startswith("http"):
            scheme = "https" if self.S3_SECURE else "http"
            return f"{scheme}://{self.S3_ENDPOINT}"
        return self.S3_ENDPOINT
