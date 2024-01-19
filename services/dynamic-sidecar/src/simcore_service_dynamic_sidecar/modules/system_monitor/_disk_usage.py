import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

import psutil
from fastapi import FastAPI
from models_library.api_schemas_dynamic_sidecar.telemetry import DiskUsage
from models_library.projects_nodes_io import NodeID
from models_library.users import GroupID
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.logging_utils import log_context
from servicelib.utils import logged_gather

from ...core.settings import ApplicationSettings
from ..mounted_fs import MountedVolumes
from ._notifier import publish_disk_usage

_logger = logging.getLogger(__name__)


async def get_usage(path: Path) -> DiskUsage:
    usage = await asyncio.get_event_loop().run_in_executor(
        None, psutil.disk_usage, f"{path}"
    )
    return DiskUsage.parse_obj(usage._asdict())


@dataclass
class DiskUsageMonitor:
    app: FastAPI
    primary_group_id: GroupID
    node_id: NodeID
    interval: timedelta
    monitored_paths: list[Path]
    _monitor_task: asyncio.Task | None = None
    _last_usage: dict[Path, DiskUsage] = field(default_factory=dict)

    async def _publish_disk_usage(self, usage: dict[Path, DiskUsage]):
        await publish_disk_usage(
            self.app,
            primary_group_id=self.primary_group_id,
            node_id=self.node_id,
            usage=usage,
        )

    async def _monitor(self) -> None:
        disk_usages: list[DiskUsage] = await logged_gather(
            *[get_usage(monitored_path) for monitored_path in self.monitored_paths]
        )

        usage: dict[Path, DiskUsage] = dict(
            zip(self.monitored_paths, disk_usages, strict=True)
        )

        # notify only when changed
        if self._last_usage != usage:
            await self._publish_disk_usage(usage)
            self._last_usage = usage

    async def setup(self) -> None:
        self._monitor_task = start_periodic_task(
            self._monitor, interval=self.interval, task_name="monitor_disk_usage"
        )

    async def shutdown(self) -> None:
        if self._monitor_task:
            await stop_periodic_task(self._monitor_task)


def _get_monitored_paths(app: FastAPI) -> list[Path]:
    mounted_volumes: MountedVolumes = app.state.mounted_volumes
    return [
        Path("/"),  # root file system and /tmp usage mainly
        *list(mounted_volumes.all_disk_paths_iter()),
    ]


def setup_disk_usage(app: FastAPI) -> None:
    async def on_startup() -> None:
        with log_context(_logger, logging.INFO, "setup disk monitor"):
            settings: ApplicationSettings = app.state.settings

            app.state.disk_usage_monitor = disk_usage_monitor = DiskUsageMonitor(
                app,
                primary_group_id=settings.DY_SIDECAR_PRIMARY_GROUP_ID,
                node_id=settings.DY_SIDECAR_NODE_ID,
                interval=settings.DYNAMIC_SIDECAR_TELEMETRY_DISK_USAGE_MONITOR_INTERVAL,
                monitored_paths=_get_monitored_paths(app),
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
