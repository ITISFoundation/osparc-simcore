# here services can be registered to be monitored for their
# current status. Events are triggered base on what happens
# Monitoring for:
# - servie available
#
#
# Handlers to subscribe to this thing

from asyncio import Lock, sleep
from typing import Dict, List
from pydantic import BaseModel, Field
from enum import Enum
import logging

from .. import config

logger = logging.getLogger(__name__)

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
        ...,
        default=False,
        scription="infroms if the web API on the service-sidecar is responding",
    )

    @classmethod
    def make_empty(cls):
        return cls()


class MonitorData(BaseModel):
    """Stores information on the current status of service-sidecar"""

    service_sidecar_status: ServiceSidecar = Field(
        ServiceSidecar.make_empty(),
        description="stores information fetched from the service-sidecar",
    )

    started_containers: List[StartedContainer] = Field(
        [],
        scription="list of container's monitor data spaned from the service-sidecar",
    )

    @classmethod
    def make_empty(cls):
        return cls()


class ServiceSidecarsMonitor:
    __slots__ = ("to_monitor", "_lock", "_keep_running")

    def __init__(self):
        self.to_monitor: Dict[str, MonitorData] = dict()
        self._lock: Lock = Lock()
        self._keep_running: bool = False

    async def add_service_to_monitor(self, service_name: str) -> None:
        # invoked when the service is started
        async with self._lock:
            if service_name in self.to_monitor:
                return
            self.to_monitor[service_name] = MonitorData.make_empty()

    async def remove_service_from_monitor(self, service_name: str) -> None:
        # invoked when the service is removed
        async with self._lock:
            if service_name in self.to_monitor:
                del self.to_monitor[service_name]

    async def get_service_status(self, service_name: str) -> MonitorData:
        # it is ok to error out if requesting a service which dose not exists, this should not happen
        async with self._lock:
            return self.to_monitor[service_name]

    # start monitor - tied to the lifecycle of the app
    # stop monitor

    async def _run_monitor(self) -> None:
        while self._keep_running:
            # make sure access to the dict is locked while the monitoring cycle is running
            async with self._lock:
                await self._runner()

            sleep(config.SERVICE_SIDECAR_MONITOR_INTERVAL_SECONDS)

    async def _runner(self):
        """This code runs under the lock"""
        # spawn prcesses in parallel, use dedicated ClientSession just for this to monitor the requests to the service sidecars
        # merge results back to the dictionary
        logger.info("Doing some monitorung here")
