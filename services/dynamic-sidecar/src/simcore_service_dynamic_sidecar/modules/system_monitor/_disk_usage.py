import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from functools import cached_property
from pathlib import Path
from typing import Final

import psutil
from fastapi import FastAPI
from models_library.api_schemas_dynamic_sidecar.telemetry import (
    DiskUsage,
    MountPathCategory,
)
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.logging_utils import log_context
from servicelib.utils import logged_gather

from ...core.settings import ApplicationSettings
from ..mounted_fs import MountedVolumes
from ..notifications import publish_disk_usage

_NODE_FILE_SYSTEM_PATH: Final[Path] = Path("/")


_logger = logging.getLogger(__name__)


_SUPPORTED_ITEMS: Final[set[str]] = {
    MountPathCategory.HOST,
    MountPathCategory.STATES_VOLUMES,
}


async def get_usage(path: Path) -> DiskUsage:
    usage = await asyncio.get_event_loop().run_in_executor(
        None, psutil.disk_usage, f"{path}"
    )
    return DiskUsage.from_ps_util_disk_usage(usage)


def get_relative_path(path: Path, dy_volumes_mount_dir: Path) -> Path:
    try:
        return path.relative_to(dy_volumes_mount_dir)
    except ValueError:
        return path


def _get_normalized_folder_name(path: Path) -> str:
    return f"{path}".replace("/", "_")


@dataclass
class DiskUsageMonitor:
    app: FastAPI
    user_id: UserID
    node_id: NodeID
    interval: timedelta
    monitored_paths: dict[MountPathCategory, set[Path]]

    dy_volumes_mount_dir: Path
    _monitor_task: asyncio.Task | None = None

    # tracked disk usage
    _last_usage: dict[MountPathCategory, DiskUsage] = field(default_factory=dict)
    _usage_overwrite: dict[str, DiskUsage] = field(
        default_factory=dict,
        metadata={
            "description": (
                "third party services can update the disk usage for certain paths "
                "monitored by the dynamic-sidecar. This is the case for the efs-guardian."
            )
        },
    )

    @cached_property
    def _monitored_paths_set(self) -> set[Path]:
        return set.union(*self.monitored_paths.values())

    @cached_property
    def _normalized_monitored_paths(self) -> dict[MountPathCategory, set[str]]:
        """
        Transforms Path -> str form `/tmp/.some_file/here` -> `_tmp_.some_file_here`.
        This a one way transformation used to uniquely identify volume mounts inside
        by the dynamic-sidecar. These are also used by the efs-guardian.
        """
        return {
            k: {
                _get_normalized_folder_name(
                    get_relative_path(p, self.dy_volumes_mount_dir)
                )
                for p in paths
            }
            for k, paths in self.monitored_paths.items()
        }

    async def _get_measured_disk_usage(self) -> list[DiskUsage]:
        return await logged_gather(
            *[get_usage(monitored_path) for monitored_path in self._monitored_paths_set]
        )

    def _get_local_disk_usage(
        self, measured_disk_usage: list[DiskUsage]
    ) -> dict[str, DiskUsage]:
        return {
            _get_normalized_folder_name(
                get_relative_path(p, self.dy_volumes_mount_dir)
            ): u
            for p, u in zip(self._monitored_paths_set, measured_disk_usage, strict=True)
        }

    def _replace_incoming_usage(
        self, normalized_disk_usage: dict[str, DiskUsage]
    ) -> None:
        """overwrites local disk usage with incoming usage from egs-guardian"""
        for key, overwrite_usage in self._usage_overwrite.items():
            normalized_disk_usage[key] = overwrite_usage  # noqa: PERF403

    @staticmethod
    def _get_grouped_usage_to_folder_names(
        local_disk_usage: dict[str, DiskUsage]
    ) -> dict[DiskUsage, set[str]]:
        """Groups all paths that have the same metrics together"""
        usage_to_folder_names: dict[DiskUsage, set[str]] = {}
        for folder_name, disk_usage in local_disk_usage.items():
            if disk_usage not in usage_to_folder_names:
                usage_to_folder_names[disk_usage] = set()

            usage_to_folder_names[disk_usage].add(folder_name)
        return usage_to_folder_names

    async def _publish_disk_usage(self, usage: dict[MountPathCategory, DiskUsage]):
        await publish_disk_usage(
            self.app, user_id=self.user_id, node_id=self.node_id, usage=usage
        )

    async def _monitor(self) -> None:
        measured_disk_usage = await self._get_measured_disk_usage()

        local_disk_usage = self._get_local_disk_usage(measured_disk_usage)

        self._replace_incoming_usage(local_disk_usage)

        usage_to_folder_names = self._get_grouped_usage_to_folder_names(
            local_disk_usage
        )

        # compute new version of DiskUsage for FE, only 1 label for each unique disk usage entry
        usage: dict[MountPathCategory, DiskUsage] = {}

        normalized_paths = self._normalized_monitored_paths

        for disk_usage, folder_names in usage_to_folder_names.items():
            for category in [
                MountPathCategory.HOST,
                MountPathCategory.STATES_VOLUMES,
                MountPathCategory.INPUTS_VOLUMES,
                MountPathCategory.OUTPUTS_VOLUMES,
            ]:
                if folder_names.intersection(normalized_paths[category]):
                    usage[category] = disk_usage
                    break
            else:
                msg = f"Could not assign {disk_usage=} for {folder_names=}"
                raise RuntimeError(msg)

        supported_usage = {k: v for k, v in usage.items() if k in _SUPPORTED_ITEMS}

        # notify only when usage changes
        if self._last_usage != supported_usage:
            await self._publish_disk_usage(supported_usage)
            self._last_usage = supported_usage

    async def setup(self) -> None:
        self._monitor_task = start_periodic_task(
            self._monitor, interval=self.interval, task_name="monitor_disk_usage"
        )

    async def shutdown(self) -> None:
        if self._monitor_task:
            await stop_periodic_task(self._monitor_task)

    def set_disk_usage_for_path(self, overwrite_usage: dict[str, DiskUsage]) -> None:
        """
        efs-guardian manages disk quotas since the underlying FS has no support for them.
        the dynamic-sidecar will use this information to provide correct quotas for the
        volumes managed by the efs-guardian
        """
        self._usage_overwrite = overwrite_usage


def _get_monitored_paths(app: FastAPI) -> dict[MountPathCategory, set[Path]]:
    mounted_volumes: MountedVolumes = app.state.mounted_volumes
    return {
        MountPathCategory.HOST: {_NODE_FILE_SYSTEM_PATH},
        MountPathCategory.INPUTS_VOLUMES: {mounted_volumes.disk_inputs_path},
        MountPathCategory.OUTPUTS_VOLUMES: {mounted_volumes.disk_outputs_path},
        MountPathCategory.STATES_VOLUMES: set(mounted_volumes.disk_state_paths_iter()),
    }


def get_disk_usage_monitor(app: FastAPI) -> DiskUsageMonitor:
    disk_usage_monitor: DiskUsageMonitor = app.state.disk_usage_monitor
    return disk_usage_monitor


def setup_disk_usage(app: FastAPI) -> None:
    async def on_startup() -> None:
        with log_context(_logger, logging.INFO, "setup disk monitor"):
            settings: ApplicationSettings = app.state.settings

            app.state.disk_usage_monitor = disk_usage_monitor = DiskUsageMonitor(
                app,
                user_id=settings.DY_SIDECAR_USER_ID,
                node_id=settings.DY_SIDECAR_NODE_ID,
                interval=settings.DYNAMIC_SIDECAR_TELEMETRY_DISK_USAGE_MONITOR_INTERVAL,
                monitored_paths=_get_monitored_paths(app),
                dy_volumes_mount_dir=settings.DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR,
            )
            await disk_usage_monitor.setup()

    async def on_shutdown() -> None:
        with log_context(_logger, logging.INFO, "shutdown disk monitor"):
            if disk_usage_monitor := getattr(  # noqa: B009
                app.state, "disk_usage_monitor"
            ):
                await disk_usage_monitor.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
