"""Dynamic services scheduler

This scheduler takes care of scheduling the dynamic services life cycle.

self._to_observe is a list containing all the dynamic services to schedule (from creation to deletion)
self._to_observe is protected by an asyncio Lock
1. a background task runs every X seconds and adds all the current scheduled services in an asyncio.Queue
2. a second background task processes the entries in the Queue and starts a task per service
  a. if the service is already under "observation" then it will skip this cycle
3. a third background task dealing with ensuring no `volumes removal services`
    remain in the system in case the director-v2:
    - is restarted before while the service is running
    - an error occurs while removing one such services
"""

import asyncio
import contextlib
import functools
import logging
from asyncio import Lock, Queue, Task, sleep
from dataclasses import dataclass, field

from fastapi import FastAPI
from models_library.basic_types import PortInt
from models_library.projects import ProjectID
from models_library.projects_networks import DockerNetworkAlias
from models_library.projects_nodes_io import NodeID
from models_library.service_settings_labels import RestartPolicy, SimcoreServiceLabels
from models_library.users import UserID
from pydantic import AnyHttpUrl
from servicelib.background_task import cancel_task
from servicelib.fastapi.long_running_tasks.client import ProgressCallback
from servicelib.fastapi.long_running_tasks.server import TaskProgress

from .....core.settings import DynamicServicesSchedulerSettings, DynamicSidecarSettings
from .....models.domains.dynamic_services import (
    DynamicServiceCreate,
    RetrieveDataOutEnveloped,
)
from .....models.schemas.dynamic_services import (
    RunningDynamicServiceDetails,
    SchedulerData,
    ServiceName,
)
from ...api_client import SidecarsClient, get_sidecars_client
from ...docker_api import update_scheduler_data_label
from ...errors import DynamicSidecarError, DynamicSidecarNotFoundError
from .._abc import SchedulerPublicInterface
from . import _scheduler_utils
from ._events_utils import (
    service_remove_containers,
    service_remove_sidecar_proxy_docker_networks_and_volumes,
    service_save_state,
)
from ._observer import observing_single_service

logger = logging.getLogger(__name__)


_DISABLED_MARK = object()


@dataclass
class Scheduler(  # pylint: disable=too-many-instance-attributes
    SchedulerPublicInterface
):
    app: FastAPI

    _lock: Lock = field(default_factory=Lock)
    _to_observe: dict[ServiceName, SchedulerData] = field(default_factory=dict)
    _service_observation_task: dict[ServiceName, asyncio.Task | object | None] = field(
        default_factory=dict
    )
    _keep_running: bool = False
    _inverse_search_mapping: dict[NodeID, ServiceName] = field(default_factory=dict)
    _scheduler_task: Task | None = None
    _cleanup_volume_removal_services_task: Task | None = None
    _trigger_observation_queue_task: Task | None = None
    _trigger_observation_queue: Queue = field(default_factory=Queue)
    _observation_counter: int = 0

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

        self._cleanup_volume_removal_services_task = asyncio.create_task(
            _scheduler_utils.cleanup_volume_removal_services(self.app),
            name="dynamic-scheduler-cleanup-volume-removal-services",
        )
        await _scheduler_utils.discover_running_services(self)

    async def shutdown(self) -> None:
        logger.info("Shutting down dynamic-sidecar scheduler")
        self._keep_running = False
        self._inverse_search_mapping = {}
        self._to_observe = {}

        if self._cleanup_volume_removal_services_task is not None:
            self._cleanup_volume_removal_services_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_volume_removal_services_task
            self._cleanup_volume_removal_services_task = None

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

        # let's properly cleanup remaining observation tasks
        running_tasks = [
            x for x in self._service_observation_task.values() if isinstance(x, Task)
        ]
        for task in running_tasks:
            task.cancel()
        try:
            MAX_WAIT_TIME_SECONDS = 5
            results = await asyncio.wait_for(
                asyncio.gather(*running_tasks, return_exceptions=True),
                timeout=MAX_WAIT_TIME_SECONDS,
            )
            if bad_results := list(filter(lambda r: isinstance(r, Exception), results)):
                logger.error(
                    "Following observation tasks completed with an unexpected error:%s",
                    f"{bad_results}",
                )
        except asyncio.TimeoutError:
            logger.error(
                "Timed-out waiting for %s to complete. Action: Check why this is blocking",
                f"{running_tasks=}",
            )

    def toggle_observation(self, node_uuid: NodeID, disable: bool) -> bool:
        """
        returns True if it managed to enable/disable observation of the service

        raises DynamicSidecarNotFoundError
        """
        if node_uuid not in self._inverse_search_mapping:
            raise DynamicSidecarNotFoundError(node_uuid)
        service_name = self._inverse_search_mapping[node_uuid]

        service_task = self._service_observation_task.get(service_name)

        if isinstance(service_task, asyncio.Task):
            return False

        if disable:
            self._service_observation_task[service_name] = _DISABLED_MARK
        else:
            self._service_observation_task.pop(service_name, None)

        return True

    async def push_service_outputs(
        self,
        node_uuid: NodeID,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        await _scheduler_utils.push_service_outputs(
            self.app, node_uuid, progress_callback
        )

    async def remove_service_containers(
        self, node_uuid: NodeID, progress_callback: ProgressCallback | None = None
    ) -> None:
        sidecars_client: SidecarsClient = get_sidecars_client(self.app, node_uuid)
        await service_remove_containers(
            app=self.app,
            node_uuid=node_uuid,
            sidecars_client=sidecars_client,
            progress_callback=progress_callback,
        )

    async def remove_service_sidecar_proxy_docker_networks_and_volumes(
        self, task_progress: TaskProgress, node_uuid: NodeID
    ) -> None:
        dynamic_sidecar_settings: DynamicSidecarSettings = (
            self.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )
        await service_remove_sidecar_proxy_docker_networks_and_volumes(
            task_progress=task_progress,
            app=self.app,
            node_uuid=node_uuid,
            dynamic_sidecar_settings=dynamic_sidecar_settings,
        )

    async def save_service_state(
        self, node_uuid: NodeID, progress_callback: ProgressCallback | None = None
    ) -> None:
        sidecars_client: SidecarsClient = get_sidecars_client(self.app, node_uuid)
        await service_save_state(
            app=self.app,
            node_uuid=node_uuid,
            sidecars_client=sidecars_client,
            progress_callback=progress_callback,
        )

    async def add_service(
        self,
        service: DynamicServiceCreate,
        simcore_service_labels: SimcoreServiceLabels,
        port: PortInt,
        request_dns: str,
        request_scheme: str,
        request_simcore_user_agent: str,
        can_save: bool,
    ) -> None:
        """Invoked before the service is started"""
        scheduler_data = SchedulerData.from_http_request(
            service=service,
            simcore_service_labels=simcore_service_labels,
            port=port,
            request_dns=request_dns,
            request_scheme=request_scheme,
            request_simcore_user_agent=request_simcore_user_agent,
            can_save=can_save,
        )
        await self._add_service(scheduler_data)

    async def _add_service(self, scheduler_data: SchedulerData) -> None:
        # NOTE: Because we do not have all items require to compute the
        # service_name the node_uuid is used to keep track of the service
        # for faster searches.
        async with self._lock:
            if scheduler_data.service_name in self._to_observe:
                logger.warning(
                    "Service %s is already being observed", scheduler_data.service_name
                )
                return

            if scheduler_data.node_uuid in self._inverse_search_mapping:
                msg = (
                    f"node_uuids at a global level collided. A running service for node {scheduler_data.node_uuid} already exists."
                    " Please checkout other projects which may have this issue."
                )
                raise DynamicSidecarError(msg)

            self._inverse_search_mapping[
                scheduler_data.node_uuid
            ] = scheduler_data.service_name
            self._to_observe[scheduler_data.service_name] = scheduler_data
            self._enqueue_observation_from_service_name(scheduler_data.service_name)
            logger.debug("Added service '%s' to observe", scheduler_data.service_name)

    def is_service_tracked(self, node_uuid: NodeID) -> bool:
        return node_uuid in self._inverse_search_mapping

    def get_scheduler_data(self, node_uuid: NodeID) -> SchedulerData:
        if node_uuid not in self._inverse_search_mapping:
            raise DynamicSidecarNotFoundError(node_uuid)
        service_name = self._inverse_search_mapping[node_uuid]
        return self._to_observe[service_name]

    def list_services(
        self,
        *,
        user_id: UserID | None = None,
        project_id: ProjectID | None = None,
    ) -> list[NodeID]:
        """
        Returns the list of tracked service UUIDs

        raises DynamicSidecarNotFoundError
        """
        all_tracked_service_uuids = list(self._inverse_search_mapping.keys())
        if user_id is None and project_id is None:
            return all_tracked_service_uuids

        # let's filter
        def _is_scheduled(node_id: NodeID) -> bool:
            try:
                scheduler_data = self.get_scheduler_data(node_id)
                if user_id and scheduler_data.user_id != user_id:
                    return False
                if project_id and scheduler_data.project_id != project_id:
                    return False
                return True
            except DynamicSidecarNotFoundError:
                return False

        return list(
            filter(
                _is_scheduled,
                (n for n in all_tracked_service_uuids),
            )
        )

    async def mark_service_for_removal(
        self,
        node_uuid: NodeID,
        can_save: bool | None,
        skip_observation_recreation: bool = False,
    ) -> None:
        """Marks service for removal, causing RemoveMarkedService to trigger"""
        async with self._lock:
            if node_uuid not in self._inverse_search_mapping:
                raise DynamicSidecarNotFoundError(node_uuid)

            service_name = self._inverse_search_mapping[node_uuid]
            if service_name not in self._to_observe:
                return

            current: SchedulerData = self._to_observe[service_name]

            # if service is already being removed no need to force a cancellation and removal of the service
            if current.dynamic_sidecar.service_removal_state.can_remove:
                logger.info(
                    "Service %s is already being removed, will not cancel observation",
                    node_uuid,
                )
                return

            current.dynamic_sidecar.service_removal_state.mark_to_remove(can_save)
            await update_scheduler_data_label(current)

            # cancel current observation task
            if service_name in self._service_observation_task:
                service_task: None | asyncio.Task | object = (
                    self._service_observation_task[service_name]
                )
                if isinstance(service_task, asyncio.Task):
                    await cancel_task(service_task, timeout=10)

            if skip_observation_recreation:
                return

            # recreate new observation
            dynamic_sidecar_settings: DynamicSidecarSettings = (
                self.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
            )
            dynamic_scheduler: DynamicServicesSchedulerSettings = (
                self.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
            )
            self._service_observation_task[
                service_name
            ] = self.__create_observation_task(
                dynamic_sidecar_settings, dynamic_scheduler, service_name
            )

        logger.debug("Service '%s' marked for removal from scheduler", service_name)

    async def is_service_awaiting_manual_intervention(self, node_uuid: NodeID) -> bool:
        """returns True if services is waiting for manual intervention"""
        return await _scheduler_utils.service_awaits_manual_interventions(
            self.get_scheduler_data(node_uuid)
        )

    async def remove_service_from_observation(self, node_uuid: NodeID) -> None:
        # TODO: this is used internally no need to be here exposed in the interface
        """
        directly invoked from RemoveMarkedService once it's finished
        and removes the service from the observation cycle
        """
        async with self._lock:
            if node_uuid not in self._inverse_search_mapping:
                raise DynamicSidecarNotFoundError(node_uuid)

            service_name = self._inverse_search_mapping[node_uuid]
            if service_name not in self._to_observe:
                logger.warning(
                    "Unexpected: '%s' not found in %s, but found in %s",
                    f"{service_name}",
                    f"{self._to_observe=}",
                    f"{self._inverse_search_mapping=}",
                )

            del self._inverse_search_mapping[node_uuid]
            self._to_observe.pop(service_name, None)

        logger.debug("Removed service '%s' from scheduler", service_name)

    async def get_stack_status(self, node_uuid: NodeID) -> RunningDynamicServiceDetails:
        """

        raises DynamicSidecarNotFoundError
        """
        if node_uuid not in self._inverse_search_mapping:
            raise DynamicSidecarNotFoundError(node_uuid)
        service_name = self._inverse_search_mapping[node_uuid]

        scheduler_data: SchedulerData = self._to_observe[service_name]
        return await _scheduler_utils.get_stack_status_from_scheduler_data(
            scheduler_data
        )

    async def retrieve_service_inputs(
        self, node_uuid: NodeID, port_keys: list[str]
    ) -> RetrieveDataOutEnveloped:
        """Pulls data from input ports for the service"""
        if node_uuid not in self._inverse_search_mapping:
            raise DynamicSidecarNotFoundError(node_uuid)

        service_name = self._inverse_search_mapping[node_uuid]
        scheduler_data: SchedulerData = self._to_observe[service_name]
        dynamic_sidecar_endpoint: AnyHttpUrl = scheduler_data.endpoint
        sidecars_client: SidecarsClient = get_sidecars_client(self.app, node_uuid)

        transferred_bytes = await sidecars_client.pull_service_input_ports(
            dynamic_sidecar_endpoint, port_keys
        )

        if scheduler_data.restart_policy == RestartPolicy.ON_INPUTS_DOWNLOADED:
            logger.info("Will restart containers")
            await sidecars_client.restart_containers(dynamic_sidecar_endpoint)

        return RetrieveDataOutEnveloped.from_transferred_bytes(transferred_bytes)

    async def attach_project_network(
        self, node_id: NodeID, project_network: str, network_alias: DockerNetworkAlias
    ) -> None:
        if node_id not in self._inverse_search_mapping:
            return

        service_name = self._inverse_search_mapping[node_id]
        scheduler_data = self._to_observe[service_name]

        sidecars_client: SidecarsClient = get_sidecars_client(self.app, node_id)

        await sidecars_client.attach_service_containers_to_project_network(
            dynamic_sidecar_endpoint=scheduler_data.endpoint,
            dynamic_sidecar_network_name=scheduler_data.dynamic_sidecar_network_name,
            project_network=project_network,
            project_id=scheduler_data.project_id,
            network_alias=network_alias,
        )

    async def detach_project_network(
        self, node_id: NodeID, project_network: str
    ) -> None:
        if node_id not in self._inverse_search_mapping:
            return

        service_name = self._inverse_search_mapping[node_id]
        scheduler_data = self._to_observe[service_name]

        sidecars_client: SidecarsClient = get_sidecars_client(self.app, node_id)

        await sidecars_client.detach_service_containers_from_project_network(
            dynamic_sidecar_endpoint=scheduler_data.endpoint,
            project_network=project_network,
            project_id=scheduler_data.project_id,
        )

    async def restart_containers(self, node_uuid: NodeID) -> None:
        """Restarts containers without saving or restoring the state or I/O ports"""
        if node_uuid not in self._inverse_search_mapping:
            raise DynamicSidecarNotFoundError(node_uuid)

        service_name: ServiceName = self._inverse_search_mapping[node_uuid]
        scheduler_data: SchedulerData = self._to_observe[service_name]

        sidecars_client: SidecarsClient = get_sidecars_client(self.app, node_uuid)

        await sidecars_client.restart_containers(scheduler_data.endpoint)

    def _enqueue_observation_from_service_name(self, service_name: str) -> None:
        self._trigger_observation_queue.put_nowait(service_name)

    def __create_observation_task(
        self,
        dynamic_sidecar_settings: DynamicSidecarSettings,
        dynamic_scheduler: DynamicServicesSchedulerSettings,
        service_name: ServiceName,
    ) -> asyncio.Task:
        scheduler_data: SchedulerData = self._to_observe[service_name]
        observation_task = asyncio.create_task(
            observing_single_service(
                scheduler=self,
                service_name=service_name,
                scheduler_data=scheduler_data,
                dynamic_sidecar_settings=dynamic_sidecar_settings,
                dynamic_scheduler=dynamic_scheduler,
            ),
            name=f"{__name__}.observe_{service_name}",
        )
        observation_task.add_done_callback(
            functools.partial(
                lambda s, _: self._service_observation_task.pop(s, None),
                service_name,
            )
        )
        logger.debug("created %s for %s", f"{observation_task=}", f"{service_name=}")
        return observation_task

    async def _run_trigger_observation_queue_task(self) -> None:
        """generates events at regular time interval"""
        dynamic_sidecar_settings: DynamicSidecarSettings = (
            self.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )
        dynamic_scheduler: DynamicServicesSchedulerSettings = (
            self.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
        )

        service_name: ServiceName
        while service_name := await self._trigger_observation_queue.get():
            logger.info("Handling observation for %s", service_name)

            if service_name not in self._to_observe:
                logger.warning(
                    "%s is missing from list of services to observe", f"{service_name=}"
                )
                continue

            if self._service_observation_task.get(service_name) is None:
                logger.info("Create observation task for service %s", service_name)
                self._service_observation_task[
                    service_name
                ] = self.__create_observation_task(
                    dynamic_sidecar_settings, dynamic_scheduler, service_name
                )

        logger.info("Scheduler 'trigger observation queue task' was shut down")

    async def _run_scheduler_task(self) -> None:
        settings: DynamicServicesSchedulerSettings = (
            self.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
        )
        logger.debug(
            "dynamic-sidecars observation interval %s",
            settings.DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL_SECONDS,
        )

        while self._keep_running:
            logger.debug("Observing dynamic-sidecars %s", list(self._to_observe.keys()))

            try:
                # prevent access to self._to_observe
                async with self._lock:
                    for service_name in self._to_observe:
                        self._enqueue_observation_from_service_name(service_name)
            except asyncio.CancelledError:  # pragma: no cover
                logger.info("Stopped dynamic scheduler")
                raise
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    "Unexpected error while scheduling sidecars observation"
                )

            await sleep(settings.DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL_SECONDS)
            self._observation_counter += 1
