from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final

from common_library.pydantic_validators import validate_numeric_string_as_timedelta
from pydantic import ByteSize, Field, NonNegativeInt, TypeAdapter

from .base import BaseCustomSettings
from .s3 import S3Settings

DEFAULT_VFS_CACHE_PATH: Final[Path] = Path("/vfs-cache")
DEFAULT_VFS_CACHE_MAX_SIZE: Final[str] = "10G"


_TRANSFER_COUNT: Final[NonNegativeInt] = 30
_TPS_PER_TRANSFER: Final[NonNegativeInt] = 7

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

    R_CLONE_MOUNT_SHOW_DEBUG_LOGS: Annotated[
        bool,
        Field(
            description="whether to enable debug logs for the rclone mount command",
        ),
    ] = False

    R_CLONE_MEMORY_LIMIT: Annotated[
        ByteSize, Field(description="memory limit for the rclone mount container")
    ] = TypeAdapter(ByteSize).validate_python("1GiB")

    R_CLONE_NANO_CPUS: Annotated[
        NonNegativeInt, Field(description="CPU limit for the rclone mount container")
    ] = (1 * _ONE_NANO_CPU)

    # CLI command `rclone mount`

    R_CLONE_MOUNT_VFS_CACHE_PATH: Annotated[
        Path,
        Field(
            description="`--cache-dir X`: sets the path to use for vfs cache",
        ),
    ] = DEFAULT_VFS_CACHE_PATH

    R_CLONE_VFS_READ_AHEAD: Annotated[
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

    R_CLONE_CACHE_POLL_INTERVAL: Annotated[
        str,
        Field(
            description="`--vfs-cache-poll-interval X`: sets the interval to poll the vfs cache",
        ),
    ] = "5m"

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

    R_CLONE_DIR_CACHE_TIME: Annotated[
        str,
        Field(
            description="`--dir-cache-time X`: sets the time to cache directory and file information",
        ),
    ] = "10m"

    R_CLONE_ATTR_TIMEOUT: Annotated[
        str,
        Field(
            description="`--attr-timeout X`: sets the time to cache file attributes",
        ),
    ] = "1m"

    R_CLONE_TPSLIMIT: Annotated[
        NonNegativeInt,
        Field(
            description="`--tpslimit X`: sets the transactions per second limit",
        ),
    ] = (
        _TRANSFER_COUNT * _TPS_PER_TRANSFER
    )
    R_CLONE_TPSLIMIT_BURST: Annotated[
        NonNegativeInt,
        Field(
            description="`--tpslimit-burst X`: sets the burst limit for transactions per second",
        ),
    ] = (
        _TRANSFER_COUNT * _TPS_PER_TRANSFER * 2
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
    ] = _TRANSFER_COUNT

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
    ] = 8

    R_CLONE_S3_UPLOAD_CONCURRENCY: Annotated[
        NonNegativeInt,
        Field(
            description="`--s3-upload-concurrency X`: sets the number of concurrent uploads to S3",
        ),
    ] = _TRANSFER_COUNT

    R_CLONE_CHUNK_SIZE: Annotated[
        str,
        Field(description="`--s3-chunk-size X`: sets the chunk size for S3"),
    ] = "64M"

    R_CLONE_ORDER_BY: Annotated[
        str,
        Field(
            description="`--order-by X`: sets the order of file upload, e.g., 'size,mixed'",
        ),
    ] = "size,mixed"

    R_CLONE_MOUNT_SETTINGS: RCloneMountSettings = Field(
        json_schema_extra={"auto_default_from_env": True}
    )


def get_rclone_common_optimizations(r_clone_settings: RCloneSettings) -> list[str]:
    # TODO: move to settings is better
    return [
        "--retries",
        f"{r_clone_settings.R_CLONE_OPTION_RETRIES}",
        "--transfers",
        f"{r_clone_settings.R_CLONE_OPTION_TRANSFERS}",
        # below two options reduce to a minimum the memory footprint
        # https://forum.rclone.org/t/how-to-set-a-memory-limit/10230/4
        "--buffer-size",  # docs https://rclone.org/docs/#buffer-size-size
        r_clone_settings.R_CLONE_OPTION_BUFFER_SIZE,
        "--checkers",
        f"{r_clone_settings.R_CLONE_OPTION_CHECKERS}",
        "--s3-upload-concurrency",
        f"{r_clone_settings.R_CLONE_S3_UPLOAD_CONCURRENCY}",
        "--s3-chunk-size",
        r_clone_settings.R_CLONE_CHUNK_SIZE,
        # handles the order of file upload
        "--order-by",
        r_clone_settings.R_CLONE_ORDER_BY,
        "--fast-list",
    ]
