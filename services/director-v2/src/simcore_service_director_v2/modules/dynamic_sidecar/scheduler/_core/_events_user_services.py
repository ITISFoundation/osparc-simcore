import logging

from fastapi import FastAPI
from models_library.api_schemas_long_running_tasks.base import ProgressPercent
from models_library.projects import ProjectAtDB
from models_library.projects_nodes_io import NodeIDStr
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services import ServiceKeyVersion, ServiceVersion
from models_library.services_creation import CreateServiceMetricsAdditionalParams
from pydantic import TypeAdapter
from servicelib.fastapi.long_running_tasks.client import TaskId
from tenacity import RetryError
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from .....core.dynamic_services_settings.scheduler import (
    DynamicServicesSchedulerSettings,
)
from .....models.dynamic_services_scheduler import SchedulerData
from .....modules.instrumentation import get_instrumentation, get_metrics_labels
from .....utils.db import get_repository
from ....db.repositories.groups_extra_properties import GroupsExtraPropertiesRepository
from ....db.repositories.projects import ProjectsRepository
from ....db.repositories.users import UsersRepository
from ....director_v0 import DirectorV0Client
from ...api_client import get_sidecars_client
from ...docker_compose_specs import assemble_spec
from ...errors import EntrypointContainerNotFoundError
from ._events_utils import get_director_v0_client

_logger = logging.getLogger(__name__)


async def submit_compose_sepc(app: FastAPI, scheduler_data: SchedulerData) -> None:
    _logger.debug(
        "Getting docker compose spec for service %s", scheduler_data.service_name
    )

    sidecars_client = await get_sidecars_client(app, scheduler_data.node_uuid)
    dynamic_sidecar_endpoint = scheduler_data.endpoint

    # check values have been set by previous step
    if (
        scheduler_data.dynamic_sidecar.dynamic_sidecar_id is None
        or scheduler_data.dynamic_sidecar.dynamic_sidecar_network_id is None
        or scheduler_data.dynamic_sidecar.swarm_network_id is None
        or scheduler_data.dynamic_sidecar.swarm_network_name is None
        or scheduler_data.proxy_admin_api_port is None
    ):
        msg = (
            "Did not expect None for any of the following: "
            f"{scheduler_data.dynamic_sidecar.dynamic_sidecar_id=} "
            f"{scheduler_data.dynamic_sidecar.dynamic_sidecar_network_id=} "
            f"{scheduler_data.dynamic_sidecar.swarm_network_id=} "
            f"{scheduler_data.dynamic_sidecar.swarm_network_name=} "
            f"{scheduler_data.proxy_admin_api_port=}"
        )
        raise ValueError(msg)

    # Starts dynamic SIDECAR -------------------------------------
    # creates a docker compose spec given the service key and tag
    # fetching project form DB and fetching user settings

    director_v0_client: DirectorV0Client = get_director_v0_client(app)
    simcore_service_labels: SimcoreServiceLabels = (
        await director_v0_client.get_service_labels(
            service=ServiceKeyVersion(
                key=scheduler_data.key, version=scheduler_data.version
            )
        )
    )

    groups_extra_properties = get_repository(app, GroupsExtraPropertiesRepository)
    assert scheduler_data.product_name is not None  # nosec
    allow_internet_access: bool = await groups_extra_properties.has_internet_access(
        user_id=scheduler_data.user_id, product_name=scheduler_data.product_name
    )

    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings = (
        app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
    )

    compose_spec: str = await assemble_spec(
        app=app,
        service_key=scheduler_data.key,
        service_version=scheduler_data.version,
        paths_mapping=scheduler_data.paths_mapping,
        compose_spec=scheduler_data.compose_spec,
        container_http_entry=scheduler_data.container_http_entry,
        dynamic_sidecar_network_name=scheduler_data.dynamic_sidecar_network_name,
        swarm_network_name=scheduler_data.dynamic_sidecar.swarm_network_name,
        service_resources=scheduler_data.service_resources,
        has_quota_support=dynamic_services_scheduler_settings.DYNAMIC_SIDECAR_ENABLE_VOLUME_LIMITS,
        simcore_service_labels=simcore_service_labels,
        allow_internet_access=allow_internet_access,
        product_name=scheduler_data.product_name,
        user_id=scheduler_data.user_id,
        project_id=scheduler_data.project_id,
        node_id=scheduler_data.node_uuid,
        simcore_user_agent=scheduler_data.request_simcore_user_agent,
        swarm_stack_name=dynamic_services_scheduler_settings.SWARM_STACK_NAME,
    )

    _logger.debug(
        "Submitting to %s it's compose-specs:\n%s",
        scheduler_data.service_name,
        compose_spec,
    )
    await sidecars_client.submit_docker_compose_spec(
        dynamic_sidecar_endpoint, compose_spec=compose_spec
    )
    scheduler_data.dynamic_sidecar.was_compose_spec_submitted = True


async def create_user_services(  # pylint: disable=too-many-statements
    app: FastAPI, scheduler_data: SchedulerData
) -> None:
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings = (
        app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
    )
    sidecars_client = await get_sidecars_client(app, scheduler_data.node_uuid)
    dynamic_sidecar_endpoint = scheduler_data.endpoint

    _logger.debug("Starting containers %s", scheduler_data.service_name)

    async def progress_create_containers(
        message: str, percent: ProgressPercent | None, task_id: TaskId
    ) -> None:
        _logger.debug("%s: %.2f %s", task_id, percent, message)

    # data from project
    projects_repository = get_repository(app, ProjectsRepository)
    project: ProjectAtDB = await projects_repository.get_project(
        project_id=scheduler_data.project_id
    )
    project_name = project.name
    node_name = project.workbench[NodeIDStr(scheduler_data.node_uuid)].label

    # data from user
    users_repository = get_repository(app, UsersRepository)
    user_email = await users_repository.get_user_email(scheduler_data.user_id)

    # Billing info
    wallet_id = None
    wallet_name = None
    pricing_plan_id = None
    pricing_unit_id = None
    pricing_unit_cost_id = None
    if scheduler_data.wallet_info:
        wallet_id = scheduler_data.wallet_info.wallet_id
        wallet_name = scheduler_data.wallet_info.wallet_name
        assert scheduler_data.pricing_info  # nosec
        pricing_plan_id = scheduler_data.pricing_info.pricing_plan_id
        pricing_unit_id = scheduler_data.pricing_info.pricing_unit_id
        pricing_unit_cost_id = scheduler_data.pricing_info.pricing_unit_cost_id

    metrics_params = CreateServiceMetricsAdditionalParams(
        wallet_id=wallet_id,
        wallet_name=wallet_name,
        pricing_plan_id=pricing_plan_id,
        pricing_unit_id=pricing_unit_id,
        pricing_unit_cost_id=pricing_unit_cost_id,
        product_name=scheduler_data.product_name,
        simcore_user_agent=scheduler_data.request_simcore_user_agent,
        user_email=user_email,
        project_name=project_name,
        node_name=node_name,
        service_key=scheduler_data.key,
        service_version=TypeAdapter(ServiceVersion).validate_python(scheduler_data.version),
        service_resources=scheduler_data.service_resources,
        service_additional_metadata={},
    )
    await sidecars_client.create_containers(
        dynamic_sidecar_endpoint,
        metrics_params,
        progress_create_containers,
    )

    # NOTE: when in READ ONLY mode disable the outputs watcher
    enable_outputs = scheduler_data.dynamic_sidecar.service_removal_state.can_save
    await sidecars_client.toggle_service_ports_io(
        dynamic_sidecar_endpoint, enable_outputs=enable_outputs, enable_inputs=True
    )

    # Starts PROXY -----------------------------------------------
    # The entrypoint container name was now computed
    # continue starting the proxy

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_delay(
                dynamic_services_scheduler_settings.DYNAMIC_SIDECAR_WAIT_FOR_CONTAINERS_TO_START
            ),
            wait=wait_fixed(1),
            before_sleep=before_sleep_log(_logger, logging.WARNING),
        ):
            with attempt:
                if scheduler_data.dynamic_sidecar.service_removal_state.was_removed:
                    # the service was removed while waiting for the operation to finish
                    _logger.warning(
                        "Stopping `get_entrypoint_container_name` operation. "
                        "Will no try to start the service."
                    )
                    return

                entrypoint_container = await sidecars_client.get_entrypoint_container_name(
                    dynamic_sidecar_endpoint=dynamic_sidecar_endpoint,
                    dynamic_sidecar_network_name=scheduler_data.dynamic_sidecar_network_name,
                )
                _logger.info(
                    "Fetched container entrypoint name %s", entrypoint_container
                )
    except RetryError as err:
        raise EntrypointContainerNotFoundError from err

    await sidecars_client.configure_proxy(
        proxy_endpoint=scheduler_data.get_proxy_endpoint,
        entrypoint_container_name=entrypoint_container,
        service_port=scheduler_data.service_port,
    )

    scheduler_data.dynamic_sidecar.were_containers_created = True

    # NOTE: user services are already in running state, meaning it is safe to pull inputs
    await sidecars_client.pull_service_input_ports(dynamic_sidecar_endpoint)

    start_duration = (
        scheduler_data.dynamic_sidecar.instrumentation.elapsed_since_start_request()
    )
    assert start_duration is not None  # nosec
    get_instrumentation(app).dynamic_sidecar_metrics.start_time_duration.labels(
        **get_metrics_labels(scheduler_data)
    ).observe(start_duration)

    _logger.info("Internal state after creating user services %s", scheduler_data)
