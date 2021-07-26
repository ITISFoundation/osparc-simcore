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
    DynamicServicesSchedulerSettings,
    DynamicServicesSettings,
    DynamicSidecarSettings,
)
from ....models.schemas.dynamic_services import (
    AsyncResourceLock,
    DynamicSidecarStatus,
    LockWithSchedulerData,
    RunningDynamicServiceDetails,
    SchedulerData,
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
    get_dynamic_sidecars_to_observe,
    remove_dynamic_sidecar_network,
    remove_dynamic_sidecar_stack,
)
from ..docker_states import ServiceState, extract_containers_minimim_statuses
from ..errors import DynamicSidecarError, DynamicSidecarNotFoundError
from .events import REGISTERED_EVENTS

logger = logging.getLogger(__name__)


async def _apply_observation_cycle(
    app: FastAPI, scheduler: "DynamicSidecarsScheduler", scheduler_data: SchedulerData
) -> None:
    """
    fetches status for service and then processes all the registered events
    and updates the status back
    """
    dynamic_services_settings: DynamicServicesSettings = (
        app.state.settings.DYNAMIC_SERVICES
    )
    initial_status = deepcopy(scheduler_data.dynamic_sidecar.status)

    if (  # do not refactor, second part of "and condition" is skiped most times
        scheduler_data.dynamic_sidecar.were_services_created
        and not await are_all_services_present(
            node_uuid=scheduler_data.node_uuid,
            dynamic_sidecar_settings=dynamic_services_settings.DYNAMIC_SIDECAR,
        )
    ):
        logger.warning(
            "Removing service %s from observation", scheduler_data.service_name
        )
        await scheduler.remove_service_to_observe(
            node_uuid=scheduler_data.node_uuid,
            save_state=scheduler_data.dynamic_sidecar.can_save_state,
        )
        return  # pragma: no cover

    # if the service is not OK (for now failing) observation cycle will
    # be skipped. This will allow for others to debug it
    if scheduler_data.dynamic_sidecar.status.current != DynamicSidecarStatus.OK:
        message = (
            f"Service {scheduler_data.service_name} is failing. Skipping observation.\n"
            f"Scheduler data\n{scheduler_data}"
        )
        # logging as error as this must be addressed by someone
        logger.error(message)
        return

    try:
        with timeout(
            dynamic_services_settings.DYNAMIC_SCHEDULER.DIRECTOR_V2_DYNAMIC_SCHEDULER_MAX_STATUS_API_DURATION
        ):
            await update_dynamic_sidecar_health(app, scheduler_data)
    except asyncio.TimeoutError:
        scheduler_data.dynamic_sidecar.is_available = False

    for dynamic_scheduler_event in REGISTERED_EVENTS:
        if await dynamic_scheduler_event.will_trigger(
            app=app, scheduler_data=scheduler_data
        ):
            # event.action will apply changes to the output_scheduler_data
            await dynamic_scheduler_event.action(app, scheduler_data)

    # check if the status of the services has changed from OK
    if initial_status != scheduler_data.dynamic_sidecar.status:
        logger.info(
            "Service %s overall status changed to %s",
            scheduler_data.service_name,
            scheduler_data.dynamic_sidecar.status,
        )


class DynamicSidecarsScheduler:
    def __init__(self, app: FastAPI):
        self._app: FastAPI = app
        self._lock: Lock = Lock()

        self._to_observe: Dict[str, LockWithSchedulerData] = dict()
        self._keep_running: bool = False
        self._inverse_search_mapping: Dict[UUID, str] = dict()
        self._scheduler_task: Optional[Task] = None

    async def add_service_to_observe(self, scheduler_data: SchedulerData) -> None:
        """Invoked before the service is started

        Because we do not have all items require to compute the service_name the node_uuid is used to
        keep track of the service for faster searches.
        """
        async with self._lock:
            if scheduler_data.service_name in self._to_observe:
                logger.warning(
                    "Service %s is already being observed", scheduler_data.service_name
                )
                return
            if scheduler_data.node_uuid in self._inverse_search_mapping:
                raise DynamicSidecarError(
                    "node_uuids at a global level collided. A running "
                    f"service for node {scheduler_data.node_uuid} already exists. "
                    "Please checkout other projects which may have this issue."
                )
            if not scheduler_data.service_name:
                raise DynamicSidecarError(
                    "a service with no name is not valid. Invalid usage."
                )
            self._inverse_search_mapping[
                scheduler_data.node_uuid
            ] = scheduler_data.service_name
            self._to_observe[scheduler_data.service_name] = LockWithSchedulerData(
                resource_lock=AsyncResourceLock.from_is_locked(False),
                scheduler_data=scheduler_data,
            )
            logger.debug("Added service '%s' to observe", scheduler_data.service_name)

    async def remove_service_to_observe(
        self, node_uuid: NodeID, save_state: Optional[bool]
    ) -> None:
        """Handles the removal cycle of the services, saving states etc..."""
        async with self._lock:
            if node_uuid not in self._inverse_search_mapping:
                raise DynamicSidecarNotFoundError(node_uuid)

            service_name = self._inverse_search_mapping[node_uuid]
            if service_name not in self._to_observe:
                return

            # invoke container cleanup at this point
            dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(
                self._app
            )

            current: LockWithSchedulerData = self._to_observe[service_name]
            dynamic_sidecar_endpoint = current.scheduler_data.dynamic_sidecar.endpoint
            await dynamic_sidecar_client.begin_service_destruction(
                dynamic_sidecar_endpoint=dynamic_sidecar_endpoint
            )

            dynamic_sidecar_settings: DynamicSidecarSettings = (
                self._app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
            )

            _ = save_state
            # TODO: save state and others go here

            # remove the 2 services
            await remove_dynamic_sidecar_stack(
                node_uuid=current.scheduler_data.node_uuid,
                dynamic_sidecar_settings=dynamic_sidecar_settings,
            )
            # remove network
            await remove_dynamic_sidecar_network(
                current.scheduler_data.dynamic_sidecar_network_name
            )

            # finally remove it from the scheduler
            del self._to_observe[service_name]
            del self._inverse_search_mapping[node_uuid]
            logger.debug("Removed service '%s' from scheduler", service_name)

    async def get_stack_status(self, node_uuid: NodeID) -> RunningDynamicServiceDetails:
        async with self._lock:
            if node_uuid not in self._inverse_search_mapping:
                raise DynamicSidecarNotFoundError(node_uuid)
            service_name = self._inverse_search_mapping[node_uuid]

            scheduler_data: SchedulerData = self._to_observe[
                service_name
            ].scheduler_data

            # check if there was an error picked up by the scheduler
            # and marked this service as failing
            if scheduler_data.dynamic_sidecar.status.current != DynamicSidecarStatus.OK:
                return RunningDynamicServiceDetails.from_scheduler_data(
                    node_uuid=node_uuid,
                    scheduler_data=scheduler_data,
                    service_state=ServiceState.FAILED,
                    service_message=scheduler_data.dynamic_sidecar.status.info,
                )

            dynamic_sidecar_settings: DynamicSidecarSettings = (
                self._app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
            )
            dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(
                self._app
            )

            service_state, service_message = await get_dynamic_sidecar_state(
                # the service_name is unique and will not collide with other names
                # it can be used in place of the service_id here, as the docker API accepts both
                service_id=scheduler_data.service_name,
                dynamic_sidecar_settings=dynamic_sidecar_settings,
            )

            # while the dynamic-sidecar state is not RUNNING report it's state
            if service_state != ServiceState.RUNNING:
                return RunningDynamicServiceDetails.from_scheduler_data(
                    node_uuid=node_uuid,
                    scheduler_data=scheduler_data,
                    service_state=service_state,
                    service_message=service_message,
                )

            docker_statuses: Optional[
                Dict[str, Dict[str, str]]
            ] = await dynamic_sidecar_client.containers_docker_status(
                dynamic_sidecar_endpoint=scheduler_data.dynamic_sidecar.endpoint
            )

            # error fetching docker_statues, probably someone should check
            if docker_statuses is None:
                return RunningDynamicServiceDetails.from_scheduler_data(
                    node_uuid=node_uuid,
                    scheduler_data=scheduler_data,
                    service_state=ServiceState.STARTING,
                    service_message="There was an error while trying to fetch the stautes form the contianers",
                )

            # wait for containers to start
            if len(docker_statuses) == 0:
                # marks status as waiting for containers
                return RunningDynamicServiceDetails.from_scheduler_data(
                    node_uuid=node_uuid,
                    scheduler_data=scheduler_data,
                    service_state=ServiceState.STARTING,
                    service_message="",
                )

            # compute composed containers states
            container_state, container_message = extract_containers_minimim_statuses(
                docker_statuses
            )
            return RunningDynamicServiceDetails.from_scheduler_data(
                node_uuid=node_uuid,
                scheduler_data=scheduler_data,
                service_state=container_state,
                service_message=container_message,
            )

    async def _runner(self) -> None:
        """This code runs under a lock and can safely change the SchedulerData of all entries"""
        logger.debug("Observing dynamic-sidecars")

        async def observing_single_service(service_name: str) -> None:
            lock_with_scheduler_data: LockWithSchedulerData = self._to_observe[
                service_name
            ]
            scheduler_data: SchedulerData = lock_with_scheduler_data.scheduler_data
            try:
                await _apply_observation_cycle(self._app, self, scheduler_data)
            except asyncio.CancelledError:  # pylint: disable=try-except-raise
                raise  # pragma: no cover
            except Exception:  # pylint: disable=broad-except
                service_name = scheduler_data.service_name

                message = (
                    f"Observation of {service_name} failed:\n{traceback.format_exc()}"
                )
                logger.error(message)
                scheduler_data.dynamic_sidecar.status.update_failing_status(message)
            finally:
                # when done, always unlock the resource
                await lock_with_scheduler_data.resource_lock.unlock_resource()

        # start observation for services which are
        # not currently undergoing a observation cycle
        for service_name in self._to_observe:
            lock_with_scheduler_data = self._to_observe[service_name]
            resource_marked_as_locked = (
                await lock_with_scheduler_data.resource_lock.mark_as_locked_if_unlocked()
            )
            if resource_marked_as_locked:
                # fire and forget about the task
                asyncio.create_task(observing_single_service(service_name))

    async def _run_scheduler_task(self) -> None:
        settings: DynamicServicesSchedulerSettings = (
            self._app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
        )

        while self._keep_running:
            # make sure access to the dict is locked while the observation cycle is running
            try:
                async with self._lock:
                    await self._runner()

                await sleep(settings.DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL_SECONDS)
            except asyncio.CancelledError:  # pragma: no cover
                break  # pragma: no cover

        logger.warning("Scheduler was shut down")

    async def start(self) -> None:
        # run as a background task
        logging.info("Starting dynamic-sidecar scheduler")
        self._keep_running = True
        self._scheduler_task = asyncio.create_task(self._run_scheduler_task())

        # discover all services which were started before and add them to the scheduler
        dynamic_sidecar_settings: DynamicSidecarSettings = (
            self._app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )
        services_to_observe: Deque[
            ServiceLabelsStoredData
        ] = await get_dynamic_sidecars_to_observe(dynamic_sidecar_settings)

        logging.info(
            "The following services need to be observed: %s", services_to_observe
        )

        for service_to_observe in services_to_observe:
            scheduler_data = SchedulerData.from_service_labels_stored_data(
                service_labels_stored_data=service_to_observe,
                port=dynamic_sidecar_settings.DYNAMIC_SIDECAR_PORT,
            )
            await self.add_service_to_observe(scheduler_data)

    async def shutdown(self):
        logging.info("Shutting down dynamic-sidecar scheduler")
        self._keep_running = False
        self._inverse_search_mapping = dict()
        self._to_observe = dict()

        if self._scheduler_task is not None:
            await self._scheduler_task
            self._scheduler_task = None


async def setup_scheduler(app: FastAPI):
    dynamic_sidecars_scheduler = DynamicSidecarsScheduler(app)
    app.state.dynamic_sidecar_scheduler = dynamic_sidecars_scheduler

    settings: DynamicServicesSchedulerSettings = (
        app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
    )
    if not settings.DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED:
        logger.warning("dynamic-sidecar scheduler will not be started!!!")
        return

    await dynamic_sidecars_scheduler.start()


async def shutdown_scheduler(app: FastAPI):
    dynamic_sidecar_scheduler = app.state.dynamic_sidecar_scheduler
    await dynamic_sidecar_scheduler.shutdown()


__all__ = ["DynamicSidecarsScheduler", "setup_scheduler", "shutdown_scheduler"]
