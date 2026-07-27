import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final
from uuid import uuid4

from common_library.async_tools import cancel_wait_task
from httpx import HTTPError
from models_library.projects_nodes_io import NodeID, StorageFileID
from pydantic import AnyUrl, NonNegativeInt
from servicelib.background_task import create_periodic_task
from servicelib.logging_utils import log_catch, log_context
from settings_library.r_clone import RCloneSettings

from ._config_provider import MountRemoteType, get_config_content
from ._container import ContainerManager, RemoteControlHttpClient
from ._errors import (
    InvalidRemotePathError,
    MountPathConflictError,
    NoMountFoundForRemotePathError,
)
from ._models import DelegateInterface, MountActivity, MountId
from ._utils import get_mount_id

_logger = logging.getLogger(__name__)

_MIN_PATH_PARTS: Final[NonNegativeInt] = 3

_DEFAULT_MOUNT_ACTIVITY_UPDATE_INTERVAL: Final[timedelta] = timedelta(seconds=5)
_MOUNT_RESPONSIVE_CHECK_INTERVAL: Final[timedelta] = timedelta(seconds=6)
_CONSECUTIVE_UNRESPONSIVE_THRESHOLD: Final[NonNegativeInt] = 3
_S3_SCHEME_PREFIX: Final[str] = "s3://"


class _TrackedMount:  # pylint:disable=too-many-instance-attributes
    def __init__(  # pylint:disable=too-many-arguments
        self,
        node_id: NodeID,
        r_clone_settings: RCloneSettings,
        mount_remote_type: MountRemoteType,
        *,
        remote_path: StorageFileID,
        mount_s3_path: str,
        local_mount_path: Path,
        index: NonNegativeInt,
        delegate: DelegateInterface,
        mount_activity_update_interval: timedelta = _DEFAULT_MOUNT_ACTIVITY_UPDATE_INTERVAL,
    ) -> None:
        self.remote_path = remote_path
        self.local_mount_path = local_mount_path
        self.index = index

        self.delegate = delegate

        self._mount_activity_update_interval = mount_activity_update_interval

        self._last_mount_activity: MountActivity | None = None
        self._last_mount_activity_update: datetime = datetime.fromtimestamp(0, UTC)
        self._task_mount_activity: asyncio.Task[None] | None = None
        self._consecutive_unresponsive_count: int = 0
        self._vfs_write_back_s: NonNegativeInt = 0

        self._rc_user = f"{uuid4()}"
        self._rc_password = f"{uuid4()}"
        self._transfers_completed_timeout = (
            r_clone_settings.R_CLONE_SIMCORE_SDK_MOUNT_SETTINGS.R_CLONE_SIMCORE_SDK_MOUNT_TRANSFERS_COMPLETED_TIMEOUT
        )

        # used internally to handle the mount command
        self._container_manager = ContainerManager(
            r_clone_settings=r_clone_settings,
            node_id=node_id,
            local_mount_path=self.local_mount_path,
            index=self.index,
            r_clone_config_content=get_config_content(r_clone_settings, mount_remote_type),
            remote_path=mount_s3_path,
            rc_user=self._rc_user,
            rc_password=self._rc_password,
            delegate=self.delegate,
        )

        self._rc_http_client: RemoteControlHttpClient | None = None

    @property
    def _rc_client(self) -> RemoteControlHttpClient:
        assert self._rc_http_client is not None, "start_mount() must be called before accessing the RC client"  # nosec
        return self._rc_http_client

    async def _update_and_notify_mount_activity(self, mount_activity: MountActivity) -> None:
        now = datetime.now(UTC)

        enough_time_passed = now - self._last_mount_activity_update > self._mount_activity_update_interval

        if enough_time_passed and self._last_mount_activity != mount_activity:
            self._last_mount_activity = mount_activity
            self._last_mount_activity_update = now

            await self.delegate.mount_activity(self.local_mount_path, mount_activity)

    async def _worker_mount_activity(self) -> None:
        with log_catch(logger=_logger, reraise=False):
            mount_activity = await self._rc_client.get_mount_activity()
            mount_activity.vfs_write_back_s = self._vfs_write_back_s  # required by frontend
            await self._update_and_notify_mount_activity(mount_activity)

    async def _create_or_reconnect_container(self) -> bool:
        create_result = await self._container_manager.create()
        # always set since it's required for frontend
        self._vfs_write_back_s = create_result.vfs_write_back_s

        if create_result.reconnected:
            # recover old values
            self._rc_user = create_result.rc_user
            self._rc_password = create_result.rc_password

            _logger.info(
                "Reconnected to existing container '%s' on port='%s'",
                self._container_manager.r_clone_container_name,
                create_result.assigned_port,
            )

        node_address = await self.delegate.get_node_address()

        self._rc_http_client = RemoteControlHttpClient(
            rc_host=node_address,
            rc_port=create_result.assigned_port,
            rc_user=self._rc_user,
            rc_password=self._rc_password,
            transfers_completed_timeout=self._transfers_completed_timeout,
        )
        return create_result.reconnected

    async def start_mount(self) -> None:
        reconnected = await self._create_or_reconnect_container()
        try:
            await self._rc_client.wait_for_interface_to_be_ready()
        except HTTPError:
            if reconnected:
                # NOTE: in case of a reconnection it is possible that the container's
                # HTTP interface is not available (e.g. container was stopped).
                # Attempt removal and recreation of the container before giving up.
                await self.delegate.remove_container(self._container_manager.r_clone_container_name)

                await self._create_or_reconnect_container()
                await self._rc_client.wait_for_interface_to_be_ready()
            else:
                raise

        self._task_mount_activity = create_periodic_task(
            self._worker_mount_activity,
            interval=self._mount_activity_update_interval,
            task_name=f"rclone-mount-activity-{get_mount_id(self.local_mount_path, self.index)}",
        )

    async def stop_mount(self, *, skip_transfer_wait: bool = False) -> None:
        if not skip_transfer_wait:
            await self._rc_client.wait_for_all_transfers_to_complete()

        await self._container_manager.remove()
        if self._task_mount_activity is not None:
            await cancel_wait_task(self._task_mount_activity)

    async def wait_for_all_transfers_to_complete(self) -> None:
        await self._rc_client.wait_for_all_transfers_to_complete()

    async def is_healthy(self) -> bool:
        if await self._rc_client.is_responsive():
            self._consecutive_unresponsive_count = 0
            return True

        self._consecutive_unresponsive_count += 1
        _logger.warning(
            "Mount '%s' unresponsive %d/%d consecutive times",
            self.local_mount_path,
            self._consecutive_unresponsive_count,
            _CONSECUTIVE_UNRESPONSIVE_THRESHOLD,
        )
        return self._consecutive_unresponsive_count < _CONSECUTIVE_UNRESPONSIVE_THRESHOLD

    async def refresh_path(self, *, dir_to_refresh: str, recursive: bool) -> None:
        if dir_to_refresh:
            # Ensure VFS cache is aware of new directories created
            # externally (e.g. uploaded directly to S3) by refreshing
            # each parent segment top-down (non-recursive, cheap).
            for parent in reversed(Path(dir_to_refresh).parents):
                parent_str = "" if parent == Path() else f"{parent}"
                await self._rc_client.post_vfs_refresh(parent_str, recursive=False)
        await self._rc_client.post_vfs_refresh(dir_to_refresh, recursive=recursive)


class RCloneMountManager:
    def __init__(
        self,
        r_clone_settings: RCloneSettings,
        *,
        requires_data_mounting: bool,
        delegate: DelegateInterface,
    ) -> None:
        self.r_clone_settings = r_clone_settings
        self.requires_data_mounting = requires_data_mounting
        self.delegate = delegate

        self._tracked_mounts: dict[MountId, _TrackedMount] = {}
        self._reverse_path_search: dict[MountId, StorageFileID] = {}
        self._task_ensure_mounts_working: asyncio.Task[None] | None = None

    async def ensure_mounted(
        self,
        local_mount_path: Path,
        index: NonNegativeInt,
        *,
        node_id: NodeID,
        remote_type: MountRemoteType,
        remote_path: StorageFileID,
        mount_s3_link: AnyUrl,
    ) -> None:
        with log_context(
            _logger,
            logging.INFO,
            f"mounting {local_mount_path=} from {remote_path=}",
        ):
            mount_id = get_mount_id(local_mount_path, index)
            if mount_id in self._tracked_mounts:
                _logger.debug("Mount for '%s' at index '%s' is already started", local_mount_path, index)
                existing_remote_path = self._reverse_path_search[mount_id]
                if existing_remote_path != remote_path:
                    raise MountPathConflictError(
                        local_mount_path=local_mount_path,
                        existing_remote_path=existing_remote_path,
                        new_remote_path=remote_path,
                    )
                return

            tracked_mount = _TrackedMount(
                node_id,
                self.r_clone_settings,
                remote_type,
                remote_path=remote_path,
                mount_s3_path=f"{mount_s3_link}".removeprefix(_S3_SCHEME_PREFIX),
                local_mount_path=local_mount_path,
                index=index,
                delegate=self.delegate,
            )

            await tracked_mount.start_mount()

            self._tracked_mounts[mount_id] = tracked_mount
            self._reverse_path_search[mount_id] = remote_path

    def is_mount_tracked(self, local_mount_path: Path, index: NonNegativeInt) -> bool:
        mount_id = get_mount_id(local_mount_path, index)
        return mount_id in self._tracked_mounts

    async def ensure_unmounted(self, local_mount_path: Path, index: NonNegativeInt) -> None:
        with log_context(_logger, logging.INFO, f"unmounting {local_mount_path=}"):
            mount_id = get_mount_id(local_mount_path, index)
            tracked_mount = self._tracked_mounts.pop(mount_id)
            self._reverse_path_search.pop(mount_id)

            await tracked_mount.wait_for_all_transfers_to_complete()

            await tracked_mount.stop_mount()

    async def refresh_path(self, remote_path: StorageFileID, *, recursive: bool = False) -> None:
        # NOTE: always refreshes the containing directory, unless it's the top level directory if
        # len(remote_path_parts) == _MIN_PATH_PARTS when this one is refreshed

        remote_path_parts = remote_path.split("/")
        if len(remote_path_parts) < _MIN_PATH_PARTS or any(not p for p in remote_path_parts[:_MIN_PATH_PARTS]):
            raise InvalidRemotePathError(remote_path=remote_path)

        with log_context(_logger, logging.INFO, f"refreshing mount for {remote_path=}"):
            base_s3_path = "/".join(remote_path_parts[:_MIN_PATH_PARTS])
            tracked_mount: _TrackedMount | None = None

            for mount_id, remote in self._reverse_path_search.items():
                if base_s3_path == remote:
                    tracked_mount = self._tracked_mounts[mount_id]
                    break

            if tracked_mount is None:
                raise NoMountFoundForRemotePathError(remote_path=remote_path)

            # dir_to_refresh is relative to the mounted root.
            # Example 1 (mount root):
            # - remote_path: project-1/node-1/data
            # - dir_to_refresh: ""
            # Example 2 (file in root directory):
            # - remote_path: project-1/node-1/data/file.txt
            # - dir_to_refresh: ""
            # Example 3 (subfolder file):
            # - remote_path: project-1/node-1/data/folder/subfolder/file.txt
            # - dir_to_refresh: "folder/subfolder"
            relative_path_parts = remote_path_parts[_MIN_PATH_PARTS:]
            dir_to_refresh = "/".join(relative_path_parts[:-1]) if relative_path_parts else ""
            await tracked_mount.refresh_path(dir_to_refresh=dir_to_refresh, recursive=recursive)

    async def _worker_ensure_mount_is_responsive(self) -> None:
        mount_restored = False
        with log_context(_logger, logging.DEBUG, "ensuring rclone mount is responsive"):
            for mount in self._tracked_mounts.values():
                if not await mount.is_healthy():
                    with log_context(
                        _logger,
                        logging.WARNING,
                        f"restoring mount for path='{mount.local_mount_path}'",
                    ):
                        await mount.stop_mount(skip_transfer_wait=True)
                        await mount.start_mount()
                        mount_restored = True

            if mount_restored:
                with log_context(
                    _logger,
                    logging.WARNING,
                    "requesting service shutdown due to mount restoration",
                ):
                    # NOTE: since the mount is bind mounted, we ensure that it restarts properly
                    # then we shutdown the service since the user service will have an out of date
                    # FUSE mount.
                    await self.delegate.request_shutdown()

    async def setup(self) -> None:
        self._task_ensure_mounts_working = create_periodic_task(
            self._worker_ensure_mount_is_responsive,
            interval=_MOUNT_RESPONSIVE_CHECK_INTERVAL,
            task_name="rclone-mount-ensure-mount-is-responsive",
        )

    async def teardown(self) -> None:
        if self._task_ensure_mounts_working is not None:
            await cancel_wait_task(self._task_ensure_mounts_working)

        await asyncio.gather(
            *[
                self.ensure_unmounted(local_mount_path=tracked_mount.local_mount_path, index=tracked_mount.index)
                for tracked_mount in self._tracked_mounts.values()
            ]
        )
        self._tracked_mounts.clear()
