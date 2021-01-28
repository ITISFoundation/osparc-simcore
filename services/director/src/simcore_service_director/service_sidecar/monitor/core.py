# here services can be registered to be monitored for their
# current status. Events are triggered base on what happens
# Monitoring for:
# - servie available
#
#
# Handlers to subscribe to this thing

import asyncio
import logging
from asyncio import Lock, sleep
from typing import Deque, Dict, Tuple

from aiohttp.web import Application
from async_timeout import timeout

from ..config import ServiceSidecarSettings, get_settings
from ..docker_utils import get_service_sidecars_to_monitor
from ..exceptions import ServiceSidecarError
from .handlers import REGISTERED_HANDLERS
from .models import LockWithMonitorData, MonitorData, ServiceSidecarStatus
from .service_sidecar_api import query_service
from .utils import AsyncResourceLock

logger = logging.getLogger(__name__)

MONITOR_KEY = f"{__name__}.ServiceSidecarsMonitor"


async def apply_monitoring(
    app: Application, input_monitor_data: MonitorData
) -> MonitorData:
    """
    fetches status for service and then processes all the registered handlers
    and updates the status back
    """
    service_sidecar_settings: ServiceSidecarSettings = get_settings(app)

    output_monitor_data = input_monitor_data.copy(deep=True)

    # if the service is not OK (for now failing) monitoring will be skipped
    # this will allow others to debug it
    if (
        input_monitor_data.service_sidecar.overall_status.status
        != ServiceSidecarStatus.OK
    ):
        logger.warning(
            "Service %s is failing, skipping monitoring.",
            input_monitor_data.service_name,
        )
        return output_monitor_data

    try:
        with timeout(service_sidecar_settings.max_status_api_duration):
            output_monitor_data = await query_service(app, input_monitor_data)
    except asyncio.TimeoutError:
        output_monitor_data.service_sidecar.is_available = False
        # TODO: maybe push this into the health API to monitor degradation of the services

    for handler in REGISTERED_HANDLERS:
        # the handler will apply changes to the output_monitor_data
        await handler.process(
            app=app, previous=input_monitor_data, current=output_monitor_data
        )

    # check if the status of the services has changed from OK

    if (
        input_monitor_data.service_sidecar.overall_status
        != output_monitor_data.service_sidecar.overall_status
    ):
        # TODO: push this to the UI to display to the user?
        logger.info(
            "Service %s overall status changed to %s",
            output_monitor_data.service_name,
            output_monitor_data.service_sidecar.overall_status,
        )

    return output_monitor_data


class ServiceSidecarsMonitor:
    __slots__ = (
        "_to_monitor",
        "_lock",
        "_keep_running",
        "_inverse_search_mapping",
        "_app",
    )

    def __init__(self, app: Application):
        self._app: Application = app
        self._lock: Lock = Lock()

        self._to_monitor: Dict[str, LockWithMonitorData] = dict()
        self._keep_running: bool = False
        self._inverse_search_mapping: Dict[str, str] = dict()

    async def add_service_to_monitor(
        self,
        service_name: str,
        node_uuid: str,
        hostname: str,
        port: int,
        service_key: str,
        service_tag: str,
        service_published_url: str,
    ) -> None:
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
            self._to_monitor[service_name] = LockWithMonitorData(
                resource_lock=AsyncResourceLock(False),
                monitor_data=MonitorData.assemble(
                    service_name=service_name,
                    hostname=hostname,
                    port=port,
                    service_key=service_key,
                    service_tag=service_tag,
                    service_published_url=service_published_url,
                ),
            )
            logger.debug("Added service '%s' to monitor", service_name)

    async def remove_service_from_monitor(self, node_uuid) -> None:
        # invoked before the service is removed
        async with self._lock:
            if node_uuid not in self._inverse_search_mapping:
                return

            service_name = self._inverse_search_mapping[node_uuid]
            if service_name in self._to_monitor:
                logger.debug("Removed service '%s' from monitoring", service_name)
                del self._to_monitor[service_name]
                del self._inverse_search_mapping[node_uuid]

    async def _runner(self):
        """This code runs under a lock and can safely change the Monitor data of all entries"""
        logger.info("Doing some monitorung here")

        async def monitor_single_service(service_name: str) -> None:
            lock_with_monitor_data: LockWithMonitorData = self._to_monitor[service_name]

            try:
                self._to_monitor[service_name].monitor_data = await apply_monitoring(
                    self._app, lock_with_monitor_data.monitor_data
                )
            except asyncio.CancelledError:
                raise
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    "Something went wrong while monitoring service %s", service_name
                )
            finally:
                # when done, always unlock the resource
                await lock_with_monitor_data.resource_lock.unlock_resource()

        # start monitoring for services which are not currently undergoing
        # a monitoring cycle
        for service_name in self._to_monitor:
            lock_with_monitor_data = self._to_monitor[service_name]
            resource_was_locked = (
                await lock_with_monitor_data.resource_lock.mark_as_locked_if_unlocked()
            )
            if resource_was_locked:
                # fire and forget about the task
                asyncio.get_event_loop().create_task(
                    monitor_single_service(service_name)
                )

    async def _run_monitor_task(self) -> None:
        service_sidecar_settings = get_settings(self._app)

        while self._keep_running:
            # make sure access to the dict is locked while the monitoring cycle is running
            try:
                async with self._lock:
                    await self._runner()

                await sleep(service_sidecar_settings.monitor_interval_seconds)
            except asyncio.CancelledError:
                break

        logger.warning("Monitor was shut down")

    async def start(self):
        # run as a background task
        logging.info("Starting service-sidecar monitor")
        self._keep_running = True
        asyncio.get_event_loop().create_task(self._run_monitor_task())

        # discover all services which were started before and add them to the monitor
        service_sidecar_settings: ServiceSidecarSettings = get_settings(self._app)
        services_to_monitor: Deque[
            Tuple[str, str, str, str, str]
        ] = await get_service_sidecars_to_monitor(service_sidecar_settings)

        logging.info(
            "The following services need to be monitored: %s", services_to_monitor
        )

        for service_to_monitor in services_to_monitor:
            (
                service_name,
                node_uuid,
                service_key,
                service_tag,
                service_published_url,
            ) = service_to_monitor

            await self.add_service_to_monitor(
                service_name=service_name,
                node_uuid=node_uuid,
                hostname=service_name,
                port=service_sidecar_settings.web_service_port,
                service_key=service_key,
                service_tag=service_tag,
                service_published_url=service_published_url,
            )

    async def shutdown(self):
        logging.info("Shutting down service-sidecar monitor")
        self._keep_running = False
        self._inverse_search_mapping = dict()
        self._to_monitor = dict()


def get_monitor(app: Application) -> ServiceSidecarsMonitor:
    return app[MONITOR_KEY]


async def setup_monitor(app: Application):
    app[MONITOR_KEY] = service_sidecars_monitor = ServiceSidecarsMonitor(app)
    await service_sidecars_monitor.start()


async def shutdown_monitor(app: Application):
    service_sidecars_monitor = app[MONITOR_KEY]
    await service_sidecars_monitor.shutdown()
