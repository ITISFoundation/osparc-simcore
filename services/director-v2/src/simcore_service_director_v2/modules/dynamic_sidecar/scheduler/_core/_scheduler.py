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
import functools
import logging
from asyncio import sleep
from contextlib import suppress
from dataclasses import dataclass
from typing import Optional, Union

from models_library.basic_types import PortInt
from models_library.projects import ProjectID
from models_library.projects_networks import DockerNetworkAlias
from models_library.projects_nodes_io import NodeID
from models_library.service_settings_labels import RestartPolicy, SimcoreServiceLabels
from models_library.users import UserID
from pydantic import AnyHttpUrl
from servicelib.fastapi.long_running_tasks.client import ProgressCallback
from servicelib.fastapi.long_running_tasks.server import TaskProgress

from .....core.settings import DynamicServicesSchedulerSettings, DynamicSidecarSettings
from .....models.domains.dynamic_services import (
    DynamicServiceCreate,
    RetrieveDataOutEnveloped,
)
from .....models.schemas.dynamic_services import (
    DynamicSidecarStatus,
    RunningDynamicServiceDetails,
    SchedulerData,
)
from ...api_client import DynamicSidecarClient, get_dynamic_sidecar_client
from ...docker_api import (
    get_dynamic_sidecar_state,
    get_dynamic_sidecars_to_observe,
    remove_pending_volume_removal_services,
    update_scheduler_data_label,
)
from ...docker_states import ServiceState, extract_containers_minimum_statuses
from ...errors import (
    DockerServiceNotFoundError,
    DynamicSidecarError,
    DynamicSidecarNotFoundError,
)
from .._abc import SchedulerPublicInterface
from ._events_utils import (
    service_push_outputs,
    service_remove_containers,
    service_remove_sidecar_proxy_docker_networks_and_volumes,
    service_save_state,
)
from ._observer import observing_single_service
from ._scheduler_mixin import SchedulerInternalsMixin

logger = logging.getLogger(__name__)


_DISABLED_MARK = object()


@dataclass
class Scheduler(SchedulerInternalsMixin, SchedulerPublicInterface):
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
        progress_callback: Optional[ProgressCallback] = None,
    ) -> None:
        dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(
            self.app
        )
        await service_push_outputs(
            app=self.app,
            node_uuid=node_uuid,
            dynamic_sidecar_client=dynamic_sidecar_client,
            progress_callback=progress_callback,
        )

    async def remove_service_containers(
        self, node_uuid: NodeID, progress_callback: Optional[ProgressCallback] = None
    ) -> None:
        dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(
            self.app
        )
        await service_remove_containers(
            app=self.app,
            node_uuid=node_uuid,
            dynamic_sidecar_client=dynamic_sidecar_client,
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
        self, node_uuid: NodeID, progress_callback: Optional[ProgressCallback] = None
    ) -> None:
        dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(
            self.app
        )
        await service_save_state(
            app=self.app,
            node_uuid=node_uuid,
            dynamic_sidecar_client=dynamic_sidecar_client,
            progress_callback=progress_callback,
        )

    async def add_service(
        self,
        service: DynamicServiceCreate,
        simcore_service_labels: SimcoreServiceLabels,
        port: PortInt,
        request_dns: str,
        request_scheme: str,
    ) -> None:
        """Invoked before the service is started"""
        scheduler_data = SchedulerData.from_http_request(
            service=service,
            simcore_service_labels=simcore_service_labels,
            port=port,
            request_dns=request_dns,
            request_scheme=request_scheme,
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
                raise DynamicSidecarError(
                    "node_uuids at a global level collided. A running "
                    f"service for node {scheduler_data.node_uuid} already exists. "
                    "Please checkout other projects which may have this issue."
                )

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
        user_id: Optional[UserID] = None,
        project_id: Optional[ProjectID] = None,
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
        can_save: Optional[bool],
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
            current.dynamic_sidecar.service_removal_state.mark_to_remove(can_save)
            await update_scheduler_data_label(current)

            # cancel current observation task
            if service_name in self._service_observation_task:
                service_task: Optional[
                    Union[asyncio.Task, object]
                ] = self._service_observation_task[service_name]
                if isinstance(service_task, asyncio.Task):
                    service_task.cancel()

                    async def _await_task(task: asyncio.Task) -> None:
                        await task

                    with suppress(asyncio.CancelledError):
                        try:
                            await asyncio.wait_for(
                                _await_task(service_task), timeout=10
                            )
                        except asyncio.TimeoutError:
                            pass

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
                return

            del self._to_observe[service_name]
            del self._inverse_search_mapping[node_uuid]

        logger.debug("Removed service '%s' from scheduler", service_name)

    async def get_stack_status(self, node_uuid: NodeID) -> RunningDynamicServiceDetails:
        # pylint: disable=too-many-return-statements
        """

        raises DynamicSidecarNotFoundError
        """
        if node_uuid not in self._inverse_search_mapping:
            raise DynamicSidecarNotFoundError(node_uuid)
        service_name = self._inverse_search_mapping[node_uuid]

        scheduler_data: SchedulerData = self._to_observe[service_name]

        # check if there was an error picked up by the scheduler
        # and marked this service as failed
        if scheduler_data.dynamic_sidecar.status.current != DynamicSidecarStatus.OK:
            return RunningDynamicServiceDetails.from_scheduler_data(
                node_uuid=node_uuid,
                scheduler_data=scheduler_data,
                service_state=ServiceState.FAILED,
                service_message=scheduler_data.dynamic_sidecar.status.info,
            )

        # is the service stopping?
        if scheduler_data.dynamic_sidecar.service_removal_state.can_remove:
            return RunningDynamicServiceDetails.from_scheduler_data(
                node_uuid=node_uuid,
                scheduler_data=scheduler_data,
                service_state=ServiceState.STOPPING,
                service_message=scheduler_data.dynamic_sidecar.status.info,
            )

        # the service should be either running or starting
        try:
            sidecar_state, sidecar_message = await get_dynamic_sidecar_state(
                # the service_name is unique and will not collide with other names
                # it can be used in place of the service_id here, as the docker API accepts both
                service_id=scheduler_data.service_name
            )
        except DockerServiceNotFoundError:
            # in this case, the service is starting, so state is pending
            return RunningDynamicServiceDetails.from_scheduler_data(
                node_uuid=node_uuid,
                scheduler_data=scheduler_data,
                service_state=ServiceState.PENDING,
                service_message=scheduler_data.dynamic_sidecar.status.info,
            )

        # while the dynamic-sidecar state is not RUNNING report it's state
        if sidecar_state != ServiceState.RUNNING:
            return RunningDynamicServiceDetails.from_scheduler_data(
                node_uuid=node_uuid,
                scheduler_data=scheduler_data,
                service_state=sidecar_state,
                service_message=sidecar_message,
            )

        # NOTE: This will be repeatedly called until the
        # user services are effectively started

        # wait for containers to start
        if len(scheduler_data.dynamic_sidecar.containers_inspect) == 0:
            # marks status as waiting for containers
            return RunningDynamicServiceDetails.from_scheduler_data(
                node_uuid=node_uuid,
                scheduler_data=scheduler_data,
                service_state=ServiceState.STARTING,
                service_message="",
            )

        # compute composed containers states
        container_state, container_message = extract_containers_minimum_statuses(
            scheduler_data.dynamic_sidecar.containers_inspect
        )
        return RunningDynamicServiceDetails.from_scheduler_data(
            node_uuid=node_uuid,
            scheduler_data=scheduler_data,
            service_state=container_state,
            service_message=container_message,
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
        dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(
            self.app
        )

        transferred_bytes = await dynamic_sidecar_client.pull_service_input_ports(
            dynamic_sidecar_endpoint, port_keys
        )

        if scheduler_data.restart_policy == RestartPolicy.ON_INPUTS_DOWNLOADED:
            logger.info("Will restart containers")
            await dynamic_sidecar_client.restart_containers(dynamic_sidecar_endpoint)

        return RetrieveDataOutEnveloped.from_transferred_bytes(transferred_bytes)

    async def attach_project_network(
        self, node_id: NodeID, project_network: str, network_alias: DockerNetworkAlias
    ) -> None:
        if node_id not in self._inverse_search_mapping:
            return

        service_name = self._inverse_search_mapping[node_id]
        scheduler_data = self._to_observe[service_name]

        dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(
            self.app
        )

        await dynamic_sidecar_client.attach_service_containers_to_project_network(
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

        dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(
            self.app
        )

        await dynamic_sidecar_client.detach_service_containers_from_project_network(
            dynamic_sidecar_endpoint=scheduler_data.endpoint,
            project_network=project_network,
            project_id=scheduler_data.project_id,
        )

    async def restart_containers(self, node_uuid: NodeID) -> None:
        """Restarts containers without saving or restoring the state or I/O ports"""
        if node_uuid not in self._inverse_search_mapping:
            raise DynamicSidecarNotFoundError(node_uuid)

        service_name = self._inverse_search_mapping[node_uuid]
        scheduler_data: SchedulerData = self._to_observe[service_name]

        dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(
            self.app
        )

        await dynamic_sidecar_client.restart_containers(scheduler_data.endpoint)

    def _enqueue_observation_from_service_name(self, service_name: str) -> None:
        self._trigger_observation_queue.put_nowait(service_name)

    def __create_observation_task(
        self,
        dynamic_sidecar_settings: DynamicSidecarSettings,
        dynamic_scheduler: DynamicServicesSchedulerSettings,
        service_name: str,
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

        service_name: str
        while service_name := await self._trigger_observation_queue.get():
            logger.info("Handling observation for %s", service_name)

            if service_name not in self._to_observe:
                logger.warning(
                    "%s is missing from list of services to observe", f"{service_name=}"
                )
                continue

            if self._service_observation_task.get(service_name) is None:
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

    async def _discover_running_services(self) -> None:
        """discover all services which were started before and add them to the scheduler"""
        dynamic_sidecar_settings: DynamicSidecarSettings = (
            self.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )
        services_to_observe: list[
            SchedulerData
        ] = await get_dynamic_sidecars_to_observe(dynamic_sidecar_settings)

        logger.info(
            "The following services need to be observed: %s", services_to_observe
        )

        for scheduler_data in services_to_observe:
            await self._add_service(scheduler_data)

    async def _cleanup_volume_removal_services(self) -> None:
        settings: DynamicServicesSchedulerSettings = (
            self.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
        )
        dynamic_sidecar_settings: DynamicSidecarSettings = (
            self.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )

        logger.debug(
            "dynamic-sidecars cleanup pending volume removal services every %s seconds",
            settings.DIRECTOR_V2_DYNAMIC_SCHEDULER_PENDING_VOLUME_REMOVAL_INTERVAL_S,
        )
        while await asyncio.sleep(
            settings.DIRECTOR_V2_DYNAMIC_SCHEDULER_PENDING_VOLUME_REMOVAL_INTERVAL_S,
            True,
        ):
            logger.debug("Removing pending volume removal services...")

            try:
                await remove_pending_volume_removal_services(dynamic_sidecar_settings)
            except asyncio.CancelledError:
                logger.info("Stopped pending volume removal services task")
                raise
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    "Unexpected error while cleaning up pending volume removal services"
                )
