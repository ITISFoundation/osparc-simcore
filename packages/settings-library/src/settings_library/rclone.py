from enum import Enum

from .s3 import S3Settings


class S3BackendType(str, Enum):
    MINIO = "MINIO"
    CEPH = "CEPH"
    S3 = "S3"


class RCloneSettings(S3Settings):
    S3_BACKEND: S3BackendType
