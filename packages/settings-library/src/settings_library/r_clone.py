from enum import Enum

from pydantic import Field, constr, ByteSize

from .base import BaseCustomSettings
from .s3 import S3Settings

MemoryStr = constr(regex=r"^[1-9][0-9]*[bkmg]")


class S3Provider(str, Enum):
    AWS = "AWS"
    CEPH = "CEPH"
    MINIO = "MINIO"


class RCloneSettings(BaseCustomSettings):
    R_CLONE_S3: S3Settings = Field(auto_default_from_env=True)
    R_CLONE_PROVIDER: S3Provider
    R_CLONE_VERSION: str = "1.58.1"
    R_CLONE_MEMORY_RESERVATION: MemoryStr = "100m"
    R_CLONE_MEMORY_LIMIT: MemoryStr = "1g"
    R_CLONE_MAX_CPU_USAGE: float = 0.5
    R_CLONE_UPLOAD_TIMEOUT_S: int = 3600


def docker_size_as_bytes(docker_memory_string: MemoryStr) -> ByteSize:
    unit = docker_memory_string[-1]
    if unit in {"k", "m", "g"}:
        unit = f"{unit}b"

    number = docker_memory_string[:-1]
    return ByteSize.validate(f"{number}{unit}")
