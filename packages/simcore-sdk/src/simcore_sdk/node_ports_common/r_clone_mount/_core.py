import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from functools import cached_property
from pathlib import Path
from textwrap import dedent
from typing import Any, Final
from uuid import uuid4

from common_library.async_tools import cancel_wait_task
from httpx import AsyncClient, HTTPError
from models_library.basic_types import PortInt
from models_library.progress_bar import ProgressReport
from models_library.projects_nodes_io import NodeID, StorageFileID
from pydantic import NonNegativeInt
from servicelib.background_task import create_periodic_task
from servicelib.logging_utils import log_catch, log_context
from servicelib.utils import unused_port
from settings_library.r_clone import (
    RCloneMountSettings,
    RCloneSettings,
    get_rclone_common_optimizations,
)
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

from . import _docker_utils
from ._config_provider import CONFIG_KEY, MountRemoteType, get_config_content
from ._errors import (
    MountAlreadyStartedError,
    WaitingForQueueToBeEmptyError,
    WaitingForTransfersToCompleteError,
)
from ._models import (
    GetBindPathsProtocol,
    MountActivity,
    MountActivityProtocol,
    RequestShutdownProtocol,
)

_logger = logging.getLogger(__name__)


_MAX_WAIT_RC_HTTP_INTERFACE_READY: Final[timedelta] = timedelta(seconds=10)
_DEFAULT_UPDATE_INTERVAL: Final[timedelta] = timedelta(seconds=1)
_DEFAULT_R_CLONE_CLIENT_REQUEST_TIMEOUT: Final[timedelta] = timedelta(seconds=20)

_DEFAULT_MOUNT_ACTIVITY_UPDATE_INTERVAL: Final[timedelta] = timedelta(seconds=5)

_DOCKER_PREFIX_MOUNT: Final[str] = "rcm"

type _MountId = str

_R_CLONE_MOUNT_TEMPLATE: Final[str] = dedent(
    """
set -e

MOUNT_POINT='{local_mount_path}'

cleanup() {{
  echo 'STARTED CLEANUP...'
  umount -f "$MOUNT_POINT" || true
  echo 'FINISHED CLEANUP'
}}
trap cleanup SIGTERM SIGINT

cat <<EOF > {r_clone_config_path}
{r_clone_config_content}
EOF

echo "Start command: {r_clone_command}"

{r_clone_command} 2>&1 &

RCLONE_PID=$!
wait "$RCLONE_PID"
echo "rclone exited, running cleanup (if not already triggered)..."
cleanup
"""
)


def _get_rclone_mount_command(
    r_clone_settings: RCloneSettings,
    r_clone_config_content: str,
    remote_path: StorageFileID,
    local_mount_path: Path,
    remote_control_port: PortInt,
    rc_user: str,
    rc_password: str,
) -> str:
    mount_settings = r_clone_settings.R_CLONE_MOUNT_SETTINGS
    escaped_remote_path = f"{remote_path}".lstrip("/")

    r_clone_command = " ".join(
        [
            "rclone",
            "--config",
            f"{mount_settings.R_CLONE_CONTAINER_CONFIG_FILE_PATH}",
            ("-vv" if mount_settings.R_CLONE_CONTAINER_MOUNT_SHOW_DEBUG_LOGS else ""),
            "mount",
            f"{CONFIG_KEY}:{escaped_remote_path}",
            f"{local_mount_path}",
            # VFS
            "--vfs-cache-mode",
            "full",
            "--vfs-read-ahead",
            mount_settings.R_CLONE_VFS_READ_AHEAD,
            "--vfs-cache-max-size",
            mount_settings.R_CLONE_MOUNT_VFS_CACHE_MAX_SIZE,
            "--vfs-cache-min-free-space",
            mount_settings.R_CLONE_MOUNT_VFS_CACHE_MIN_FREE_SPACE,
            "--vfs-cache-poll-interval",
            mount_settings.R_CLONE_CACHE_POLL_INTERVAL,
            "--vfs-write-back",
            mount_settings.R_CLONE_MOUNT_VFS_WRITE_BACK,
            (
                "--vfs-fast-fingerprint"
                if mount_settings.R_CLONE_MOUNT_VFS_FAST_FINGERPRINT
                else ""
            ),
            "--cache-dir",
            f"{mount_settings.R_CLONE_MOUNT_VFS_CACHE_PATH}",
            "--dir-cache-time",
            mount_settings.R_CLONE_DIR_CACHE_TIME,
            "--attr-timeout",
            mount_settings.R_CLONE_ATTR_TIMEOUT,
            "--tpslimit",
            f"{mount_settings.R_CLONE_TPSLIMIT}",
            "--tpslimit-burst",
            f"{mount_settings.R_CLONE_TPSLIMIT_BURST}",
            ("--no-modtime" if mount_settings.R_CLONE_MOUNT_NO_MODTIME else ""),
            # REMOTE CONTROL
            "--rc",
            f"--rc-addr=0.0.0.0:{remote_control_port}",
            "--rc-enable-metrics",
            f"--rc-user='{rc_user}'",
            f"--rc-pass='{rc_password}'",
            "--allow-non-empty",
            "--allow-other",
            *get_rclone_common_optimizations(r_clone_settings),
        ]
    )
    return _R_CLONE_MOUNT_TEMPLATE.format(
        r_clone_config_path=mount_settings.R_CLONE_CONTAINER_CONFIG_FILE_PATH,
        r_clone_config_content=r_clone_config_content,
        r_clone_command=r_clone_command,
        local_mount_path=local_mount_path,
    )


def _get_mount_id(local_mount_path: Path, index: NonNegativeInt) -> _MountId:
    # unique reproducible id for the mount
    return f"{index}{local_mount_path}".replace("/", "_")[::-1]


class ContainerManager:  # pylint:disable=too-many-instance-attributes
    def __init__(  # pylint:disable=too-many-arguments
        self,
        r_clone_settings: RCloneSettings,
        node_id: NodeID,
        remote_control_port: PortInt,
        local_mount_path: Path,
        index: NonNegativeInt,
        r_clone_config_content: str,
        remote_path: str,
        rc_user: str,
        rc_password: str,
        *,
        handler_get_bind_paths: GetBindPathsProtocol,
    ) -> None:
        self.r_clone_settings = r_clone_settings
        self.node_id = node_id
        self.remote_control_port = remote_control_port
        self.local_mount_path = local_mount_path
        self.index = index
        self.r_clone_config_content = r_clone_config_content
        self.remote_path = remote_path
        self.rc_user = rc_user
        self.rc_password = rc_password

        self.handler_get_bind_paths = handler_get_bind_paths

    @cached_property
    def r_clone_container_name(self) -> str:
        mount_id = _get_mount_id(self.local_mount_path, self.index)
        return f"{_DOCKER_PREFIX_MOUNT}-c-{self.node_id}{mount_id}"[:63]

    @cached_property
    def _r_clone_network_name(self) -> str:
        mount_id = _get_mount_id(self.local_mount_path, self.index)
        return f"{_DOCKER_PREFIX_MOUNT}-c-{self.node_id}{mount_id}"[:63]

    async def create(self):
        async with _docker_utils.get_or_crate_docker_session(None) as client:
            # ensure nothing was left from previous runs
            await _docker_utils.remove_container_if_exists(
                client, self.r_clone_container_name
            )
            await _docker_utils.remove_network_if_exists(
                client, self.r_clone_container_name
            )

            # create network + container and connect to sidecar
            await _docker_utils.create_network_and_connect_sidecar_container(
                client, self._r_clone_network_name
            )

            mount_settings = self.r_clone_settings.R_CLONE_MOUNT_SETTINGS
            assert mount_settings.R_CLONE_CONTAINER_VERSION is not None  # nosec
            await _docker_utils.create_r_clone_container(
                client,
                self.r_clone_container_name,
                command=_get_rclone_mount_command(
                    r_clone_settings=self.r_clone_settings,
                    r_clone_config_content=self.r_clone_config_content,
                    remote_path=self.remote_path,
                    local_mount_path=self.local_mount_path,
                    remote_control_port=self.remote_control_port,
                    rc_user=self.rc_user,
                    rc_password=self.rc_password,
                ),
                r_clone_version=mount_settings.R_CLONE_CONTAINER_VERSION,
                remote_control_port=self.remote_control_port,
                r_clone_network_name=self._r_clone_network_name,
                local_mount_path=self.local_mount_path,
                memory_limit=mount_settings.R_CLONE_CONTAINER_MEMORY_LIMIT,
                nano_cpus=mount_settings.R_CLONE_CONTAINER_NANO_CPUS,
                handler_get_bind_paths=self.handler_get_bind_paths,
            )

    async def remove(self):
        async with _docker_utils.get_or_crate_docker_session(None) as client:
            await _docker_utils.remove_container_if_exists(
                client, self.r_clone_container_name
            )
            await _docker_utils.remove_network_if_exists(
                client, self.r_clone_container_name
            )


class RemoteControlHttpClient:
    def __init__(
        self,
        remote_control_port: PortInt,
        r_clone_mount_settings: RCloneMountSettings,
        remote_control_host: str,
        rc_user: str,
        rc_password: str,
        *,
        update_handler: Callable[[MountActivity], Awaitable[None]],
        update_interval: timedelta = _DEFAULT_UPDATE_INTERVAL,
        r_clone_client_timeout: timedelta = _DEFAULT_R_CLONE_CLIENT_REQUEST_TIMEOUT,
    ) -> None:
        self._r_clone_mount_settings = r_clone_mount_settings
        self._update_interval_seconds = update_interval.total_seconds()
        self._r_clone_client_timeout = r_clone_client_timeout
        self._rc_user = rc_user
        self._rc_password = rc_password
        self._update_handler = update_handler

        self._rc_host = remote_control_host
        self._rc_port = remote_control_port

    @property
    def _base_url(self) -> str:
        return f"http://{self._rc_host}:{self._rc_port}"

    async def _request(self, method: str, path: str) -> Any:
        request_url = f"{self._base_url}/{path}"
        _logger.debug("Sending '%s %s' request", method, request_url)

        async with AsyncClient(
            timeout=self._r_clone_client_timeout.total_seconds()
        ) as client:
            response = await client.request(
                method, request_url, auth=(self._rc_user, self._rc_password)
            )
            response.raise_for_status()
            result = response.json()

        _logger.debug("'%s %s' replied with: %s", method, path, result)
        return result

    async def _post_core_stats(self) -> dict:
        return await self._request("POST", "core/stats")

    async def _post_vfs_queue(self) -> dict:
        return await self._request("POST", "vfs/queue")

    async def _rc_noop(self) -> dict:
        return await self._request("POST", "rc/noop")

    async def get_mount_activity(self) -> MountActivity:
        core_stats, vfs_queue = await asyncio.gather(
            self._post_core_stats(), self._post_vfs_queue()
        )

        return MountActivity(
            transferring=(
                {
                    x["name"]: ProgressReport(
                        actual_value=(
                            x["percentage"] / 100 if "percentage" in x else 0.0
                        )
                    )
                    for x in core_stats["transferring"]
                }
                if "transferring" in core_stats
                else {}
            ),
            queued=[x["name"] for x in vfs_queue["queue"]],
        )

    @retry(
        wait=wait_fixed(1),
        stop=stop_after_delay(_MAX_WAIT_RC_HTTP_INTERFACE_READY.total_seconds()),
        reraise=True,
        retry=retry_if_exception_type(HTTPError),
        before_sleep=before_sleep_log(_logger, logging.WARNING),
    )
    async def wait_for_interface_to_be_ready(self) -> None:
        await self._rc_noop()

    async def is_responsive(self) -> bool:
        try:
            await self._rc_noop()
            return True
        except HTTPError:
            return False

    async def wait_for_all_transfers_to_complete(self) -> None:
        """
        Should be waited before closing the mount
        to ensure all data is transferred to remote.
        """

        @retry(
            wait=wait_fixed(1),
            stop=stop_after_delay(
                self._r_clone_mount_settings.R_CLONE_MOUNT_TRANSFERS_COMPLETED_TIMEOUT.total_seconds()
            ),
            reraise=True,
            retry=retry_if_exception_type(
                (WaitingForQueueToBeEmptyError, WaitingForTransfersToCompleteError)
            ),
            before_sleep=before_sleep_log(_logger, logging.WARNING),
        )
        async def _() -> None:
            core_stats, vfs_queue = await asyncio.gather(
                self._post_core_stats(), self._post_vfs_queue()
            )

            if (
                core_stats["transfers"] != core_stats["totalTransfers"]
                or "transferring" in core_stats
            ):
                raise WaitingForTransfersToCompleteError

            queue = vfs_queue["queue"]
            if len(queue) != 0:
                raise WaitingForQueueToBeEmptyError(queue=queue)

        await _()


class TrackedMount:  # pylint:disable=too-many-instance-attributes
    def __init__(  # pylint:disable=too-many-arguments
        self,
        node_id: NodeID,
        r_clone_settings: RCloneSettings,
        remote_type: MountRemoteType,
        *,
        rc_port: PortInt,
        remote_path: StorageFileID,
        local_mount_path: Path,
        index: NonNegativeInt,
        handler_get_bind_paths: GetBindPathsProtocol,
        handler_mount_activity: MountActivityProtocol,
        mount_activity_update_interval: timedelta = _DEFAULT_MOUNT_ACTIVITY_UPDATE_INTERVAL,
    ) -> None:
        self.node_id = node_id
        self.r_clone_settings = r_clone_settings
        self.mount_type = remote_type
        self.rc_port = rc_port
        self.remote_path = remote_path
        self.local_mount_path = local_mount_path
        self.index = index
        self.rc_user = f"{uuid4()}"
        self.rc_password = f"{uuid4()}"
        self.handler_get_bind_paths = handler_get_bind_paths
        self.handler_mount_activity = handler_mount_activity

        self._last_mount_activity: MountActivity | None = None
        self._last_mount_activity_update: datetime = datetime.fromtimestamp(0, UTC)
        self._mount_activity_update_interval = mount_activity_update_interval
        self._task_mount_activity: asyncio.Task[None] | None = None

        # used internally to handle the mount command
        self._container_manager = ContainerManager(
            r_clone_settings=self.r_clone_settings,
            node_id=self.node_id,
            remote_control_port=self.rc_port,
            local_mount_path=self.local_mount_path,
            index=self.index,
            r_clone_config_content=get_config_content(
                self.r_clone_settings, self.mount_type
            ),
            remote_path=f"{self.r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME}/{self.remote_path}",
            rc_user=self.rc_user,
            rc_password=self.rc_password,
            handler_get_bind_paths=self.handler_get_bind_paths,
        )

        self._rc_http_client = RemoteControlHttpClient(
            remote_control_port=self.rc_port,
            r_clone_mount_settings=self.r_clone_settings.R_CLONE_MOUNT_SETTINGS,
            remote_control_host=self._container_manager.r_clone_container_name,
            rc_user=self.rc_user,
            rc_password=self.rc_password,
            update_handler=self._handler_mount_activity,
        )

    async def _handler_mount_activity(self, mount_activity: MountActivity) -> None:
        now = datetime.now(UTC)

        enough_time_passed = (
            now - self._last_mount_activity_update
            > self._mount_activity_update_interval
        )

        if enough_time_passed and self._last_mount_activity != mount_activity:
            self._last_mount_activity = mount_activity
            self._last_mount_activity_update = now

            await self.handler_mount_activity(self.local_mount_path, mount_activity)

    async def _worker_mount_activity(self) -> None:
        mount_activity = await self._rc_http_client.get_mount_activity()
        with log_catch(logger=_logger, reraise=False):
            await self._handler_mount_activity(mount_activity)

    async def start_mount(self) -> None:
        await self._container_manager.create()

        await self._rc_http_client.wait_for_interface_to_be_ready()

        self._task_mount_activity = create_periodic_task(
            self._worker_mount_activity,
            interval=self._mount_activity_update_interval,
            task_name=f"rclone-mount-activity-{_get_mount_id(self.local_mount_path, self.index)}",
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
        handler_request_shutdown: RequestShutdownProtocol,
    ) -> None:
        self.r_clone_settings = r_clone_settings
        self.handler_request_shutdown = handler_request_shutdown
        if (
            self.r_clone_settings.R_CLONE_MOUNT_SETTINGS.R_CLONE_CONTAINER_VERSION
            is None
        ):
            msg = "R_CLONE_VERSION setting is not set"
            raise RuntimeError(msg)

        self._tracked_mounts: dict[_MountId, TrackedMount] = {}
        self._task_ensure_mounts_working: asyncio.Task[None] | None = None

    async def ensure_mounted(
        self,
        local_mount_path: Path,
        index: NonNegativeInt,
        *,
        node_id: NodeID,
        remote_type: MountRemoteType,
        remote_path: StorageFileID,
        handler_get_bind_paths: GetBindPathsProtocol,
        handler_mount_activity: MountActivityProtocol,
    ) -> None:
        with log_context(
            _logger,
            logging.INFO,
            f"mounting {local_mount_path=} from {remote_path=}",
            log_duration=True,
        ):
            mount_id = _get_mount_id(local_mount_path, index)
            if mount_id in self._tracked_mounts:
                tracked_mount = self._tracked_mounts[mount_id]
                raise MountAlreadyStartedError(local_mount_path=local_mount_path)

            free_port = await asyncio.get_running_loop().run_in_executor(
                None, unused_port
            )

            tracked_mount = TrackedMount(
                node_id,
                self.r_clone_settings,
                remote_type,
                rc_port=free_port,
                remote_path=remote_path,
                local_mount_path=local_mount_path,
                index=index,
                handler_get_bind_paths=handler_get_bind_paths,
                handler_mount_activity=handler_mount_activity,
            )
            await tracked_mount.start_mount()

            self._tracked_mounts[mount_id] = tracked_mount

    def is_mount_tracked(self, local_mount_path: Path, index: NonNegativeInt) -> bool:
        """True if if a mount is being tracked"""
        mount_id = _get_mount_id(local_mount_path, index)
        return mount_id in self._tracked_mounts

    async def ensure_unmounted(
        self, local_mount_path: Path, index: NonNegativeInt
    ) -> None:
        with log_context(
            _logger, logging.INFO, f"unmounting {local_mount_path=}", log_duration=True
        ):
            mount_id = _get_mount_id(local_mount_path, index)
            tracked_mount = self._tracked_mounts[mount_id]

            await tracked_mount.wait_for_all_transfers_to_complete()

            await tracked_mount.stop_mount()

    async def _worker_ensure_mounts_working(self) -> None:
        mount_restored = False
        with log_context(_logger, logging.DEBUG, "Ensuring rclone mounts are working"):
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
                    await self.handler_request_shutdown()

    async def setup(self) -> None:
        self._task_ensure_mounts_working = create_periodic_task(
            self._worker_ensure_mounts_working,
            interval=timedelta(seconds=10),
            task_name="rclone-mount-ensure-mounts-working",
        )

    async def teardown(self) -> None:
        # shutdown still ongoing mounts
        await asyncio.gather(
            *[mount.stop_mount() for mount in self._tracked_mounts.values()]
        )
        self._tracked_mounts.clear()

        if self._task_ensure_mounts_working is not None:
            await cancel_wait_task(self._task_ensure_mounts_working)
