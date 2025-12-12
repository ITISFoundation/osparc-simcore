import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from functools import cached_property
from pathlib import Path
from textwrap import dedent
from typing import Any, Final, Protocol
from uuid import uuid4

import aiodocker
import httpx
from aiodocker.containers import DockerContainer
from aiodocker.networks import DockerNetwork
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

from ._config_provider import CONFIG_KEY, MountRemoteType, get_config_content

_logger = logging.getLogger(__name__)


_MAX_WAIT_RC_HTTP_INTERFACE_READY: Final[timedelta] = timedelta(seconds=10)
_DEFAULT_UPDATE_INTERVAL: Final[timedelta] = timedelta(seconds=1)
_DEFAULT_R_CLONE_CLIENT_REQUEST_TIMEOUT: Final[timedelta] = timedelta(seconds=5)

_DEFAULT_MOUNT_ACTIVITY_UPDATE_INTERVAL: Final[timedelta] = timedelta(seconds=5)

_DOCKER_PREFIX_MOUNT: Final[str] = "rcm"

_NOT_FOUND: Final[int] = 404

type MountId = str


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


def _get_self_container_id() -> str:
    # in docker the hostname is the container id
    return os.environ["HOSTNAME"]


class GetBindPathProtocol(Protocol):
    async def __call__(self, path: Path) -> dict: ...


class ContainerManager:
    def __init__(
        self,
        node_id: NodeID,
        r_clone_version: str,
        remote_control_port: PortInt,
        local_mount_path: Path,
        index: NonNegativeInt,
        r_clone_config_content: str,
        remote_path: str,
        vfs_cache_path: Path,
        rc_user: str,
        rc_password: str,
        *,
        handler_get_bind_path: GetBindPathProtocol,
    ) -> None:
        self.node_id = node_id
        self.r_clone_version = r_clone_version
        self.remote_control_port = remote_control_port
        self.local_mount_path = local_mount_path
        self.index = index
        self.r_clone_config_content = r_clone_config_content
        self.handler_get_bind_path = handler_get_bind_path

        self.command = _get_rclone_mount_command(
            r_clone_config_content=r_clone_config_content,
            remote_path=remote_path,
            local_mount_path=self.local_mount_path,
            vfs_cache_path=vfs_cache_path,
            rc_addr=f"0.0.0.0:{remote_control_port}",
            rc_user=rc_user,
            rc_password=rc_password,
        )

        self._cleanup_stack = AsyncExitStack()
        self._client: aiodocker.Docker | None = None

        self._r_clone_container: DockerContainer | None = None
        self._r_clone_network: DockerNetwork | None = None

    @cached_property
    def r_clone_container_name(self) -> str:
        mount_id = _get_mount_id(self.local_mount_path, self.index)
        return f"{_DOCKER_PREFIX_MOUNT}-c-{self.node_id}{mount_id}"[:63]

    @cached_property
    def _r_clone_network_name(self) -> str:
        mount_id = _get_mount_id(self.local_mount_path, self.index)
        return f"{_DOCKER_PREFIX_MOUNT}-c-{self.node_id}{mount_id}"[:63]

    @property
    def _aiodocker_client(self) -> aiodocker.Docker:
        assert self._client is not None  # nosec
        return self._client

    async def start(self):
        self._client = await self._cleanup_stack.enter_async_context(aiodocker.Docker())
        # TODO: toss away docker session when done with it do not maintain object in memory to avoid issues
        # better more robust way of doing it

        try:
            existing_container = await self._aiodocker_client.containers.get(
                self.r_clone_container_name
            )
            await existing_container.delete(force=True)
        except aiodocker.exceptions.DockerError as e:
            if e.status != _NOT_FOUND:
                raise

        try:
            existing_network = DockerNetwork(
                self._aiodocker_client, self._r_clone_network_name
            )
            await existing_network.show()
            await existing_network.delete()
        except aiodocker.exceptions.DockerError as e:
            if e.status != _NOT_FOUND:
                raise

        self._r_clone_network = await self._aiodocker_client.networks.create(
            {"Name": self._r_clone_network_name, "Attachable": True}
        )
        await self._r_clone_network.connect({"Container": _get_self_container_id()})

        # create rclone container attached to the network
        self._r_clone_container = await self._aiodocker_client.containers.run(
            config={
                "Image": f"rclone/rclone:{self.r_clone_version}",
                "Entrypoint": [
                    "/bin/sh",
                    "-c",
                    f"{self.command} && sleep 100000 || sleep 100000000 ",
                ],
                "ExposedPorts": {f"{self.remote_control_port}/tcp": {}},
                "HostConfig": {
                    "NetworkMode": self._r_clone_network_name,
                    "Binds": [],
                    # TODO: mount the VFS cache directory somewhere to have better performance
                    "Mounts": [await self.handler_get_bind_path(self.local_mount_path)],
                    "Devices": [
                        {
                            "PathOnHost": "/dev/fuse",
                            "PathInContainer": "/dev/fuse",
                            "CgroupPermissions": "rwm",
                        }
                    ],
                    "CapAdd": ["SYS_ADMIN"],
                    "SecurityOpt": ["apparmor:unconfined", "seccomp:unconfined"],
                },
            },
            name=self.r_clone_container_name,
        )
        container_inspect = await self._r_clone_container.show()
        _logger.debug(
            "Started rclone mount container '%s' with command='%s' (inspect=%s)",
            self.r_clone_container_name,
            self.command,
            container_inspect,
        )

    async def stop(self):
        assert self._r_clone_container is not None  # nosec
        assert self._r_clone_network is not None  # nosec

        await self._r_clone_container.stop()

        await self._r_clone_network.disconnect({"Container": _get_self_container_id()})
        await self._r_clone_network.delete()

        await self._r_clone_container.delete()

        await self._cleanup_stack.aclose()


def _get_mount_id(local_mount_path: Path, index: NonNegativeInt) -> MountId:
    # reversing string to avoid collisions
    return f"{index}{local_mount_path}".replace("/", "_")[::-1]


_COMMAND_TEMPLATE: Final[str] = dedent(
    """
cat <<EOF > /tmp/rclone.conf
{r_clone_config_content}
EOF

{r_clone_command}
"""
)


def _get_rclone_mount_command(
    r_clone_config_content: str,
    remote_path: StorageFileID,
    local_mount_path: Path,
    vfs_cache_path: Path,
    rc_addr: str,
    rc_user: str,
    rc_password: str,
) -> str:
    # jupyter gid and uid form the user inside
    uid = 1000
    gid = 100
    escaped_remote_path = f"{remote_path}".lstrip("/")
    command_array: list[str] = [
        "rclone",
        "--config",
        "/tmp/rclone.conf",  # noqa: S108
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
        "--allow-other",
        "--uid",
        f"{uid}",
        "--gid",
        f"{gid}",
    ]
    r_clone_command = " ".join(command_array)

    return _COMMAND_TEMPLATE.format(
        r_clone_config_content=r_clone_config_content,
        r_clone_command=r_clone_command,
    )


class MountActivity(BaseModel):
    transferring: dict[str, ProgressReport]
    queued: list[str]


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

    async def _monitor(self) -> None:
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
        vfs_cache_path: Path,
        handler_get_bind_path: GetBindPathProtocol,
        mount_activity_update_interval: timedelta = _DEFAULT_MOUNT_ACTIVITY_UPDATE_INTERVAL,
    ) -> None:
        self.node_id = node_id
        self.r_clone_settings = r_clone_settings
        self.mount_type = remote_type
        self.rc_port = rc_port
        self.remote_path = remote_path
        self.local_mount_path = local_mount_path
        self.index = index
        self.vfs_cache_path = vfs_cache_path
        self.rc_user = f"{uuid4()}"
        self.rc_password = f"{uuid4()}"
        self.handler_get_bind_path = handler_get_bind_path

        self._last_mount_activity: MountActivity | None = None
        self._last_mount_activity_update: datetime = datetime.fromtimestamp(0, UTC)
        self._mount_activity_update_interval = mount_activity_update_interval

        # used internally to handle the mount command
        self._container_manager: ContainerManager | None = None
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

            # NOTE: this could also be useful if pushed to the UI
            _logger.info(
                "Activity for '%s': %s",
                self.local_mount_path,
                self._last_mount_activity,
            )

    async def teardown(self) -> None:
        await self.stop_mount()

    async def start_mount(self) -> None:
        if self._container_manager is not None:
            raise _ContainerAlreadyStartedError(
                container=self._container_manager.r_clone_container_name,
                command=self._container_manager.command,
            )

        r_clone_config_content = get_config_content(
            self.r_clone_settings, self.mount_type
        )

        if self.r_clone_settings.R_CLONE_MOUNT_SETTINGS.R_CLONE_VERSION is None:
            msg = "R_CLONE_VERSION setting is not set"
            raise RuntimeError(msg)

        self._container_manager = ContainerManager(
            node_id=self.node_id,
            r_clone_version=self.r_clone_settings.R_CLONE_MOUNT_SETTINGS.R_CLONE_VERSION,
            remote_control_port=self.rc_port,
            local_mount_path=self.local_mount_path,
            index=self.index,
            r_clone_config_content=r_clone_config_content,
            remote_path=f"{self.r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME}/{self.remote_path}",
            vfs_cache_path=self.vfs_cache_path,
            rc_user=self.rc_user,
            rc_password=self.rc_password,
            handler_get_bind_path=self.handler_get_bind_path,
        )

        self._rc_interface: RCloneRCInterfaceClient | None = RCloneRCInterfaceClient(
            remote_control_port=self.rc_port,
            r_clone_mount_settings=self.r_clone_settings.R_CLONE_MOUNT_SETTINGS,
            remote_control_host=self._container_manager.r_clone_container_name,
            rc_user=self.rc_user,
            rc_password=self.rc_password,
            update_handler=self._progress_handler,
        )

        await self._container_manager.start()
        await self.rc_interface.setup()
        await self.rc_interface.wait_for_interface_to_be_ready()

    async def stop_mount(self) -> None:
        if self._container_manager is None:
            return

        await self.rc_interface.wait_for_all_transfers_to_complete()
        await self.rc_interface.teardown()
        self._rc_interface = None

        await self._container_manager.stop()
        self._container_manager = None

        await self._cleanup_stack.aclose()


class RCloneMountManager:
    def __init__(self, r_clone_settings: RCloneSettings) -> None:
        self.r_clone_settings = r_clone_settings
        self._common_vfs_cache_path = (
            self.r_clone_settings.R_CLONE_MOUNT_SETTINGS.R_CLONE_MOUNT_VFS_CACHE_PATH
        )

        self._started_mounts: dict[MountId, TrackedMount] = {}

    async def start_mount(
        self,
        node_id: NodeID,
        remote_type: MountRemoteType,
        remote_path: StorageFileID,
        local_mount_path: Path,
        index: NonNegativeInt,
        handler_get_bind_path: GetBindPathProtocol,
        vfs_cache_path_overwrite: Path | None = None,
    ) -> None:
        try:
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

                vfs_cache_path = (
                    vfs_cache_path_overwrite or self._common_vfs_cache_path
                ) / mount_id
                vfs_cache_path.mkdir(parents=True, exist_ok=True)

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
                    vfs_cache_path=vfs_cache_path,
                    handler_get_bind_path=handler_get_bind_path,
                )
                await tracked_mount.start_mount()

                self._started_mounts[mount_id] = tracked_mount
        except Exception:
            _logger.exception("SOMETHING WENT WRONG WAITING HERE FOR DEBUGGING")
            await asyncio.sleep(100000)  # let rclone write logs

            raise

    async def wait_for_transfers_to_complete(
        self, local_mount_path: Path, index: NonNegativeInt
    ) -> None:
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
        mount_id = _get_mount_id(local_mount_path, index)
        return mount_id in self._started_mounts

    async def stop_mount(self, local_mount_path: Path, index: NonNegativeInt) -> None:
        with log_context(
            _logger, logging.INFO, f"unmounting {local_mount_path=}", log_duration=True
        ):
            mount_id = _get_mount_id(local_mount_path, index)
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
