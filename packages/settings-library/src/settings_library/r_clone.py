from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final, Literal

from common_library.basic_types import DEFAULT_FACTORY
from common_library.pydantic_validators import validate_numeric_string_as_timedelta
from pydantic import ByteSize, Field, NonNegativeInt, TypeAdapter

from .base import BaseCustomSettings
from .s3 import S3Settings

DEFAULT_VFS_CACHE_PATH: Final[Path] = Path("/vfs-cache")
DEFAULT_VFS_CACHE_MAX_SIZE: Final[str] = "500G"


TPSLIMIT: Final[NonNegativeInt] = 2000

_ONE_CPU: Final[NonNegativeInt] = int(1e9)


class S3Provider(StrEnum):
    AWS = "AWS"
    AWS_MOTO = "AWS_MOTO"
    CEPH = "CEPH"
    MINIO = "MINIO"


type ElemertsToRemove = Annotated[Literal[1, 2], int]
type SearchOption = str
type EditOption = str
type OptionValue = str
type ReplaceOption = EditOption | tuple[EditOption, OptionValue]
type EditEntries = dict[SearchOption, ReplaceOption]
type RemoveEntries = list[tuple[SearchOption, ElemertsToRemove]]


class SimcoreSDKMountSettings(BaseCustomSettings):
    R_CLONE_SIMCORE_SDK_MOUNT_TRANSFERS_COMPLETED_TIMEOUT: Annotated[
        timedelta,
        Field(
            description="max amount of time to wait for rclone mount command to finish",
        ),
    ] = timedelta(minutes=60)

    _validate_r_clone_mount_transfers_completed_timeout = validate_numeric_string_as_timedelta(
        "R_CLONE_SIMCORE_SDK_MOUNT_TRANSFERS_COMPLETED_TIMEOUT"
    )

    # CONTAINER
    R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_CONFIG_FILE_PATH: Annotated[
        Path,
        Field(
            description="path inside the container where the rclone config file is located",
        ),
    ] = Path(
        "/tmp/rclone.conf"  # noqa: S108
    )

    R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_SHOW_DEBUG_LOGS: Annotated[
        bool,
        Field(
            description="whether to enable debug logs for the rclone mount command",
        ),
    ] = False

    R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_MEMORY_LIMIT: Annotated[
        ByteSize, Field(description="memory limit for the rclone mount container")
    ] = TypeAdapter(ByteSize).validate_python("2GiB")

    R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_NANO_CPUS: Annotated[
        NonNegativeInt, Field(description="CPU limit for the rclone mount container")
    ] = 1 * _ONE_CPU

    R_CLONE_SIMCORE_SDK_MOUNT_COMMAND_EDIT_ENTRIES: Annotated[EditEntries, Field(default_factory=dict)] = (
        DEFAULT_FACTORY
    )

    R_CLONE_SIMCORE_SDK_MOUNT_COMMAND_REMOVE_ENTRIES: Annotated[RemoveEntries, Field(default_factory=list)] = (
        DEFAULT_FACTORY
    )


class SimcoreSDKSyncSettings(BaseCustomSettings):
    R_CLONE_SIMCORE_SDK_SYNC_COMMAND_EDIT_ENTRIES: Annotated[EditEntries, Field(default_factory=dict)] = DEFAULT_FACTORY

    R_CLONE_SIMCORE_SDK_SYNC_COMMAND_REMOVE_ENTRIES: Annotated[RemoveEntries, Field(default_factory=list)] = (
        DEFAULT_FACTORY
    )


class RCloneSettings(BaseCustomSettings):
    R_CLONE_S3: Annotated[S3Settings, Field(json_schema_extra={"auto_default_from_env": True})]
    R_CLONE_PROVIDER: S3Provider

    R_CLONE_VERSION: Annotated[
        str | None,
        Field(
            pattern=r"^\d+\.\d+\.\d+$",
            description="version of rclone for the container image",
        ),
    ] = None

    R_CLONE_SIMCORE_SDK_MOUNT_SETTINGS: SimcoreSDKMountSettings = Field(
        json_schema_extra={"auto_default_from_env": True}
    )
    R_CLONE_SIMCORE_SDK_SYNC_SETTINGS: SimcoreSDKSyncSettings = Field(json_schema_extra={"auto_default_from_env": True})
