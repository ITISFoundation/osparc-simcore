from datetime import timedelta
from enum import StrEnum
from typing import Annotated

from common_library.pydantic_validators import validate_numeric_string_as_timedelta
from pydantic import Field, NonNegativeInt

from .base import BaseCustomSettings
from .s3 import S3Settings


class S3Provider(StrEnum):
    AWS = "AWS"
    AWS_MOTO = "AWS_MOTO"
    CEPH = "CEPH"
    MINIO = "MINIO"


class RCloneMountSettings(BaseCustomSettings):
    """all settings related to mounting go here"""

    R_CLONE_MOUNT_TRANSFERS_COMPLETED_TIMEOUT: timedelta = Field(
        default=timedelta(minutes=60),
        description="max amount of time to wait when closing the rclone mount",
    )

    _validate_r_clone_mount_transfers_completed_timeout = (
        validate_numeric_string_as_timedelta(
            "R_CLONE_MOUNT_TRANSFERS_COMPLETED_TIMEOUT"
        )
    )


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

    R_CLONE_MOUNT_SETTINGS: RCloneMountSettings = Field(
        json_schema_extra={"auto_default_from_env": True}
    )
