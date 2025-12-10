import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final
from uuid import uuid4

import httpx
from common_library.errors_classes import OsparcErrorMixin
from httpx import AsyncClient
from models_library.basic_types import PortInt
from models_library.progress_bar import ProgressReport
from models_library.projects_nodes_io import StorageFileID
from pydantic import BaseModel, NonNegativeFloat
from servicelib.container_utils import run_command_in_container
from servicelib.logging_utils import log_catch, log_context
from servicelib.r_clone_utils import config_file
from servicelib.utils import unused_port
from settings_library.r_clone import RCloneMountSettings, RCloneSettings
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

from ._config_provider import CONFIG_KEY, MountRemoteType, get_config_content

_logger = logging.getLogger(__name__)


_DEFAULT_REMOTE_CONTROL_HOST: Final[str] = "localhost"
_MAX_WAIT_RC_HTTP_INTERFACE_READY: Final[timedelta] = timedelta(seconds=10)
_DEFAULT_UPDATE_INTERVAL: Final[timedelta] = timedelta(seconds=1)
_DEFAULT_R_CLONE_CLIENT_REQUEST_TIMEOUT: Final[timedelta] = timedelta(seconds=5)

_DEFAULT_MOUNT_ACTIVITY_UPDATE_INTERVAL: Final[timedelta] = timedelta(seconds=5)


class _BaseRcloneMountError(OsparcErrorMixin, RuntimeError):
    pass


class _ProcessAlreadyStartedError(_BaseRcloneMountError):
    msg_template: str = "Process already started with pid='{pid}' via '{command}'"


class _TrackedMountAlreadyStartedError(_BaseRcloneMountError):
    msg_template: str = (
        "Mount process already stareted with pid='{pid}' via '{command}'"
    )


class _WaitingForTransfersToCompleteError(_BaseRcloneMountError):
    msg_template: str = "Waiting for all transfers to complete"


class _WaitingForQueueToBeEmptyError(_BaseRcloneMountError):
    msg_template: str = "Waiting for VFS queue to be empty: queue={queue}"


class MountAlreadyStartedError(_BaseRcloneMountError):
    msg_template: str = "Mount already started for local path='{local_mount_path}'"


class MountNotStartedError(_BaseRcloneMountError):
    msg_template: str = "Mount not started for local path='{local_mount_path}'"


def _get_command__pid_of_background_command(command: str) -> str:
    return f"sh -c '{command} & echo $!'"


def _get_command__sigterm_process(pid: str) -> str:
    return f"kill -SIGTERM {pid}"


class DaemonProcessManager:
    """manage a command that is meant to run in a container forever"""

    def __init__(self, command: str, *, timeout: NonNegativeFloat = 5) -> None:
        self.command = command
        self.timeout = timeout
        self.pid: str | None = None

    async def _run_in_container(self, command: str) -> str:
        self_container = os.environ["HOSTNAME"]
        return await run_command_in_container(
            self_container, command=command, timeout=self.timeout
        )

    async def start(self):
        if self.pid:
            raise _ProcessAlreadyStartedError(pid=self.pid, command=self.command)

        command_result = await self._run_in_container(
            command=_get_command__pid_of_background_command(self.command)
        )
        # pid is printed as the first line of the output
        self.pid = command_result.strip().split("\n")[0]
        _logger.debug("Started rclone mount with pid=%s", self.pid)

    async def stop(self):
        if self.pid is None:
            return

        # since the process could have failed to start or failed shortly after
        # starting the pid mind not be corresponding to a running process
        # and will raise an error
        with log_catch(_logger, reraise=False):
            await self._run_in_container(
                command=_get_command__sigterm_process(self.pid)
            )


def _get_rclone_mount_command(
    config_file_path: str,
    remote_path: StorageFileID,
    local_mount_path: Path,
    vfs_cache_path: Path,
    rc_addr: str,
    rc_user: str,
    rc_password: str,
) -> str:
    escaped_remote_path = f"{remote_path}".lstrip("/")
    command: list[str] = [
        "rclone",
        "--config",
        config_file_path,
        f"--log-file=/tmp/rclone-debug{uuid4()}.log",  # TODO: maybe it is possible to make a reproducible path insteaa of random for simpler access to logs?
        "-vv",
        "mount",
        f"{CONFIG_KEY}:{escaped_remote_path}",
        f"{local_mount_path}",
        "--vfs-cache-mode full",
        "--vfs-write-back",
        "1s",  # write-back delay    TODO: could be part of the settings?
        "--vfs-fast-fingerprint",  # recommended for s3 backend  TODO: could be part of the settings?
        "--no-modtime",  # don't read/write the modification time    TODO: could be part of the settings?
        "--cache-dir",
        f"{vfs_cache_path}",
        "--rc",
        f"--rc-addr={rc_addr}",
        "--rc-enable-metrics",
        f"--rc-user='{rc_user}'",
        f"--rc-pass='{rc_password}'",
        "--allow-non-empty",
    ]
    return " ".join(command)


class MountActivity(BaseModel):
    transferring: dict[str, ProgressReport]
    queued: list[str]


class RCloneRCInterfaceClient:
    def __init__(
        self,
        remote_control_port: PortInt,
        r_clone_mount_settings: RCloneMountSettings,
        *,
        update_handler: Callable[[MountActivity], Awaitable[None]],
        remote_control_host: str = _DEFAULT_REMOTE_CONTROL_HOST,
        update_interval: timedelta = _DEFAULT_UPDATE_INTERVAL,
        r_clone_client_timeout: timedelta = _DEFAULT_R_CLONE_CLIENT_REQUEST_TIMEOUT,
    ) -> None:
        self._r_clone_mount_settings = r_clone_mount_settings
        self._update_interval_seconds = update_interval.total_seconds()
        self._r_clone_client_timeout = r_clone_client_timeout
        self._update_handler = update_handler

        self._rc_host = remote_control_host
        self._rc_port = remote_control_port
        self.rc_user = f"{uuid4()}"
        self.rc_password = f"{uuid4()}"

        self._cleanup_stack = AsyncExitStack()
        self._client: AsyncClient | None = None

        self._continue_running: bool = True
        self._transfer_monitor: asyncio.Task | None = None

    async def setup(self) -> None:
        self._client = await self._cleanup_stack.enter_async_context(
            AsyncClient(timeout=self._r_clone_client_timeout.total_seconds())
        )
        self._transfer_monitor = asyncio.create_task(self._monitor())

    async def teardown(self) -> None:
        if self._transfer_monitor is not None:
            self._continue_running = False
            await self._transfer_monitor
            self._transfer_monitor = None

        await self._cleanup_stack.aclose()

    @property
    def _base_url(self) -> str:
        return f"http://{self._rc_host}:{self._rc_port}"

    async def _request(self, method: str, path: str) -> Any:
        assert self._client is not None  # nosec

        response = await self._client.request(
            method, f"{self._base_url}/{path}", auth=(self.rc_user, self.rc_password)
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

    async def _monitor(self) -> None:
        while self._continue_running:
            await asyncio.sleep(self._update_interval_seconds)

            core_stats, vfs_queue = await asyncio.gather(
                self._post_core_stats(), self._post_vfs_queue()
            )

            mount_activity = MountActivity(
                transferring=(
                    {
                        x["name"]: ProgressReport(actual_value=x["percentage"] / 100)
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
        r_clone_settings: RCloneSettings,
        remote_type: MountRemoteType,
        *,
        rc_port: PortInt,
        remote_path: StorageFileID,
        local_mount_path: Path,
        vfs_cache_path: Path,
        mount_activity_update_interval: timedelta = _DEFAULT_MOUNT_ACTIVITY_UPDATE_INTERVAL,
    ) -> None:
        self.r_clone_settings = r_clone_settings
        self.mount_type = remote_type
        self.rc_port = rc_port
        self.remote_path = remote_path
        self.local_mount_path = local_mount_path
        self.vfs_cache_path = vfs_cache_path

        self.rc_interface = RCloneRCInterfaceClient(
            remote_control_port=rc_port,
            r_clone_mount_settings=r_clone_settings.R_CLONE_MOUNT_SETTINGS,
            update_handler=self._progress_handler,
        )
        self._last_mount_activity: MountActivity | None = None
        self._last_mount_activity_update: datetime = datetime.fromtimestamp(0, UTC)
        self._mount_activity_update_interval = mount_activity_update_interval

        # used internally to handle the mount command
        self._daemon_manager: DaemonProcessManager | None = None
        self._cleanup_stack = AsyncExitStack()

    async def _progress_handler(self, mount_activity: MountActivity) -> None:
        now = datetime.now(UTC)

        enough_time_passed = (
            now - self._last_mount_activity_update
            > self._mount_activity_update_interval
        )

        if enough_time_passed and self._last_mount_activity != mount_activity:
            self._last_mount_activity = mount_activity
            self._last_mount_activity_update = now

            # NOTE: this could also be useful if pushed to the UI
            _logger.info(
                "Activity for '%s': %s",
                self.local_mount_path,
                self._last_mount_activity,
            )

    async def teardown(self) -> None:
        await self.stop_mount()

    async def start_mount(self) -> None:
        if self._daemon_manager is not None:
            raise _TrackedMountAlreadyStartedError(
                pid=self._daemon_manager.pid, command=self._daemon_manager.command
            )

        config_file_path = await self._cleanup_stack.enter_async_context(
            config_file(get_config_content(self.r_clone_settings, self.mount_type))
        )

        self._daemon_manager = DaemonProcessManager(
            command=_get_rclone_mount_command(
                config_file_path=config_file_path,
                remote_path=f"{self.r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME}/{self.remote_path}",
                local_mount_path=self.local_mount_path,
                vfs_cache_path=self.vfs_cache_path,
                rc_addr=f"0.0.0.0:{self.rc_port}",
                rc_user=self.rc_interface.rc_user,
                rc_password=self.rc_interface.rc_password,
            )
        )
        await self._daemon_manager.start()
        await self.rc_interface.setup()
        await self.rc_interface.wait_for_interface_to_be_ready()

    async def stop_mount(self) -> None:
        if self._daemon_manager is None:
            return

        await self.rc_interface.wait_for_all_transfers_to_complete()
        await self.rc_interface.teardown()

        await self._daemon_manager.stop()
        self._daemon_manager = None

        await self._cleanup_stack.aclose()


class RCloneMountManager:
    def __init__(self, r_clone_settings: RCloneSettings) -> None:
        self.r_clone_settings = r_clone_settings
        self._common_vfs_cache_path = (
            self.r_clone_settings.R_CLONE_MOUNT_SETTINGS.R_CLONE_MOUNT_VFS_CACHE_PATH
        )

        self._started_mounts: dict[str, TrackedMount] = {}

    @staticmethod
    def _get_mount_id(local_mount_path: Path) -> str:
        return f"{local_mount_path}".replace("/", "_")

    async def start_mount(
        self,
        remote_type: MountRemoteType,
        remote_path: StorageFileID,
        local_mount_path: Path,
        vfs_cache_path_overwrite: Path | None = None,
    ) -> None:
        with log_context(
            _logger,
            logging.INFO,
            f"mounting {local_mount_path=} from {remote_path=}",
            log_duration=True,
        ):
            mount_id = self._get_mount_id(local_mount_path)
            if mount_id in self._started_mounts:
                tracked_mount = self._started_mounts[mount_id]
                raise MountAlreadyStartedError(local_mount_path=local_mount_path)

            vfs_cache_path = (
                vfs_cache_path_overwrite or self._common_vfs_cache_path
            ) / mount_id
            vfs_cache_path.mkdir(parents=True, exist_ok=True)

            free_port = await asyncio.get_running_loop().run_in_executor(
                None, unused_port
            )

            tracked_mount = TrackedMount(
                self.r_clone_settings,
                remote_type,
                rc_port=free_port,
                remote_path=remote_path,
                local_mount_path=local_mount_path,
                vfs_cache_path=vfs_cache_path,
            )
            await tracked_mount.start_mount()

            self._started_mounts[mount_id] = tracked_mount

    async def wait_for_transfers_to_complete(self, local_mount_path: Path) -> None:
        with log_context(
            _logger,
            logging.INFO,
            f"wait for transfers to complete {local_mount_path=}",
            log_duration=True,
        ):
            mount_id = self._get_mount_id(local_mount_path)
            if mount_id not in self._started_mounts:
                raise MountNotStartedError(local_mount_path=local_mount_path)

            tracked_mount = self._started_mounts[mount_id]
            await tracked_mount.rc_interface.wait_for_all_transfers_to_complete()

    async def stop_mount(self, local_mount_path: Path) -> None:
        with log_context(
            _logger, logging.INFO, f"unmounting {local_mount_path=}", log_duration=True
        ):
            mount_id = self._get_mount_id(local_mount_path)
            if mount_id not in self._started_mounts:
                raise MountNotStartedError(local_mount_path=local_mount_path)

            tracked_mount = self._started_mounts[mount_id]
            await tracked_mount.stop_mount()

    async def setup(self) -> None:
        pass

    async def teardown(self) -> None:
        # shutdown still ongoing mounts
        await asyncio.gather(
            *[mount.teardown() for mount in self._started_mounts.values()]
        )
        self._started_mounts.clear()


# TODO: oauth atuthorization pattern needs to be setup for non S3 providers
