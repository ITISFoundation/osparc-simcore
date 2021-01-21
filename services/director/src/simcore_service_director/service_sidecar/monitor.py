# here services can be registered to be monitored for their
# current status. Events are triggered base on what happens
# Monitoring for:
# - servie available
#
#
# Handlers to subscribe to this thing

import asyncio
from aiohttp.web import Application
from asyncio import Lock, sleep
from typing import Dict, List
from pydantic import BaseModel, Field
from enum import Enum
import logging

from .config import get_settings
from .exceptions import ServiceSidecarError

logger = logging.getLogger(__name__)

MONITOR_KEY = f"{__name__}.ServiceSidecarsMonitor"

# think about how to recover a reply when status changed here? or something like that when starting a service


class DockerStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    REMOVING = "removing"
    EXITED = "exited"
    DEAD = "dead"


class StartedContainer(BaseModel):
    status: DockerStatus = Field(
        ...,
        scription="status of the underlying container",
    )


class ServiceSidecar(BaseModel):
    is_available: bool = Field(
        False,
        scription="infroms if the web API on the service-sidecar is responding",
    )

    @classmethod
    def make_empty(cls):
        return cls()


class MonitorData(BaseModel):
    """Stores information on the current status of service-sidecar"""

    service_name: str = Field(
        ..., description="Name of the current sidecar-service being monitored"
    )

    service_sidecar_status: ServiceSidecar = Field(
        ServiceSidecar.make_empty(),
        description="stores information fetched from the service-sidecar",
    )

    started_containers: List[StartedContainer] = Field(
        [],
        scription="list of container's monitor data spaned from the service-sidecar",
    )

    @classmethod
    def assemble(cls, service_name: str):
        return cls(service_name=service_name)


def apply_monitoring(input_monitor_data: MonitorData) -> MonitorData:
    # should do something and return an updated instance or a new one
    # there is no difference
    logger.debug("No transformation applied to %s", input_monitor_data)
    return input_monitor_data


class ServiceSidecarsMonitor:
    __slots__ = (
        "_to_monitor",
        "_lock",
        "_keep_running",
        "_inverse_search_mapping",
        "_app",
    )

    def __init__(self, app: Application):
        self._to_monitor: Dict[str, MonitorData] = dict()
        self._lock: Lock = Lock()
        self._keep_running: bool = False
        self._inverse_search_mapping: Dict[str, str] = dict()
        self._app: Application = app

    async def add_service_to_monitor(self, service_name: str, node_uuid: str) -> None:
        """Invoked before the service is started

        Because we do not have all items require to compute the service_name the node_uuid is used to
        keep track of the service for faster searches.
        """
        async with self._lock:
            if service_name in self._to_monitor:
                return
            if node_uuid in self._inverse_search_mapping:
                raise ServiceSidecarError(
                    "node_uuids at a global level collided. A running "
                    f"service for node {node_uuid} already exists. Please checkout "
                    "other projects which may have this issue."
                )
            self._inverse_search_mapping[node_uuid] = service_name
            self._to_monitor[service_name] = MonitorData.assemble(service_name)
            logger.debug("Added service '%s' to monitor", service_name)

    async def remove_service_from_monitor(self, node_uuid) -> None:
        # invoked before the service is removed
        # TODO: fetch service_name from somewhere we must keep a mapping of them
        async with self._lock:
            if node_uuid not in self._inverse_search_mapping:
                return

            service_name = self._inverse_search_mapping[node_uuid]
            if service_name in self._to_monitor:
                logger.debug("Removed service '%s' from monitoring", service_name)
                del self._to_monitor[service_name]

    async def get_service_status(self, service_name: str) -> MonitorData:
        # it is ok to error out if requesting a service which dose not exists, this should not happen
        async with self._lock:
            return self._to_monitor[service_name]

    # start monitor - tied to the lifecycle of the app
    # stop monitor

    async def _runner(self):
        """This code runs under a lock and can safely change the Monitor data of all entries"""
        logger.info("Doing some monitorung here")

        for service_name in self._to_monitor:
            monitor_data: MonitorData = self._to_monitor[service_name]

            try:
                self._to_monitor[service_name] = apply_monitoring(monitor_data)
            except asyncio.CancelledError:
                raise
            except Exception:   #pylint: disable=broad-except
                logger.exception(
                    "Something went wrong while monitoring service %s", service_name
                )

    async def _run_monitor_task(self) -> None:
        service_sidecar_settings = get_settings(self._app)

        while self._keep_running:
            # make sure access to the dict is locked while the monitoring cycle is running
            async with self._lock:
                await self._runner()

            await sleep(service_sidecar_settings.monitor_interval_seconds)

        logger.warning("Monitor was shut down")

    async def start(self):
        # run as a background task
        logging.info("Starting service-sidecar monitor")
        self._keep_running = True
        asyncio.get_event_loop().create_task(self._run_monitor_task())

    async def shutdown(self):
        logging.info("Shutting down service-sidecar monitor")
        self._keep_running = False


def get_monitor(app: Application) -> ServiceSidecarsMonitor:
    return app[MONITOR_KEY]


async def setup_monitor(app: Application):
    app[MONITOR_KEY] = service_sidecars_monitor = ServiceSidecarsMonitor(app)
    await service_sidecars_monitor.start()


async def shutdown_monitor(app: Application):
    service_sidecars_monitor = app[MONITOR_KEY]
    await service_sidecars_monitor.shutdown()