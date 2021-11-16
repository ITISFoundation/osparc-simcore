import asyncio
import contextlib
import logging
import traceback
from asyncio import Lock, Queue, Task, sleep
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional
from uuid import UUID

import httpx
from async_timeout import timeout
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID

from ....core.settings import (
    DynamicServicesSchedulerSettings,
    DynamicServicesSettings,
    DynamicSidecarSettings,
)
from ....models.domains.dynamic_services import RetrieveDataOutEnveloped
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
    # TODO: PC-> ANE: custom settings are frozen. in principle, no need to create copies.
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
        await scheduler.mark_service_for_removal(
            node_uuid=scheduler_data.node_uuid,
            can_save=scheduler_data.dynamic_sidecar.can_save_state,
        )

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


@dataclass
class DynamicSidecarsScheduler:
    app: FastAPI

    _lock: Lock = field(default_factory=Lock)
    _to_observe: Dict[str, LockWithSchedulerData] = field(default_factory=dict)
    _keep_running: bool = False
    _inverse_search_mapping: Dict[UUID, str] = field(default_factory=dict)
    _scheduler_task: Optional[Task] = None
    _trigger_observation_queue_task: Optional[Task] = None
    _trigger_observation_queue: Queue = field(default_factory=Queue)

    async def add_service(self, scheduler_data: SchedulerData) -> None:
        """Invoked before the service is started

        Because we do not have all items require to compute the service_name the node_uuid is used to
        keep track of the service for faster searches.
        """
        async with self._lock:

            if not scheduler_data.service_name:
                raise DynamicSidecarError(
                    "a service with no name is not valid. Invalid usage."
                )

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

            self._inverse_search_mapping[
                scheduler_data.node_uuid
            ] = scheduler_data.service_name
            self._to_observe[scheduler_data.service_name] = LockWithSchedulerData(
                resource_lock=AsyncResourceLock.from_is_locked(False),
                scheduler_data=scheduler_data,
            )

            await self._enqueue_observation_from_service_name(
                scheduler_data.service_name
            )
            logger.debug("Added service '%s' to observe", scheduler_data.service_name)

    async def mark_service_for_removal(
        self, node_uuid: NodeID, can_save: Optional[bool]
    ) -> None:
        """Marks service for removal, causing RemoveMarkedService to trigger"""
        async with self._lock:
            if node_uuid not in self._inverse_search_mapping:
                raise DynamicSidecarNotFoundError(node_uuid)

            service_name = self._inverse_search_mapping[node_uuid]
            if service_name not in self._to_observe:
                return

            current: LockWithSchedulerData = self._to_observe[service_name]
            current.scheduler_data.dynamic_sidecar.service_removal_state.mark_to_remove(
                can_save
            )

        await self._enqueue_observation_from_service_name(service_name)
        logger.debug("Service '%s' marked for removal from scheduler", service_name)

    async def finish_service_removal(self, node_uuid: NodeID) -> None:
        """
        directly invoked from RemoveMarkedService once it's finished
        removes the service from the observation cycle
        """
        async with self._lock:
            if node_uuid not in self._inverse_search_mapping:
                raise DynamicSidecarNotFoundError(node_uuid)

            service_name = self._inverse_search_mapping[node_uuid]
            if service_name not in self._to_observe:
                return

            del self._to_observe[service_name]
            del self._inverse_search_mapping[node_uuid]

        logger.debug("Removed service '%s' from scheduler", service_name)

    async def get_stack_status(self, node_uuid: NodeID) -> RunningDynamicServiceDetails:
        if node_uuid not in self._inverse_search_mapping:
            raise DynamicSidecarNotFoundError(node_uuid)
        service_name = self._inverse_search_mapping[node_uuid]

        scheduler_data: SchedulerData = self._to_observe[service_name].scheduler_data

        # check if there was an error picked up by the scheduler
        # and marked this service as failing
        if scheduler_data.dynamic_sidecar.status.current != DynamicSidecarStatus.OK:
            return RunningDynamicServiceDetails.from_scheduler_data(
                node_uuid=node_uuid,
                scheduler_data=scheduler_data,
                service_state=ServiceState.FAILED,
                service_message=scheduler_data.dynamic_sidecar.status.info,
            )

        service_state, service_message = await get_dynamic_sidecar_state(
            # the service_name is unique and will not collide with other names
            # it can be used in place of the service_id here, as the docker API accepts both
            service_id=scheduler_data.service_name
        )

        # while the dynamic-sidecar state is not RUNNING report it's state
        if service_state != ServiceState.RUNNING:
            return RunningDynamicServiceDetails.from_scheduler_data(
                node_uuid=node_uuid,
                scheduler_data=scheduler_data,
                service_state=service_state,
                service_message=service_message,
            )

        dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(
            self.app
        )

        try:
            docker_statuses: Optional[
                Dict[str, Dict[str, str]]
            ] = await dynamic_sidecar_client.containers_docker_status(
                dynamic_sidecar_endpoint=scheduler_data.dynamic_sidecar.endpoint
            )
        except httpx.HTTPError:
            # error fetching docker_statues, probably someone should check
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

    async def retrieve_service_inputs(
        self, node_uuid: NodeID, port_keys: List[str]
    ) -> RetrieveDataOutEnveloped:
        """Pulls data from input ports for the service"""
        if node_uuid not in self._inverse_search_mapping:
            raise DynamicSidecarNotFoundError(node_uuid)

        service_name = self._inverse_search_mapping[node_uuid]
        scheduler_data: SchedulerData = self._to_observe[service_name].scheduler_data

        dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(
            self.app
        )

        transferred_bytes = await dynamic_sidecar_client.service_pull_input_ports(
            dynamic_sidecar_endpoint=scheduler_data.dynamic_sidecar.endpoint,
            port_keys=port_keys,
        )

        return RetrieveDataOutEnveloped.from_transferred_bytes(transferred_bytes)

    async def _enqueue_observation_from_service_name(self, service_name: str) -> None:
        await self._trigger_observation_queue.put(service_name)

    async def _run_trigger_observation_queue_task(self) -> None:
        """generates events at regular time interval"""

        async def observing_single_service(service_name: str) -> None:
            lock_with_scheduler_data: LockWithSchedulerData = self._to_observe[
                service_name
            ]
            scheduler_data: SchedulerData = lock_with_scheduler_data.scheduler_data
            try:
                await _apply_observation_cycle(self.app, self, scheduler_data)
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

        service_name: Optional[str]
        while service_name := await self._trigger_observation_queue.get():
            logger.info("Handling observation for %s", service_name)
            if service_name not in self._to_observe:
                logger.debug(
                    "Skipping observation, service no longer found %s", service_name
                )
                continue

            lock_with_scheduler_data = self._to_observe[service_name]
            resource_marked_as_locked = (
                await lock_with_scheduler_data.resource_lock.mark_as_locked_if_unlocked()
            )
            if resource_marked_as_locked:
                # fire and forget about the task
                asyncio.create_task(
                    observing_single_service(service_name),
                    name=f"observe {service_name}",
                )

        logger.info("Scheduler 'trigger observation queue task' was shut down")

    async def _run_scheduler_task(self) -> None:
        settings: DynamicServicesSchedulerSettings = (
            self.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
        )

        while self._keep_running:
            logger.debug("Observing dynamic-sidecars %s", self._to_observe.keys())

            try:
                # prevent access to self._to_observe
                async with self._lock:
                    for service_name in self._to_observe:
                        await self._enqueue_observation_from_service_name(service_name)

                await sleep(settings.DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL_SECONDS)
            except asyncio.CancelledError:  # pragma: no cover
                logger.info("Stopped dynamic scheduler")
                raise
            except Exception:  # pylint: disable=broad-except
                logger.error("Unexpected error in dynamic scheduler", exc_info=True)

    async def _discover_running_services(self) -> None:
        """discover all services which were started before and add them to the scheduler"""
        dynamic_sidecar_settings: DynamicSidecarSettings = (
            self.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )
        services_to_observe: Deque[
            ServiceLabelsStoredData
        ] = await get_dynamic_sidecars_to_observe(dynamic_sidecar_settings)

        logger.info(
            "The following services need to be observed: %s", services_to_observe
        )

        for service_to_observe in services_to_observe:
            scheduler_data = SchedulerData.from_service_labels_stored_data(
                service_labels_stored_data=service_to_observe,
                port=dynamic_sidecar_settings.DYNAMIC_SIDECAR_PORT,
            )
            await self.add_service(scheduler_data)

    async def start(self) -> None:
        # run as a background task
        logger.info("Starting dynamic-sidecar scheduler")
        self._keep_running = True
        self._scheduler_task = asyncio.create_task(
            self._run_scheduler_task(), name="dynamic-scheduler"
        )
        self._trigger_observation_queue_task = asyncio.create_task(
            self._run_trigger_observation_queue_task(),
            name="dynamic-scheduler-trigger-obs-queue",
        )

        await self._discover_running_services()

    async def shutdown(self):
        logger.info("Shutting down dynamic-sidecar scheduler")
        self._keep_running = False
        self._inverse_search_mapping = {}
        self._to_observe = {}

        if self._scheduler_task is not None:
            self._scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scheduler_task
            self._scheduler_task = None

        if self._trigger_observation_queue_task is not None:
            await self._trigger_observation_queue.put(None)

            self._trigger_observation_queue_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._trigger_observation_queue_task
            self._trigger_observation_queue_task = None
            self._trigger_observation_queue = Queue()


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
