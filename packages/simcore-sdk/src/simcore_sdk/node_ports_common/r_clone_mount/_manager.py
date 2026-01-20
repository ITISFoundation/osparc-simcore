import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final
from uuid import uuid4

from common_library.async_tools import cancel_wait_task
from models_library.basic_types import PortInt
from models_library.projects_nodes_io import NodeID, StorageFileID
from pydantic import NonNegativeInt
from servicelib.background_task import create_periodic_task
from servicelib.logging_utils import log_catch, log_context
from servicelib.utils import unused_port
from settings_library.r_clone import RCloneSettings

from ._config_provider import MountRemoteType, get_config_content
from ._container import ContainerManager, RemoteControlHttpClient
from ._errors import (
    MountAlreadyStartedError,
)
from ._models import DelegateInterface, MountActivity, MountId
from ._utils import get_mount_id

_logger = logging.getLogger(__name__)


_DEFAULT_MOUNT_ACTIVITY_UPDATE_INTERVAL: Final[timedelta] = timedelta(seconds=5)


class _TrackedMount:  # pylint:disable=too-many-instance-attributes
    def __init__(  # pylint:disable=too-many-arguments
        self,
        node_id: NodeID,
        r_clone_settings: RCloneSettings,
        mount_remote_type: MountRemoteType,
        *,
        rc_port: PortInt,
        remote_path: StorageFileID,
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

        rc_user = f"{uuid4()}"
        rc_password = f"{uuid4()}"

        # used internally to handle the mount command
        self._container_manager = ContainerManager(
            r_clone_settings=r_clone_settings,
            node_id=node_id,
            rc_port=rc_port,
            local_mount_path=self.local_mount_path,
            index=self.index,
            r_clone_config_content=get_config_content(r_clone_settings, mount_remote_type),
            remote_path=f"{r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME}/{self.remote_path}",
            rc_user=rc_user,
            rc_password=rc_password,
            delegate=self.delegate,
        )

        self._rc_http_client = RemoteControlHttpClient(
            rc_port=rc_port,
            rc_user=rc_user,
            rc_password=rc_password,
            transfers_completed_timeout=r_clone_settings.R_CLONE_SIMCORE_SDK_MOUNT_SETTINGS.R_CLONE_SIMCORE_SDK_MOUNT_TRANSFERS_COMPLETED_TIMEOUT,
        )

    async def _update_and_notify_mount_activity(self, mount_activity: MountActivity) -> None:
        now = datetime.now(UTC)

        enough_time_passed = now - self._last_mount_activity_update > self._mount_activity_update_interval

        if enough_time_passed and self._last_mount_activity != mount_activity:
            self._last_mount_activity = mount_activity
            self._last_mount_activity_update = now

            await self.delegate.mount_activity(self.local_mount_path, mount_activity)

    async def _worker_mount_activity(self) -> None:
        with log_catch(logger=_logger, reraise=False):
            mount_activity = await self._rc_http_client.get_mount_activity()
            await self._update_and_notify_mount_activity(mount_activity)

    async def start_mount(self) -> None:
        await self._container_manager.create()

        await self._rc_http_client.wait_for_interface_to_be_ready()

        self._task_mount_activity = create_periodic_task(
            self._worker_mount_activity,
            interval=self._mount_activity_update_interval,
            task_name=f"rclone-mount-activity-{get_mount_id(self.local_mount_path, self.index)}",
        )

    async def stop_mount(self, *, skip_transfer_wait: bool = False) -> None:
        if not skip_transfer_wait:
            await self._rc_http_client.wait_for_all_transfers_to_complete()

        await self._container_manager.remove()
        if self._task_mount_activity is not None:
            await cancel_wait_task(self._task_mount_activity)

    async def wait_for_all_transfers_to_complete(self) -> None:
        await self._rc_http_client.wait_for_all_transfers_to_complete()

    async def is_responsive(self) -> bool:
        return await self._rc_http_client.is_responsive()


class RCloneMountManager:
    def __init__(
        self,
        r_clone_settings: RCloneSettings,
        *,
        delegate: DelegateInterface,
    ) -> None:
        self.r_clone_settings = r_clone_settings
        self.delegate = delegate
        if r_clone_settings.R_CLONE_VERSION is None:
            msg = "R_CLONE_VERSION setting is not set"
            raise RuntimeError(msg)

        self._tracked_mounts: dict[MountId, _TrackedMount] = {}
        self._task_ensure_mounts_working: asyncio.Task[None] | None = None

    async def ensure_mounted(
        self,
        local_mount_path: Path,
        index: NonNegativeInt,
        *,
        node_id: NodeID,
        remote_type: MountRemoteType,
        remote_path: StorageFileID,
    ) -> None:
        with log_context(
            _logger,
            logging.INFO,
            f"mounting {local_mount_path=} from {remote_path=}",
            log_duration=True,
        ):
            mount_id = get_mount_id(local_mount_path, index)
            if mount_id in self._tracked_mounts:
                tracked_mount = self._tracked_mounts[mount_id]
                raise MountAlreadyStartedError(local_mount_path=local_mount_path)

            free_port = await asyncio.get_running_loop().run_in_executor(None, unused_port)

            tracked_mount = _TrackedMount(
                node_id,
                self.r_clone_settings,
                remote_type,
                rc_port=free_port,
                remote_path=remote_path,
                local_mount_path=local_mount_path,
                index=index,
                delegate=self.delegate,
            )
            self._tracked_mounts[mount_id] = tracked_mount
            await tracked_mount.start_mount()

    def is_mount_tracked(self, local_mount_path: Path, index: NonNegativeInt) -> bool:
        mount_id = get_mount_id(local_mount_path, index)
        return mount_id in self._tracked_mounts

    async def ensure_unmounted(self, local_mount_path: Path, index: NonNegativeInt) -> None:
        with log_context(_logger, logging.INFO, f"unmounting {local_mount_path=}", log_duration=True):
            mount_id = get_mount_id(local_mount_path, index)
            tracked_mount = self._tracked_mounts.pop(mount_id)

            await tracked_mount.wait_for_all_transfers_to_complete()

            await tracked_mount.stop_mount()

    async def _worker_ensure_mount_is_responsive(self) -> None:
        mount_restored = False
        with log_context(_logger, logging.DEBUG, "ensuring rclone mount is responsive"):
            for mount in self._tracked_mounts.values():
                if not await mount.is_responsive():
                    with log_context(
                        _logger,
                        logging.WARNING,
                        f"Restoring mount for path='{mount.local_mount_path}'",
                    ):
                        await mount.stop_mount(skip_transfer_wait=True)
                        await mount.start_mount()
                        mount_restored = True

            if mount_restored:
                with log_context(
                    _logger,
                    logging.WARNING,
                    "Requesting service shutdown due to mount restoration",
                ):
                    # NOTE: since the mount is bind mounted, we ensure that it restarts properly
                    # then we shutdown the service since the user service will have an out of date
                    # FUSE mount.
                    await self.delegate.request_shutdown()

    async def setup(self) -> None:
        self._task_ensure_mounts_working = create_periodic_task(
            self._worker_ensure_mount_is_responsive,
            interval=timedelta(seconds=10),
            task_name="rclone-mount-ensure-mount-is-responsive",
        )

    async def teardown(self) -> None:
        if self._task_ensure_mounts_working is not None:
            await cancel_wait_task(self._task_ensure_mounts_working)

        await asyncio.gather(*[mount.stop_mount() for mount in self._tracked_mounts.values()])
        self._tracked_mounts.clear()
