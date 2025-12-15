from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final

from common_library.pydantic_validators import validate_numeric_string_as_timedelta
from pydantic import Field, NonNegativeInt

from .base import BaseCustomSettings
from .s3 import S3Settings

DEFAULT_VFS_CACHE_PATH: Final[Path] = Path("/vfs-cache")
DEFAULT_VFS_CACHE_MAX_SIZE: Final[str] = "500G"


class S3Provider(StrEnum):
    AWS = "AWS"
    AWS_MOTO = "AWS_MOTO"
    CEPH = "CEPH"
    MINIO = "MINIO"


class RCloneMountSettings(BaseCustomSettings):
    R_CLONE_MOUNT_TRANSFERS_COMPLETED_TIMEOUT: Annotated[
        timedelta,
        Field(
            description="max amount of time to wait when closing the rclone mount",
        ),
    ] = timedelta(minutes=60)

    _validate_r_clone_mount_transfers_completed_timeout = (
        validate_numeric_string_as_timedelta(
            "R_CLONE_MOUNT_TRANSFERS_COMPLETED_TIMEOUT"
        )
    )

    # CONTAINER

    R_CLONE_VERSION: Annotated[
        str | None,
        Field(
            pattern=r"^\d+\.\d+\.\d+$",
            description="version of rclone for the container image",
        ),
    ] = None

    R_CLONE_CONFIG_FILE_PATH: Annotated[
        Path,
        Field(
            description="path inside the container where the rclone config file is located",
        ),
    ] = Path(
        "/tmp/rclone.conf"  # noqa: S108
    )

    # CLI command `rclone mount`

    R_CLONE_MOUNT_VFS_CACHE_PATH: Annotated[
        Path,
        Field(
            description="`--cache-dir X`: sets the path to use for vfs cache",
        ),
    ] = DEFAULT_VFS_CACHE_PATH

    R_CLONE_MOUNT_VFS_CACHE_MAX_SIZE: Annotated[
        str,
        Field(
            description="`--vfs-cache-max-size X`: sets the maximum size of the vfs cache",
        ),
    ] = DEFAULT_VFS_CACHE_MAX_SIZE

    R_CLONE_MOUNT_VFS_WRITE_BACK: Annotated[
        str,
        Field(
            description="`--vfs-write-back X`: sets the time to wait before writing back data to the remote",
        ),
    ] = "5s"

    R_CLONE_MOUNT_VFS_FAST_FINGERPRINT: Annotated[
        bool,
        Field(
            description="whether to use `--vfs-fast-fingerprint` option",
        ),
    ] = True

    R_CLONE_MOUNT_NO_MODTIME: Annotated[
        bool,
        Field(
            description="whether to use `--no-modtime` option",
        ),
    ] = True


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
