from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from models_library.progress_bar import ProgressReport
from pydantic import BaseModel

if TYPE_CHECKING:
    from aiodocker.types import JSONObject

type MountId = str
type FileName = str
type FilesInTransfer = dict[FileName, ProgressReport]


class MountActivity(BaseModel):
    in_transfer: FilesInTransfer
    queued: list[FileName]


class DelegateInterface(ABC):
    @abstractmethod
    async def get_local_vfs_cache_path(self) -> Path:
        """
        Provides the folder to which the vfs-cache volume is mounted locally
        """

    @abstractmethod
    async def get_bind_paths(self, state_path: Path) -> list:
        """
        Provides bind paths for rclone mount given the state path
        returns: a vfs_cache mount and the state_path mount
        """

    @abstractmethod
    async def mount_activity(self, state_path: Path, activity: MountActivity) -> None:
        """
        Callback notifying the caller about the mount activity
        """

    @abstractmethod
    async def request_shutdown(self) -> None:
        """
        If the rclone mount container restarts the fuse mount ids will change,
        which are not propagated to other containers mounting the volume.
        A shutdown is necessary to save current state and ensure data is not lost.
        """

    # basic docker REST interface

    @abstractmethod
    async def create_container(self, config: "JSONObject", name: str) -> None: ...

    @abstractmethod
    async def container_inspect(self, container_name: str) -> dict[str, Any]: ...

    @abstractmethod
    async def remove_container(self, container_name: str) -> None: ...
