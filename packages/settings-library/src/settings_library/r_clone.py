from enum import Enum

from pydantic import Field
from .base import BaseCustomSettings
from .s3 import S3Settings


class S3Provider(str, Enum):
    AWS = "AWS"
    CEPH = "CEPH"
    MINIO = "MINIO"


class _RequiredS3Settings(S3Settings):
    S3_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET_NAME: str
    S3_SECURE: bool


class RCloneSettings(BaseCustomSettings):
    R_CLONE_S3: _RequiredS3Settings = Field(auto_default_from_env=True)
    R_CLONE_PROVIDER: S3Provider
    R_CLONE_STORAGE_ENDPOINT: str = Field(
        ..., description="endpoint where storage is present"
    )

    R_CLONE_AIOHTTP_CLIENT_TIMEOUT_TOTAL: float = 20
    R_CLONE_AIOHTTP_CLIENT_TIMEOUT_SOCK_CONNECT: float = 5

    @property
    def storage_endpoint(self) -> str:
        if not self.R_CLONE_STORAGE_ENDPOINT.startswith("http"):
            return f"http://{self.R_CLONE_STORAGE_ENDPOINT}"
        return self.R_CLONE_STORAGE_ENDPOINT
