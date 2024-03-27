# pylint: disable=relative-beyond-top-level

import logging
from typing import Any

from fastapi import FastAPI
from servicelib.fastapi.http_client_thin import BaseHttpClientError

from .....core.dynamic_services_settings.scheduler import (
    DynamicServicesSchedulerSettings,
)
from .....models.dynamic_services_scheduler import (
    DockerContainerInspect,
    DockerStatus,
    DynamicSidecarStatus,
    SchedulerData,
)
from ...api_client import get_dynamic_sidecar_service_health, get_sidecars_client
from ...errors import UnexpectedContainerStatusError
from ._abc import DynamicSchedulerEvent
from ._event_create_sidecars import CreateSidecars
from ._events_user_services import create_user_services
from ._events_utils import (
    are_all_user_services_containers_running,
    attach_project_networks,
    attempt_pod_removal_and_data_saving,
    parse_containers_inspect,
    prepare_services_environment,
    wait_for_sidecar_api,
)

_logger = logging.getLogger(__name__)


_EXPECTED_STATUSES: set[DockerStatus] = {DockerStatus.created, DockerStatus.running}


class WaitForSidecarAPI(DynamicSchedulerEvent):
    """
    Waits for the sidecar to start and respond to API calls.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        assert app  # nose
        return (
            scheduler_data.dynamic_sidecar.was_dynamic_sidecar_started
            and not scheduler_data.dynamic_sidecar.is_healthy
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        await wait_for_sidecar_api(app, scheduler_data)


class UpdateHealth(DynamicSchedulerEvent):
    """
    Updates the health of the sidecar.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        assert app  # nose
        return scheduler_data.dynamic_sidecar.was_dynamic_sidecar_started

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        scheduler_data.dynamic_sidecar.is_ready = (
            await get_dynamic_sidecar_service_health(app, scheduler_data)
        )


class GetStatus(DynamicSchedulerEvent):
    """
    Triggered after CreateSidecars.action() runs.
    Requests the dynamic-sidecar for all "self started running containers"
    docker inspect result.
    Parses and stores the result for usage by other components.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        assert app  # nose
        return (
            scheduler_data.dynamic_sidecar.status.current == DynamicSidecarStatus.OK
            and scheduler_data.dynamic_sidecar.is_ready
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        sidecars_client = await get_sidecars_client(app, scheduler_data.node_uuid)
        dynamic_sidecar_endpoint = scheduler_data.endpoint
        dynamic_sidecars_scheduler_settings: DynamicServicesSchedulerSettings = (
            app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
        )
        scheduler_data.dynamic_sidecar.inspect_error_handler.delay_for = (
            dynamic_sidecars_scheduler_settings.DYNAMIC_SIDECAR_CLIENT_REQUEST_TIMEOUT_S
        )

        try:
            containers_inspect: dict[str, Any] = (
                await sidecars_client.containers_inspect(dynamic_sidecar_endpoint)
            )
        except BaseHttpClientError as e:
            were_service_containers_previously_present = (
                len(scheduler_data.dynamic_sidecar.containers_inspect) > 0
            )
            if were_service_containers_previously_present:
                # Containers disappeared after they were started.
                # for now just mark as error and remove the sidecar

                # NOTE: Network performance can degrade and the sidecar might
                # be temporarily unreachable.
                # Adding a delay between when the error is first seen and when the
                # error is raised to avoid random shutdowns of dynamic-sidecar services.
                scheduler_data.dynamic_sidecar.inspect_error_handler.try_to_raise(e)
            return

        scheduler_data.dynamic_sidecar.inspect_error_handler.else_reset()

        # parse and store data from container
        scheduler_data.dynamic_sidecar.containers_inspect = parse_containers_inspect(
            containers_inspect
        )

        # NOTE: All containers are expected to be either created or running.
        # Extra containers (utilities like forward proxies) can also be present here,
        # these also are expected to be created or running.

        containers_with_error: list[DockerContainerInspect] = [
            container_inspect
            for container_inspect in scheduler_data.dynamic_sidecar.containers_inspect
            if container_inspect.status not in _EXPECTED_STATUSES
        ]

        if len(containers_with_error) > 0:
            raise UnexpectedContainerStatusError(
                containers_with_error=containers_with_error
            )


class PrepareServicesEnvironment(DynamicSchedulerEvent):
    """
    Triggered when the dynamic-sidecar is responding to http requests.
    This step runs before CreateUserServices.

    Sets up the environment on the host required by the service.
    - restores service state
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        assert app  # nose
        return (
            scheduler_data.dynamic_sidecar.status.current == DynamicSidecarStatus.OK
            and scheduler_data.dynamic_sidecar.is_ready
            and not scheduler_data.dynamic_sidecar.is_service_environment_ready
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        await prepare_services_environment(app, scheduler_data)


class CreateUserServices(DynamicSchedulerEvent):
    """
    Triggered when the the environment was prepared.
    The docker compose spec for the service is assembled.
    The dynamic-sidecar is asked to start a service for that service spec.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        assert app  # nose
        return (
            scheduler_data.dynamic_sidecar.is_service_environment_ready
            and not scheduler_data.dynamic_sidecar.compose_spec_submitted
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        await create_user_services(app, scheduler_data)


class AttachProjectsNetworks(DynamicSchedulerEvent):
    """
    Triggers after CreateUserServices and when all started containers are running.

    Will attach all started containers to the project network based on what
    is saved in the project_network db entry.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        assert app  # nose
        return (
            scheduler_data.dynamic_sidecar.were_containers_created
            and not scheduler_data.dynamic_sidecar.is_project_network_attached
            and are_all_user_services_containers_running(
                scheduler_data.dynamic_sidecar.containers_inspect
            )
        )

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        await attach_project_networks(app, scheduler_data)


class RemoveUserCreatedServices(DynamicSchedulerEvent):
    """
    Triggered when the service is marked for removal.

    The state of the service will be stored. If dynamic-sidecar
        is not reachable a warning is logged.
    The outputs of the service wil be pushed. If dynamic-sidecar
        is not reachable a warning is logged.
    The dynamic-sidecar together with spawned containers
    and dedicated network will be removed.
    The scheduler will no longer track the service.
    """

    @classmethod
    async def will_trigger(cls, app: FastAPI, scheduler_data: SchedulerData) -> bool:
        assert app  # nose
        return scheduler_data.dynamic_sidecar.service_removal_state.can_remove

    @classmethod
    async def action(cls, app: FastAPI, scheduler_data: SchedulerData) -> None:
        await attempt_pod_removal_and_data_saving(app, scheduler_data)


# register all handlers defined in this module here
# A list is essential to guarantee execution order
REGISTERED_EVENTS: list[type[DynamicSchedulerEvent]] = [
    CreateSidecars,
    WaitForSidecarAPI,
    UpdateHealth,
    GetStatus,
    PrepareServicesEnvironment,
    CreateUserServices,
    AttachProjectsNetworks,
    RemoveUserCreatedServices,
]
