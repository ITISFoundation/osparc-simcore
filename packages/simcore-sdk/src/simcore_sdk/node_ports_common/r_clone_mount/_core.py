import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from functools import cached_property
from pathlib import Path
from textwrap import dedent
from typing import Any, Final, Protocol
from uuid import uuid4

import httpx
from common_library.errors_classes import OsparcErrorMixin
from httpx import AsyncClient
from models_library.basic_types import PortInt
from models_library.progress_bar import ProgressReport
from models_library.projects_nodes_io import NodeID, StorageFileID
from pydantic import BaseModel, NonNegativeInt
from servicelib.logging_utils import log_context
from servicelib.utils import unused_port
from settings_library.r_clone import RCloneMountSettings, RCloneSettings
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

from . import _docker_utils
from ._config_provider import CONFIG_KEY, MountRemoteType, get_config_content
from ._models import GetBindPathsProtocol

_logger = logging.getLogger(__name__)


_MAX_WAIT_RC_HTTP_INTERFACE_READY: Final[timedelta] = timedelta(seconds=10)
_DEFAULT_UPDATE_INTERVAL: Final[timedelta] = timedelta(seconds=1)
_DEFAULT_R_CLONE_CLIENT_REQUEST_TIMEOUT: Final[timedelta] = timedelta(seconds=20)

_DEFAULT_MOUNT_ACTIVITY_UPDATE_INTERVAL: Final[timedelta] = timedelta(seconds=5)

_DOCKER_PREFIX_MOUNT: Final[str] = "rcm"

_NOT_FOUND: Final[int] = 404

type _MountId = str

_R_CLONE_MOUNT_TEMPLATE: Final[str] = dedent(
    """
cat <<EOF > {r_clone_config_path}
{r_clone_config_content}
EOF

{r_clone_command}
"""
)


def _get_rclone_mount_command(
    mount_settings: RCloneMountSettings,
    r_clone_config_content: str,
    remote_path: StorageFileID,
    local_mount_path: Path,
    remote_control_port: PortInt,
    rc_user: str,
    rc_password: str,
) -> str:
    escaped_remote_path = f"{remote_path}".lstrip("/")
    r_clone_command = " ".join(
        [
            "rclone",
            "--config",
            f"{mount_settings.R_CLONE_CONFIG_FILE_PATH}",
            "-vv",
            "mount",
            f"{CONFIG_KEY}:{escaped_remote_path}",
            f"{local_mount_path}",
            "--vfs-cache-mode full",
            "--vfs-write-back",
            mount_settings.R_CLONE_MOUNT_VFS_WRITE_BACK,
            "--vfs-cache-max-size",
            mount_settings.R_CLONE_MOUNT_VFS_CACHE_MAX_SIZE,
            (
                "--vfs-fast-fingerprint"
                if mount_settings.R_CLONE_MOUNT_VFS_CACHE_MAX_SIZE
                else ""
            ),
            ("--no-modtime" if mount_settings.R_CLONE_MOUNT_NO_MODTIME else ""),
            "--cache-dir",
            f"{mount_settings.R_CLONE_MOUNT_VFS_CACHE_PATH}",
            "--rc",
            f"--rc-addr=0.0.0.0:{remote_control_port}",
            "--rc-enable-metrics",
            f"--rc-user='{rc_user}'",
            f"--rc-pass='{rc_password}'",
            "--allow-non-empty",
            "--allow-other",
        ]
    )
    return _R_CLONE_MOUNT_TEMPLATE.format(
        r_clone_config_path=mount_settings.R_CLONE_CONFIG_FILE_PATH,
        r_clone_config_content=r_clone_config_content,
        r_clone_command=r_clone_command,
    )


def _get_mount_id(local_mount_path: Path, index: NonNegativeInt) -> _MountId:
    # unique reproducible id for this mount
    return f"{index}{local_mount_path}".replace("/", "_")[::-1]


class _BaseRcloneMountError(OsparcErrorMixin, RuntimeError):
    pass


class _ContainerAlreadyStartedError(_BaseRcloneMountError):
    msg_template: str = (
        "Mount process already stareted via container='{container}' with command='{command}'"
    )


class _WaitingForTransfersToCompleteError(_BaseRcloneMountError):
    msg_template: str = "Waiting for all transfers to complete"


class _WaitingForQueueToBeEmptyError(_BaseRcloneMountError):
    msg_template: str = "Waiting for VFS queue to be empty: queue={queue}"


class MountAlreadyStartedError(_BaseRcloneMountError):
    msg_template: str = "Mount already started for local path='{local_mount_path}'"


class MountNotStartedError(_BaseRcloneMountError):
    msg_template: str = "Mount not started for local path='{local_mount_path}'"


class MountActivity(BaseModel):
    transferring: dict[str, ProgressReport]
    queued: list[str]


class MountActivityProtocol(Protocol):
    async def __call__(self, state_path: Path, activity: MountActivity) -> None: ...


class ContainerManager:
    def __init__(
        self,
        mount_settings: RCloneMountSettings,
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
        self.mount_settings = mount_settings
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

            assert self.mount_settings.R_CLONE_VERSION is not None  # nosec
            await _docker_utils.create_r_clone_container(
                client,
                self.r_clone_container_name,
                command=_get_rclone_mount_command(
                    mount_settings=self.mount_settings,
                    r_clone_config_content=self.r_clone_config_content,
                    remote_path=self.remote_path,
                    local_mount_path=self.local_mount_path,
                    remote_control_port=self.remote_control_port,
                    rc_user=self.rc_user,
                    rc_password=self.rc_password,
                ),
                r_clone_version=self.mount_settings.R_CLONE_VERSION,
                remote_control_port=self.remote_control_port,
                r_clone_network_name=self._r_clone_network_name,
                local_mount_path=self.local_mount_path,
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


class RCloneRCInterfaceClient:
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

        self._cleanup_stack = AsyncExitStack()
        self._client: AsyncClient | None = None

        self._continue_running: bool = True
        self._mount_activity_task: asyncio.Task | None = None

    async def setup(self) -> None:
        self._client = await self._cleanup_stack.enter_async_context(
            AsyncClient(timeout=self._r_clone_client_timeout.total_seconds())
        )
        self._mount_activity_task = asyncio.create_task(self._mount_activity_worker())

    async def teardown(self) -> None:
        if self._mount_activity_task is not None:
            self._continue_running = False
            await self._mount_activity_task
            self._mount_activity_task = None

        await self._cleanup_stack.aclose()

    @property
    def _base_url(self) -> str:
        return f"http://{self._rc_host}:{self._rc_port}"

    async def _request(self, method: str, path: str) -> Any:
        assert self._client is not None  # nosec

        request_url = f"{self._base_url}/{path}"
        _logger.debug("Sending '%s %s' request", method, request_url)
        response = await self._client.request(
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

    async def _mount_activity_worker(self) -> None:
        while self._continue_running:
            await asyncio.sleep(self._update_interval_seconds)

            core_stats, vfs_queue = await asyncio.gather(
                self._post_core_stats(), self._post_vfs_queue()
            )

            mount_activity = MountActivity(
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

            await self._update_handler(mount_activity)

    @retry(
        wait=wait_fixed(1),
        stop=stop_after_delay(_MAX_WAIT_RC_HTTP_INTERFACE_READY.total_seconds()),
        reraise=True,
        retry=retry_if_exception_type(httpx.HTTPError),
        before_sleep=before_sleep_log(_logger, logging.WARNING),
    )
    async def wait_for_interface_to_be_ready(self) -> None:
        await self._rc_noop()

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
                (_WaitingForQueueToBeEmptyError, _WaitingForTransfersToCompleteError)
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
                raise _WaitingForTransfersToCompleteError

            queue = vfs_queue["queue"]
            if len(queue) != 0:
                raise _WaitingForQueueToBeEmptyError(queue=queue)

        await _()


class TrackedMount:
    def __init__(
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

        # used internally to handle the mount command
        self._container_manager = ContainerManager(
            mount_settings=self.r_clone_settings.R_CLONE_MOUNT_SETTINGS,
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

        self._rc_interface: RCloneRCInterfaceClient | None = None
        self._cleanup_stack = AsyncExitStack()

    @property
    def rc_interface(self) -> RCloneRCInterfaceClient:
        assert self._rc_interface is not None  # nosec
        return self._rc_interface

    async def _progress_handler(self, mount_activity: MountActivity) -> None:
        now = datetime.now(UTC)

        enough_time_passed = (
            now - self._last_mount_activity_update
            > self._mount_activity_update_interval
        )

        if enough_time_passed and self._last_mount_activity != mount_activity:
            self._last_mount_activity = mount_activity
            self._last_mount_activity_update = now

            await self.handler_mount_activity(self.local_mount_path, mount_activity)

    async def teardown(self) -> None:
        await self.stop_mount()

    async def start_mount(self) -> None:

        if self.r_clone_settings.R_CLONE_MOUNT_SETTINGS.R_CLONE_VERSION is None:
            msg = "R_CLONE_VERSION setting is not set"
            raise RuntimeError(msg)

        self._rc_interface: RCloneRCInterfaceClient | None = RCloneRCInterfaceClient(
            remote_control_port=self.rc_port,
            r_clone_mount_settings=self.r_clone_settings.R_CLONE_MOUNT_SETTINGS,
            remote_control_host=self._container_manager.r_clone_container_name,
            rc_user=self.rc_user,
            rc_password=self.rc_password,
            update_handler=self._progress_handler,
        )

        await self._container_manager.create()
        await self.rc_interface.setup()
        await self.rc_interface.wait_for_interface_to_be_ready()

    async def stop_mount(self) -> None:

        await self.rc_interface.wait_for_all_transfers_to_complete()
        await self.rc_interface.teardown()
        self._rc_interface = None

        await self._container_manager.remove()

        await self._cleanup_stack.aclose()


class RCloneMountManager:
    def __init__(self, r_clone_settings: RCloneSettings) -> None:
        self.r_clone_settings = r_clone_settings
        if self.r_clone_settings.R_CLONE_MOUNT_SETTINGS.R_CLONE_VERSION is None:
            msg = "R_CLONE_VERSION setting is not set"
            raise RuntimeError(msg)

        # TODO: make this stateless and go via aiodocker to avoid issues when restartign the container
        self._started_mounts: dict[_MountId, TrackedMount] = {}

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
        # check if rlcone mount exists
        #

        with log_context(
            _logger,
            logging.INFO,
            f"mounting {local_mount_path=} from {remote_path=}",
            log_duration=True,
        ):
            mount_id = _get_mount_id(local_mount_path, index)
            if mount_id in self._started_mounts:
                tracked_mount = self._started_mounts[mount_id]
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

            self._started_mounts[mount_id] = tracked_mount

    async def wait_for_transfers_to_complete(
        self, local_mount_path: Path, index: NonNegativeInt
    ) -> None:
        # if mount is not present it just returns immediately

        with log_context(
            _logger,
            logging.INFO,
            f"wait for transfers to complete {local_mount_path=}",
            log_duration=True,
        ):
            mount_id = _get_mount_id(local_mount_path, index)
            if mount_id not in self._started_mounts:
                raise MountNotStartedError(local_mount_path=local_mount_path)

            tracked_mount = self._started_mounts[mount_id]
            await tracked_mount.rc_interface.wait_for_all_transfers_to_complete()

    async def was_mount_started(
        self, local_mount_path: Path, index: NonNegativeInt
    ) -> bool:
        # checks if mount is present or not
        mount_id = _get_mount_id(local_mount_path, index)
        return mount_id in self._started_mounts

    async def ensure_unmounted(
        self, local_mount_path: Path, index: NonNegativeInt
    ) -> None:
        # make sure this is done using stateless docker api calls
        with log_context(
            _logger, logging.INFO, f"unmounting {local_mount_path=}", log_duration=True
        ):
            mount_id = _get_mount_id(local_mount_path, index)
            if mount_id not in self._started_mounts:
                # TODO: check if this is running on docker, then shutdown -> otherwise sidecar will break
                raise MountNotStartedError(local_mount_path=local_mount_path)

            tracked_mount = self._started_mounts[mount_id]
            await tracked_mount.stop_mount()

    async def setup(self) -> None:
        # TODO: add a process which ensures that the mounts keep running -> register some local data to restart the mount process if it dies (even on accident manually)

        pass

    async def teardown(self) -> None:
        # shutdown still ongoing mounts
        await asyncio.gather(
            *[mount.teardown() for mount in self._started_mounts.values()]
        )
        self._started_mounts.clear()


# NOTES:
# There are multiple layers in place here
# - docker api to create/remove containers and networks
# - rclone container management
# - rclone process status management via its rc http interface
# - mounts management
