from enum import StrEnum
from typing import Annotated

from pydantic import Field, NonNegativeInt

from .base import BaseCustomSettings
from .s3 import S3Settings


class S3Provider(StrEnum):
    AWS = "AWS"
    CEPH = "CEPH"
    MINIO = "MINIO"


class RCloneSettings(BaseCustomSettings):
    R_CLONE_S3: Annotated[
        S3Settings, Field(json_schema_extra={"auto_default_from_env": True})
    ]
    R_CLONE_PROVIDER: S3Provider

    R_CLONE_OPTION_TRANSFERS: Annotated[
        # SEE https://rclone.org/docs/#transfers-n
        NonNegativeInt,
        Field(description="`--transfers X`: sets the amount of parallel transfers"),
    ] = 5
    R_CLONE_OPTION_RETRIES: Annotated[
        # SEE https://rclone.org/docs/#retries-int
        NonNegativeInt,
        Field(description="`--retries X`: times to retry each individual transfer"),
    ] = 3
    R_CLONE_OPTION_BUFFER_SIZE: Annotated[
        # SEE https://rclone.org/docs/#buffer-size-size
        str,
        Field(
            description="`--buffer-size X`: sets the amount of RAM to use for each individual transfer",
        ),
    ] = "16M"

    R_CLONE_OPTION_CHECKERS: Annotated[
        NonNegativeInt,
        Field(
            description="`--checkers X`: sets the number checkers",
        ),
    ] = 32

    R_CLONE_S3_UPLOAD_CONCURRENCY: Annotated[
        NonNegativeInt,
        Field(
            description="`--s3-upload-concurrency X`: sets the number of concurrent uploads to S3",
        ),
    ] = 8

    R_CLONE_CHUNK_SIZE: Annotated[
        str,
        Field(description="`--s3-chunk-size X`: sets the chunk size for S3"),
    ] = "128M"

    R_CLONE_ORDER_BY: Annotated[
        str,
        Field(
            description="`--order-by X`: sets the order of file upload, e.g., 'size,mixed'",
        ),
    ] = "size,mixed"
