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
from typing import Deque, Dict, Any, Optional, List, Tuple

from aiohttp.web import Application
from async_timeout import timeout

from ..config import ServiceSidecarSettings, get_settings
from ..docker_utils import (
    get_service_sidecars_to_monitor,
    get_service_sidecar_state,
    ServiceLabelsStoredData,
)
from ..exceptions import ServiceSidecarError
from .handlers import REGISTERED_HANDLERS
from .models import (
    LockWithMonitorData,
    MonitorData,
    ServiceSidecarStatus,
)
from .service_sidecar_api import query_service, get_api_client, ServiceSidecarClient
from .utils import AsyncResourceLock
from ....models.domains.dynamic_sidecar import PathsMappingModel, ComposeSpecModel
from ..parse_docker_status import ServiceState, extract_containers_minimim_statuses

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
        # pylint: disable=too-many-arguments
        self,
        service_name: str,
        node_uuid: str,
        hostname: str,
        port: int,
        service_key: str,
        service_tag: str,
        paths_mapping: PathsMappingModel,
        compose_spec: ComposeSpecModel,
        target_container: Optional[str],
        service_sidecar_network_name: str,
        simcore_traefik_zone: str,
        service_port: int,
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
                    paths_mapping=paths_mapping,
                    compose_spec=compose_spec,
                    target_container=target_container,
                    service_sidecar_network_name=service_sidecar_network_name,
                    simcore_traefik_zone=simcore_traefik_zone,
                    service_port=service_port,
                ),
            )
            logger.debug("Added service '%s' to monitor", service_name)

    async def remove_service_from_monitor(self, node_uuid: str) -> None:
        # invoked before the service is removed
        async with self._lock:
            if node_uuid not in self._inverse_search_mapping:
                return

            service_name = self._inverse_search_mapping[node_uuid]
            if service_name not in self._to_monitor:
                return

            # invoke container cleanup at this point
            services_sidecar_client: ServiceSidecarClient = get_api_client(self._app)

            # invokes docker compose down, even if the containers are removed they still
            # seem attached to the network; the network cannot be removed (this is logged
            # as a failure by the director) and the docker_network will trash the environment
            # There is no suitable solution to this issue, having netwoks trash
            # the environment seems to be the best approach :\
            current: LockWithMonitorData = self._to_monitor[service_name]
            service_sidecar_endpoint = current.monitor_data.service_sidecar.endpoint
            await services_sidecar_client.remove_docker_compose_spec(
                service_sidecar_endpoint=service_sidecar_endpoint
            )

            # finally remove this service
            del self._to_monitor[service_name]
            del self._inverse_search_mapping[node_uuid]
            logger.debug("Removed service '%s' from monitoring", service_name)

    async def get_stack_status(self, node_uuid: str) -> Dict[str, Any]:
        """Computes the service sidecar """

        def make_error_status():
            error_status = dict(
                dynamic_type="dynamic-sidecar",
                service_state="error",
                service_message=f"Could not find a service for node_uuid={node_uuid}",
            )
            logging.warning(
                "Producting error status for service-sidecar with node_uuid=%s\n%s",
                node_uuid,
                error_status,
            )
            return error_status

        def make_service_status(
            monitor_data: MonitorData, service_state: ServiceState, service_message: str
        ):
            return dict(
                dynamic_type="dynamic-sidecar",  # tells the frontend this is run with a dynamic sidecar
                published_port=80,  # default for the proxy
                entry_point="",  # can be removed when dynamic_type="dynamic-sidecar"
                service_uuid=node_uuid,
                service_key=monitor_data.service_key,
                service_version=monitor_data.service_tag,
                service_host=monitor_data.service_name,
                service_port=monitor_data.service_port,
                service_basepath="",  # not needed here
                service_state=service_state,
                service_message=service_message,
            )

        async with self._lock:
            if node_uuid not in self._inverse_search_mapping:
                return make_error_status()

            service_name = self._inverse_search_mapping[node_uuid]
            if service_name not in self._to_monitor:
                return make_error_status()

            monitor_data: MonitorData = self._to_monitor[service_name].monitor_data
            service_sidecar_settings = get_settings(self._app)
            services_sidecar_client: ServiceSidecarClient = get_api_client(self._app)

            service_state, service_message = await get_service_sidecar_state(
                # the service_name is unique and will not collide with other names
                # it can be used in place of the service_id here, as the docker API accepts both
                service_id=monitor_data.service_name,
                service_sidecar_settings=service_sidecar_settings,
            )

            # while the service-sidecar state is not RUNNING report it's state
            if service_state != ServiceState.RUNNING:
                return make_service_status(
                    monitor_data=monitor_data,
                    service_state=service_state,
                    service_message=service_message,
                )

            docker_statuses: Optional[
                Dict[str, Dict[str, str]]
            ] = await services_sidecar_client.containers_docker_status(
                service_sidecar_endpoint=monitor_data.service_sidecar.endpoint
            )

            # error fetching docker_statues, probably someone should check
            if docker_statuses is None:
                return make_service_status(
                    monitor_data=monitor_data,
                    service_state=ServiceState.STARTING,
                    service_message="There was an error while trying to fetch the stautes form the contianers",
                )

            # wait for containers to start
            if len(docker_statuses) == 0:
                # marks status as waiting for containers
                return make_service_status(
                    monitor_data=monitor_data,
                    service_state=ServiceState.STARTING,
                    service_message="",
                )

            # compute composed containers states
            container_state, container_message = extract_containers_minimim_statuses(
                docker_statuses
            )
            return make_service_status(
                monitor_data=monitor_data,
                service_state=container_state,
                service_message=container_message,
            )

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
            ServiceLabelsStoredData
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
                paths_mapping,
                compose_spec,
                target_container,
                service_sidecar_network_name,
                simcore_traefik_zone,
                service_port,
            ) = service_to_monitor

            await self.add_service_to_monitor(
                service_name=service_name,
                node_uuid=node_uuid,
                hostname=service_name,
                port=service_sidecar_settings.web_service_port,
                service_key=service_key,
                service_tag=service_tag,
                paths_mapping=paths_mapping,
                compose_spec=compose_spec,
                target_container=target_container,
                service_sidecar_network_name=service_sidecar_network_name,
                simcore_traefik_zone=simcore_traefik_zone,
                service_port=service_port,
            )

    async def shutdown(self):
        logging.info("Shutting down service-sidecar monitor")
        self._keep_running = False
        self._inverse_search_mapping = dict()
        self._to_monitor = dict()


def get_monitor(app: Application) -> ServiceSidecarsMonitor:
    return app.state.service_sidecar_monitor


async def setup_monitor(app: Application):
    service_sidecars_monitor = ServiceSidecarsMonitor(app)
    app.state.service_sidecar_monitor = service_sidecars_monitor

    await service_sidecars_monitor.start()


async def shutdown_monitor(app: Application):
    service_sidecars_monitor = app.state.service_sidecar_monitor
    await service_sidecars_monitor.shutdown()
