import asyncio
import logging
import traceback
from asyncio import Lock, Task, sleep
from copy import deepcopy
from typing import Deque, Dict, Optional
from uuid import UUID

from async_timeout import timeout
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID

from ....core.settings import (
    DynamicServicesMonitoringSettings,
    DynamicServicesSettings,
    DynamicSidecarSettings,
)
from ....models.schemas.dynamic_services import (
    AsyncResourceLock,
    DynamicSidecarStatus,
    LockWithMonitorData,
    MonitorData,
    RunningDynamicServiceDetails,
    ServiceLabelsStoredData,
)
from ..client_api import (
    DynamicSidecarClient,
    get_dynamic_sidecar_client,
    update_dynamic_sidecar_health,
)
from ..docker_api import (
    are_all_services_present,
    get_dynamic_sidecar_state,
    get_dynamic_sidecars_to_monitor,
    remove_dynamic_sidecar_network,
    remove_dynamic_sidecar_stack,
)
from ..docker_states import ServiceState, extract_containers_minimim_statuses
from ..errors import DynamicSidecarError, DynamicSidecarNotFoundError
from .events import REGISTERED_EVENTS

logger = logging.getLogger(__name__)


async def _apply_monitoring(
    app: FastAPI, monitor: "DynamicSidecarsMonitor", monitor_data: MonitorData
) -> None:
    """
    fetches status for service and then processes all the registered events
    and updates the status back
    """
    dynamic_services_settings: DynamicServicesSettings = (
        app.state.settings.dynamic_services
    )
    initial_status = deepcopy(monitor_data.dynamic_sidecar.status)

    if (  # do not refactor, second part of "and condition" is skiped most times
        monitor_data.dynamic_sidecar.were_services_created
        and not await are_all_services_present(
            node_uuid=monitor_data.node_uuid,
            dynamic_sidecar_settings=dynamic_services_settings.dynamic_sidecar,
        )
    ):
        logger.warning("Removing service %s from monitoring", monitor_data.service_name)
        await monitor.remove_service_from_monitor(
            node_uuid=monitor_data.node_uuid,
            save_state=monitor_data.dynamic_sidecar.can_save_state,
        )
        return  # pragma: no cover

    # if the service is not OK (for now failing) monitoring cycle will
    # be skipped. This will allow for others to debug it
    if monitor_data.dynamic_sidecar.status.current != DynamicSidecarStatus.OK:
        message = (
            f"Service {monitor_data.service_name} is failing. Skipping monitoring.\n"
            f"Monitor data\n{monitor_data}"
        )
        # logging as error as this must be addressed by someone
        logger.error(message)
        return

    try:
        with timeout(dynamic_services_settings.monitoring.max_status_api_duration):
            await update_dynamic_sidecar_health(app, monitor_data)
    except asyncio.TimeoutError:
        monitor_data.dynamic_sidecar.is_available = False

    for monitor_event in REGISTERED_EVENTS:
        if await monitor_event.will_trigger(app=app, monitor_data=monitor_data):
            # event.action will apply changes to the output_monitor_data
            await monitor_event.action(app, monitor_data)

    # check if the status of the services has changed from OK
    if initial_status != monitor_data.dynamic_sidecar.status:
        logger.info(
            "Service %s overall status changed to %s",
            monitor_data.service_name,
            monitor_data.dynamic_sidecar.status,
        )


class DynamicSidecarsMonitor:
    def __init__(self, app: FastAPI):
        self._app: FastAPI = app
        self._lock: Lock = Lock()

        self._to_monitor: Dict[str, LockWithMonitorData] = dict()
        self._keep_running: bool = False
        self._inverse_search_mapping: Dict[UUID, str] = dict()
        self._monitor_task: Optional[Task] = None

    async def add_service_to_monitor(self, monitor_data: MonitorData) -> None:
        """Invoked before the service is started

        Because we do not have all items require to compute the service_name the node_uuid is used to
        keep track of the service for faster searches.
        """
        async with self._lock:
            if monitor_data.service_name in self._to_monitor:
                logger.warning(
                    "Service %s is already being monitored", monitor_data.service_name
                )
                return
            if monitor_data.node_uuid in self._inverse_search_mapping:
                raise DynamicSidecarError(
                    "node_uuids at a global level collided. A running "
                    f"service for node {monitor_data.node_uuid} already exists. "
                    "Please checkout other projects which may have this issue."
                )
            if not monitor_data.service_name:
                raise DynamicSidecarError(
                    "a service with no name is not valid. Invalid usage."
                )
            self._inverse_search_mapping[
                monitor_data.node_uuid
            ] = monitor_data.service_name
            self._to_monitor[monitor_data.service_name] = LockWithMonitorData(
                resource_lock=AsyncResourceLock.from_is_locked(False),
                monitor_data=monitor_data,
            )
            logger.debug("Added service '%s' to monitor", monitor_data.service_name)

    async def remove_service_from_monitor(
        self, node_uuid: NodeID, save_state: Optional[bool]
    ) -> None:
        """Handles the removal cycle of the services, saving states etc..."""
        async with self._lock:
            if node_uuid not in self._inverse_search_mapping:
                raise DynamicSidecarNotFoundError(node_uuid)

            service_name = self._inverse_search_mapping[node_uuid]
            if service_name not in self._to_monitor:
                return

            # invoke container cleanup at this point
            dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(
                self._app
            )

            current: LockWithMonitorData = self._to_monitor[service_name]
            dynamic_sidecar_endpoint = current.monitor_data.dynamic_sidecar.endpoint
            await dynamic_sidecar_client.begin_service_destruction(
                dynamic_sidecar_endpoint=dynamic_sidecar_endpoint
            )

            dynamic_sidecar_settings: DynamicSidecarSettings = (
                self._app.state.settings.dynamic_services.dynamic_sidecar
            )

            _ = save_state
            # TODO: save state and others go here

            # remove the 2 services
            await remove_dynamic_sidecar_stack(
                node_uuid=current.monitor_data.node_uuid,
                dynamic_sidecar_settings=dynamic_sidecar_settings,
            )
            # remove network
            await remove_dynamic_sidecar_network(
                current.monitor_data.dynamic_sidecar_network_name
            )

            # finally remove it from the monitor
            del self._to_monitor[service_name]
            del self._inverse_search_mapping[node_uuid]
            logger.debug("Removed service '%s' from monitoring", service_name)

    async def get_stack_status(self, node_uuid: NodeID) -> RunningDynamicServiceDetails:
        async with self._lock:
            if node_uuid not in self._inverse_search_mapping:
                raise DynamicSidecarNotFoundError(node_uuid)

            service_name = self._inverse_search_mapping[node_uuid]

            monitor_data: MonitorData = self._to_monitor[service_name].monitor_data

            # check if there was an error picked up by the monitor and marked this
            # service as failing
            if monitor_data.dynamic_sidecar.status.current != DynamicSidecarStatus.OK:
                return RunningDynamicServiceDetails.from_monitoring_status(
                    node_uuid=node_uuid,
                    monitor_data=monitor_data,
                    service_state=ServiceState.FAILED,
                    service_message=monitor_data.dynamic_sidecar.status.info,
                )

            dynamic_sidecar_settings: DynamicSidecarSettings = (
                self._app.state.settings.dynamic_services.dynamic_sidecar
            )
            dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(
                self._app
            )

            service_state, service_message = await get_dynamic_sidecar_state(
                # the service_name is unique and will not collide with other names
                # it can be used in place of the service_id here, as the docker API accepts both
                service_id=monitor_data.service_name,
                dynamic_sidecar_settings=dynamic_sidecar_settings,
            )

            # while the dynamic-sidecar state is not RUNNING report it's state
            if service_state != ServiceState.RUNNING:
                return RunningDynamicServiceDetails.from_monitoring_status(
                    node_uuid=node_uuid,
                    monitor_data=monitor_data,
                    service_state=service_state,
                    service_message=service_message,
                )

            docker_statuses: Optional[
                Dict[str, Dict[str, str]]
            ] = await dynamic_sidecar_client.containers_docker_status(
                dynamic_sidecar_endpoint=monitor_data.dynamic_sidecar.endpoint
            )

            # error fetching docker_statues, probably someone should check
            if docker_statuses is None:
                return RunningDynamicServiceDetails.from_monitoring_status(
                    node_uuid=node_uuid,
                    monitor_data=monitor_data,
                    service_state=ServiceState.STARTING,
                    service_message="There was an error while trying to fetch the stautes form the contianers",
                )

            # wait for containers to start
            if len(docker_statuses) == 0:
                # marks status as waiting for containers
                return RunningDynamicServiceDetails.from_monitoring_status(
                    node_uuid=node_uuid,
                    monitor_data=monitor_data,
                    service_state=ServiceState.STARTING,
                    service_message="",
                )

            # compute composed containers states
            container_state, container_message = extract_containers_minimim_statuses(
                docker_statuses
            )
            return RunningDynamicServiceDetails.from_monitoring_status(
                node_uuid=node_uuid,
                monitor_data=monitor_data,
                service_state=container_state,
                service_message=container_message,
            )

    async def _runner(self) -> None:
        """This code runs under a lock and can safely change the Monitor data of all entries"""
        logger.debug("Monitoring dynamic-sidecars")

        async def monitor_single_service(service_name: str) -> None:
            lock_with_monitor_data: LockWithMonitorData = self._to_monitor[service_name]
            monitor_data: MonitorData = lock_with_monitor_data.monitor_data
            try:
                await _apply_monitoring(self._app, self, monitor_data)
            except asyncio.CancelledError:  # pylint: disable=try-except-raise
                raise  # pragma: no cover
            except Exception:  # pylint: disable=broad-except
                service_name = monitor_data.service_name

                message = (
                    f"Monitoring of {service_name} failed:\n{traceback.format_exc()}"
                )
                logger.error(message)
                monitor_data.dynamic_sidecar.status.update_failing_status(message)
            finally:
                # when done, always unlock the resource
                await lock_with_monitor_data.resource_lock.unlock_resource()

        # start monitoring for services which are not currently undergoing
        # a monitoring cycle
        for service_name in self._to_monitor:
            lock_with_monitor_data = self._to_monitor[service_name]
            resource_marked_as_locked = (
                await lock_with_monitor_data.resource_lock.mark_as_locked_if_unlocked()
            )
            if resource_marked_as_locked:
                # fire and forget about the task
                asyncio.create_task(monitor_single_service(service_name))

    async def _run_monitor_task(self) -> None:
        settings: DynamicServicesMonitoringSettings = (
            self._app.state.settings.dynamic_services.monitoring
        )

        while self._keep_running:
            # make sure access to the dict is locked while the monitoring cycle is running
            try:
                async with self._lock:
                    await self._runner()

                await sleep(settings.monitor_interval_seconds)
            except asyncio.CancelledError:  # pragma: no cover
                break  # pragma: no cover

        logger.warning("Monitor was shut down")

    async def start(self) -> None:
        # run as a background task
        logging.info("Starting dynamic-sidecar monitor")
        self._keep_running = True
        self._monitor_task = asyncio.create_task(self._run_monitor_task())

        # discover all services which were started before and add them to the monitor
        dynamic_sidecar_settings: DynamicSidecarSettings = (
            self._app.state.settings.dynamic_services.dynamic_sidecar
        )
        services_to_monitor: Deque[
            ServiceLabelsStoredData
        ] = await get_dynamic_sidecars_to_monitor(dynamic_sidecar_settings)

        logging.info(
            "The following services need to be monitored: %s", services_to_monitor
        )

        for service_to_monitor in services_to_monitor:
            monitor_data = MonitorData.from_service_labels_stored_data(
                service_labels_stored_data=service_to_monitor,
                port=dynamic_sidecar_settings.DYNAMIC_SIDECAR_PORT,
            )
            await self.add_service_to_monitor(monitor_data)

    async def shutdown(self):
        logging.info("Shutting down dynamic-sidecar monitor")
        self._keep_running = False
        self._inverse_search_mapping = dict()
        self._to_monitor = dict()

        if self._monitor_task is not None:
            await self._monitor_task
            self._monitor_task = None


async def setup_monitor(app: FastAPI):
    dynamic_sidecars_monitor = DynamicSidecarsMonitor(app)
    app.state.dynamic_sidecar_monitor = dynamic_sidecars_monitor

    settings: DynamicServicesMonitoringSettings = (
        app.state.settings.dynamic_services.monitoring
    )
    if not settings.monitoring_enabled:
        logger.warning("Monitor will not be started!!!")
        return

    await dynamic_sidecars_monitor.start()


async def shutdown_monitor(app: FastAPI):
    dynamic_sidecars_monitor = app.state.dynamic_sidecar_monitor
    await dynamic_sidecars_monitor.shutdown()


__all__ = ["DynamicSidecarsMonitor", "setup_monitor", "shutdown_monitor"]
