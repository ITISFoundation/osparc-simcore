from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final

from common_library.pydantic_validators import validate_numeric_string_as_timedelta
from pydantic import ByteSize, Field, NonNegativeInt, TypeAdapter

from .base import BaseCustomSettings
from .s3 import S3Settings

DEFAULT_VFS_CACHE_PATH: Final[Path] = Path("/vfs-cache")
DEFAULT_VFS_CACHE_MAX_SIZE: Final[str] = "500G"


_TRANSFER_COUNT: Final[NonNegativeInt] = 15
_TPSLIMIT: Final[NonNegativeInt] = 2000

_ONE_NANO_CPU: Final[NonNegativeInt] = int(1e9)


class S3Provider(StrEnum):
    AWS = "AWS"
    AWS_MOTO = "AWS_MOTO"
    CEPH = "CEPH"
    MINIO = "MINIO"


class RCloneMountSettings(BaseCustomSettings):
    R_CLONE_MOUNT_TRANSFERS_COMPLETED_TIMEOUT: Annotated[
        timedelta,
        Field(
            description="max amount of time to wait for rclone mount command to finish",
        ),
    ] = timedelta(minutes=60)

    _validate_r_clone_mount_transfers_completed_timeout = (
        validate_numeric_string_as_timedelta(
            "R_CLONE_MOUNT_TRANSFERS_COMPLETED_TIMEOUT"
        )
    )

    # CONTAINER
    R_CLONE_MOUNT_CONTAINER_CONFIG_FILE_PATH: Annotated[
        Path,
        Field(
            description="path inside the container where the rclone config file is located",
        ),
    ] = Path(
        "/tmp/rclone.conf"  # noqa: S108
    )

    R_CLONE_MOUNT_CONTAINER_SHOW_DEBUG_LOGS: Annotated[
        bool,
        Field(
            description="whether to enable debug logs for the rclone mount command",
        ),
    ] = False

    R_CLONE_MOUNT_CONTAINER_MEMORY_LIMIT: Annotated[
        ByteSize, Field(description="memory limit for the rclone mount container")
    ] = TypeAdapter(ByteSize).validate_python("2GiB")

    R_CLONE_MOUNT_CONTAINER_NANO_CPUS: Annotated[
        NonNegativeInt, Field(description="CPU limit for the rclone mount container")
    ] = (1 * _ONE_NANO_CPU)

    # CLI command `rclone mount`

    R_CLONE_MOUNT_VFS_CACHE_PATH: Annotated[
        Path,
        Field(
            description="`--cache-dir X`: sets the path to use for vfs cache",
        ),
    ] = DEFAULT_VFS_CACHE_PATH

    R_CLONE_MOUNT_VFS_READ_AHEAD: Annotated[
        str,
        Field(
            description="`--vfs-read-ahead X`: sets the read ahead buffer size",
        ),
    ] = "16M"

    R_CLONE_MOUNT_VFS_CACHE_MAX_SIZE: Annotated[
        str,
        Field(
            description="`--vfs-cache-max-size X`: sets the maximum size of the vfs cache",
        ),
    ] = DEFAULT_VFS_CACHE_MAX_SIZE

    R_CLONE_MOUNT_VFS_CACHE_MIN_FREE_SPACE: Annotated[
        str,
        Field(
            description="`--vfs-cache-min-free-space X`: sets the minimum free space to keep on disk",
        ),
    ] = "5G"

    R_CLONE_MOUNT_CACHE_POLL_INTERVAL: Annotated[
        str,
        Field(
            description="`--vfs-cache-poll-interval X`: sets the interval to poll the vfs cache",
        ),
    ] = "1m"

    R_CLONE_MOUNT_VFS_WRITE_BACK: Annotated[
        str,
        Field(
            description="`--vfs-write-back X`: sets the time to wait before writing back data to the remote",
        ),
    ] = "10s"

    R_CLONE_MOUNT_DIR_CACHE_TIME: Annotated[
        str,
        Field(
            description="`--dir-cache-time X`: time before directory is uploaded from remote if changed",
        ),
    ] = "10m"

    R_CLONE_MOUNT_ATTR_TIMEOUT: Annotated[
        str,
        Field(
            description="`--attr-timeout X`: sets the time to cache file attributes",
        ),
    ] = "1m"

    R_CLONE_MOUNT_TPSLIMIT: Annotated[
        NonNegativeInt,
        Field(
            description="`--tpslimit X`: sets the transactions per second limit",
        ),
    ] = _TPSLIMIT
    R_CLONE_MOUNT_TPSLIMIT_BURST: Annotated[
        NonNegativeInt,
        Field(
            description="`--tpslimit-burst X`: sets the burst limit for transactions per second",
        ),
    ] = (
        _TPSLIMIT * 2
    )

    R_CLONE_MOUNT_MAX_BUFFER_MEMORY: Annotated[
        str,
        Field(
            description="`--max-buffer-memory X`: sets the maximum buffer memory for rclone",
        ),
    ] = "16M"

    R_CLONE_MOUNT_RETRIES: Annotated[
        NonNegativeInt,
        Field(
            description="`--retries X`: sets the number of retries for rclone mount command",
        ),
    ] = 3

    R_CLONE_MOUNT_RETRIES_SLEEP: Annotated[
        str,
        Field(
            description="`--retries-sleep X`: sets the maximum sleep time between retries",
        ),
    ] = "30s"
    R_CLONE_MOUNT_TRANSFERS: Annotated[
        NonNegativeInt,
        Field(
            description="`--transfers X`: sets the number of parallel transfers for rclone mount command",
        ),
    ] = 15
    R_CLONE_MOUNT_BUFFER_SIZE: Annotated[
        str,
        Field(
            description="`--buffer-size X`: sets the buffer size for rclone mount command",
        ),
    ] = "16M"
    R_CLONE_MOUNT_CHECKERS: Annotated[
        NonNegativeInt,
        Field(
            description="`--checkers X`: sets the number of checkers for rclone mount command",
        ),
    ] = 8
    R_CLONE_MOUNT_S3_UPLOAD_CONCURRENCY: Annotated[
        NonNegativeInt,
        Field(
            description="`--s3-upload-concurrency X`: sets the number of concurrent uploads to S3",
        ),
    ] = 5
    R_CLONE_MOUNT_S3_CHUNK_SIZE: Annotated[
        str,
        Field(
            description="`--s3-chunk-size X`: sets the chunk size for S3",
        ),
    ] = "16M"
    R_CLONE_MOUNT_ORDER_BY: Annotated[
        str,
        Field(
            description="`--order-by X`: sets the order of file upload, e.g., 'size,mixed'",
        ),
    ] = "size,mixed"


class RCloneSettings(BaseCustomSettings):
    R_CLONE_S3: Annotated[
        S3Settings, Field(json_schema_extra={"auto_default_from_env": True})
    ]
    R_CLONE_PROVIDER: S3Provider

    R_CLONE_VERSION: Annotated[
        str | None,
        Field(
            pattern=r"^\d+\.\d+\.\d+$",
            description="version of rclone for the container image",
        ),
    ] = None

    R_CLONE_MOUNT_SETTINGS: RCloneMountSettings = Field(
        json_schema_extra={"auto_default_from_env": True}
    )

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

    R_CLONE_RETRIES_SLEEP: Annotated[
        str,
        Field(
            description="`--retries-sleep X`: max time to sleep between retries (caps exponential backoff)"
        ),
    ] = "30s"

    R_CLONE_OPTION_BUFFER_SIZE: Annotated[
        # SEE https://rclone.org/docs/#buffer-size-size
        str,
        Field(
            description="`--buffer-size X`: sets the amount of RAM to use for each individual transfer",
        ),
    ] = "16M"

    R_CLONE_CHECKERS: Annotated[
        NonNegativeInt,
        Field(
            description="`--checkers X`: sets the number checkers",
        ),
    ] = 8

    R_CLONE_S3_UPLOAD_CONCURRENCY: Annotated[
        NonNegativeInt,
        Field(
            description="`--s3-upload-concurrency X`: sets the number of concurrent uploads to S3",
        ),
    ] = 5

    R_CLONE_CHUNK_SIZE: Annotated[
        str,
        Field(description="`--s3-chunk-size X`: sets the chunk size for S3"),
    ] = "16M"

    R_CLONE_ORDER_BY: Annotated[
        str,
        Field(
            description="`--order-by X`: sets the order of file upload, e.g., 'size,mixed'",
        ),
    ] = "size,mixed"
