from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final, Literal

from common_library.basic_types import DEFAULT_FACTORY
from common_library.pydantic_validators import validate_numeric_string_as_timedelta
from pydantic import ByteSize, Field, NonNegativeFloat, NonNegativeInt, TypeAdapter

from .base import BaseCustomSettings
from .s3 import S3Settings

DEFAULT_VFS_CACHE_PATH: Final[Path] = Path("/vfs-cache")


_ONE_CPU: Final[NonNegativeInt] = int(1e9)


class S3Provider(StrEnum):
    AWS = "AWS"
    AWS_MOTO = "AWS_MOTO"
    CEPH = "CEPH"
    MINIO = "MINIO"
    RUSTFS = "RUSTFS"


type SearchArgument = str
type EditArgument = str
type ArgumentValue = str
type ReplaceArgument = EditArgument | tuple[EditArgument, ArgumentValue]
type ElementsToRemove = Annotated[Literal[1, 2], int]
type EditArguments = dict[SearchArgument, ReplaceArgument]
type RemoveArguments = list[tuple[SearchArgument, ElementsToRemove]]


class SimcoreSDKMountSettings(BaseCustomSettings):
    R_CLONE_SIMCORE_SDK_MOUNT_TRANSFERS_COMPLETED_TIMEOUT: Annotated[
        timedelta,
        Field(
            description=(
                "max amount of time to wait for rclone mount command to finish it's transfer queue "
                "before shutting down the mount"
            ),
        ),
    ] = timedelta(minutes=60)

    _validate_r_clone_mount_transfers_completed_timeout = validate_numeric_string_as_timedelta(
        "R_CLONE_SIMCORE_SDK_MOUNT_TRANSFERS_COMPLETED_TIMEOUT"
    )

    R_CLONE_SIMCORE_SDK_MOUNT_VFS_CACHE_PERCENT_DISK_SPACE: Annotated[
        NonNegativeFloat,
        Field(
            gt=0.0,
            le=1.0,
            description="allows to selec how much of the disk where docker is running is dedicated to vfs cache",
        ),
    ] = 0.9

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
    ] = TypeAdapter(ByteSize).validate_python("3GiB")

    R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_NANO_CPUS: Annotated[
        NonNegativeInt, Field(description="CPU limit for the rclone mount container")
    ] = 1 * _ONE_CPU

    R_CLONE_SIMCORE_SDK_MOUNT_COMMAND_EDIT_ARGUMENTS: Annotated[
        EditArguments,
        Field(default_factory=dict, description="arguments to be changed or added to the rclone mount command"),
    ] = DEFAULT_FACTORY

    R_CLONE_SIMCORE_SDK_MOUNT_COMMAND_REMOVE_ARGUMENTS: Annotated[
        RemoveArguments,
        Field(default_factory=list, description="arguments to be removed from the rclone mount command"),
    ] = DEFAULT_FACTORY


class SimcoreSDKSyncSettings(BaseCustomSettings):
    R_CLONE_SIMCORE_SDK_SYNC_COMMAND_EDIT_ARGUMENTS: Annotated[
        EditArguments,
        Field(default_factory=dict, description="arguments to be changed or added to the rclone sync command"),
    ] = DEFAULT_FACTORY

    R_CLONE_SIMCORE_SDK_SYNC_COMMAND_REMOVE_ARGUMENTS: Annotated[
        RemoveArguments,
        Field(default_factory=list, description="arguments to be removed from the rclone sync command"),
    ] = DEFAULT_FACTORY


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
