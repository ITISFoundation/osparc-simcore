from enum import Enum

from .s3 import S3Settings


class S3BackendType(str, Enum):
    AWS = "AWS"
    CEPH = "CEPH"
    MINIO = "MINIO"


class RCloneSettings(S3Settings):
    S3_BACKEND: S3BackendType
