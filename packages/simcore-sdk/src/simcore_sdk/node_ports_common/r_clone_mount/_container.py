import asyncio
import logging
from datetime import timedelta
from functools import cached_property
from pathlib import Path
from textwrap import dedent
from typing import Final

from httpx import AsyncClient, HTTPError
from models_library.basic_types import PortInt
from models_library.progress_bar import ProgressReport
from models_library.projects_nodes_io import NodeID, StorageFileID
from pydantic import NonNegativeInt
from settings_library.r_clone import DEFAULT_VFS_CACHE_PATH, TPSLIMIT, RCloneSettings, SimcoreSDKMountSettings
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

from ..r_clone_utils import overwrite_command
from . import _docker_utils
from ._config_provider import CONFIG_KEY
from ._errors import (
    WaitingForQueueToBeEmptyError,
    WaitingForTransfersToCompleteError,
)
from ._models import DelegateInterface, MountActivity
from ._utils import get_mount_id

_logger = logging.getLogger(__name__)


_MAX_WAIT_RC_HTTP_INTERFACE_READY: Final[timedelta] = timedelta(seconds=10)
_DEFAULT_UPDATE_INTERVAL: Final[timedelta] = timedelta(seconds=1)
_DEFAULT_R_CLONE_CLIENT_REQUEST_TIMEOUT: Final[timedelta] = timedelta(seconds=20)


_DOCKER_PREFIX_MOUNT: Final[str] = "rcm"


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
    mount_settings: SimcoreSDKMountSettings,
    r_clone_config_content: str,
    remote_path: StorageFileID,
    local_mount_path: Path,
    rc_port: PortInt,
    rc_user: str,
    rc_password: str,
) -> str:
    escaped_remote_path = f"{remote_path}".lstrip("/")

    command_parts = [
        "rclone",
        "--config",
        f"{mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_CONFIG_FILE_PATH}",
        ("-vv" if mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_SHOW_DEBUG_LOGS else ""),
        "mount",
        f"{CONFIG_KEY}:{escaped_remote_path}",
        f"{local_mount_path}",
        # VFS
        "--vfs-cache-mode",
        "full",
        "--vfs-read-ahead",
        "16M",
        "--vfs-cache-max-size",
        mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_VFS_CACHE_SIZE,
        "--vfs-cache-min-free-space",
        "5G",
        "--vfs-cache-poll-interval",
        "1m",
        "--write-back-cache",
        "--vfs-write-back",
        "10s",
        "--cache-dir",
        f"{DEFAULT_VFS_CACHE_PATH}",
        "--dir-cache-time",
        "10m",
        "--attr-timeout",
        "1m",
        "--tpslimit",
        f"{TPSLIMIT}",
        "--tpslimit-burst",
        f"{TPSLIMIT * 2}",
        "--no-modtime",
        "--max-buffer-memory",
        "16M",
        # TRANSFERS
        "--retries",
        "3",
        "--retries-sleep",
        "30s",
        "--transfers",
        "15",
        "--buffer-size",
        "16M",
        "--checkers",
        "8",
        "--s3-upload-concurrency",
        "5",
        "--s3-chunk-size",
        "16M",
        "--order-by",
        "size,mixed",
        # REMOTE CONTROL
        "--rc",
        f"--rc-addr=0.0.0.0:{rc_port}",
        "--rc-enable-metrics",
        f"--rc-user='{rc_user}'",
        f"--rc-pass='{rc_password}'",
        "--allow-non-empty",
        "--allow-other",
    ]
    r_clone_command = " ".join(
        overwrite_command(
            command_parts,
            edit=mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_COMMAND_EDIT_ENTRIES,
            remove=mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_COMMAND_REMOVE_ENTRIES,
        )
    )
    return _R_CLONE_MOUNT_TEMPLATE.format(
        r_clone_config_path=mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_CONFIG_FILE_PATH,
        r_clone_config_content=r_clone_config_content,
        r_clone_command=r_clone_command,
        local_mount_path=local_mount_path,
    )


class ContainerManager:  # pylint:disable=too-many-instance-attributes
    def __init__(  # pylint:disable=too-many-arguments
        self,
        r_clone_settings: RCloneSettings,
        node_id: NodeID,
        rc_port: PortInt,
        local_mount_path: Path,
        index: NonNegativeInt,
        r_clone_config_content: str,
        remote_path: str,
        rc_user: str,
        rc_password: str,
        *,
        delegate: DelegateInterface,
    ) -> None:
        self.r_clone_settings = r_clone_settings
        self.node_id = node_id
        self.rc_port = rc_port
        self.local_mount_path = local_mount_path
        self.index = index
        self.r_clone_config_content = r_clone_config_content
        self.remote_path = remote_path
        self.rc_user = rc_user
        self.rc_password = rc_password

        self.delegate = delegate

    @cached_property
    def r_clone_container_name(self) -> str:
        mount_id = get_mount_id(self.local_mount_path, self.index)
        return f"{_DOCKER_PREFIX_MOUNT}-c-{self.node_id}{mount_id}"[:63]

    @cached_property
    def _r_clone_network_name(self) -> str:
        mount_id = get_mount_id(self.local_mount_path, self.index)
        return f"{_DOCKER_PREFIX_MOUNT}-c-{self.node_id}{mount_id}"[:63]

    async def create(self):
        # ensure nothing was left from previous runs
        await _docker_utils.remove_container_if_exists(self.delegate, self.r_clone_container_name)
        await _docker_utils.remove_network_if_exists(self.delegate, self.r_clone_container_name)

        # create network + container and connect to current container
        await _docker_utils.create_network_and_connect_current_container(self.delegate, self._r_clone_network_name)

        assert self.r_clone_settings.R_CLONE_VERSION is not None  # nosec
        mount_settings = self.r_clone_settings.R_CLONE_SIMCORE_SDK_MOUNT_SETTINGS
        await _docker_utils.create_r_clone_container(
            self.delegate,
            self.r_clone_container_name,
            command=_get_rclone_mount_command(
                mount_settings=mount_settings,
                r_clone_config_content=self.r_clone_config_content,
                remote_path=self.remote_path,
                local_mount_path=self.local_mount_path,
                rc_port=self.rc_port,
                rc_user=self.rc_user,
                rc_password=self.rc_password,
            ),
            r_clone_version=self.r_clone_settings.R_CLONE_VERSION,
            rc_port=self.rc_port,
            r_clone_network_name=self._r_clone_network_name,
            local_mount_path=self.local_mount_path,
            memory_limit=mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_MEMORY_LIMIT,
            nano_cpus=mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_NANO_CPUS,
        )

    async def remove(self):
        await _docker_utils.remove_container_if_exists(self.delegate, self.r_clone_container_name)
        await _docker_utils.remove_network_if_exists(self.delegate, self.r_clone_container_name)


class RemoteControlHttpClient:
    def __init__(
        self,
        rc_host: str,
        rc_port: PortInt,
        rc_user: str,
        rc_password: str,
        *,
        transfers_completed_timeout: timedelta,
        update_interval: timedelta = _DEFAULT_UPDATE_INTERVAL,
        r_clone_client_timeout: timedelta = _DEFAULT_R_CLONE_CLIENT_REQUEST_TIMEOUT,
    ) -> None:
        self.transfers_completed_timeout = transfers_completed_timeout
        self._update_interval_seconds = update_interval.total_seconds()
        self._r_clone_client_timeout = r_clone_client_timeout

        self.rc_host = rc_host
        self.rc_port = rc_port
        self._auth = (rc_user, rc_password)

    @property
    def _base_url(self) -> str:
        return f"http://{self.rc_host}:{self.rc_port}"

    async def _request(self, method: str, path: str) -> dict:
        request_url = f"{self._base_url}/{path}"
        _logger.debug("Sending '%s %s' request", method, request_url)

        async with AsyncClient(timeout=self._r_clone_client_timeout.total_seconds()) as client:
            response = await client.request(method, request_url, auth=self._auth)
            response.raise_for_status()
            dict_response: dict = response.json()
            return dict_response

    async def _post_core_stats(self) -> dict:
        return await self._request("POST", "core/stats")

    async def _post_vfs_queue(self) -> dict:
        return await self._request("POST", "vfs/queue")

    async def _rc_noop(self) -> dict:
        return await self._request("POST", "rc/noop")

    async def get_mount_activity(self) -> MountActivity:
        core_stats, vfs_queue = await asyncio.gather(self._post_core_stats(), self._post_vfs_queue())

        return MountActivity(
            transferring=(
                {
                    x["name"]: ProgressReport(actual_value=(x["percentage"] / 100 if "percentage" in x else 0.0))
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
        await self._post_vfs_queue()

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
            stop=stop_after_delay(self.transfers_completed_timeout.total_seconds()),
            reraise=True,
            retry=retry_if_exception_type((WaitingForQueueToBeEmptyError, WaitingForTransfersToCompleteError)),
            before_sleep=before_sleep_log(_logger, logging.WARNING),
        )
        async def _() -> None:
            core_stats, vfs_queue = await asyncio.gather(self._post_core_stats(), self._post_vfs_queue())

            if core_stats["transfers"] != core_stats["totalTransfers"] or "transferring" in core_stats:
                raise WaitingForTransfersToCompleteError

            queue = vfs_queue["queue"]
            if len(queue) != 0:
                raise WaitingForQueueToBeEmptyError(queue=queue)

        await _()
