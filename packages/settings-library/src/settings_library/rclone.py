from enum import Enum
from functools import cached_property

from .s3 import S3Settings


class S3Provider(str, Enum):
    AWS = "AWS"
    CEPH = "CEPH"
    MINIO = "MINIO"


class RCloneSettings(S3Settings):
    S3_PROVIDER: S3Provider

    @cached_property
    def endpoint_url(self) -> str:
        if not self.S3_ENDPOINT.startswith("http"):
            scheme = "https" if self.S3_SECURE else "http"
            return f"{scheme}://{self.S3_ENDPOINT}"
        return self.S3_ENDPOINT
