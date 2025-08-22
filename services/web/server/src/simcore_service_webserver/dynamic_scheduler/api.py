import logging
from contextlib import AsyncExitStack
from functools import partial

from aiohttp import web
from models_library.api_schemas_directorv2.dynamic_services import (
    DynamicServiceGet,
    GetProjectInactivityResponse,
    RetrieveDataOutEnveloped,
)
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.api_schemas_webserver.projects_nodes import (
    NodeGet,
    NodeGetIdle,
    NodeGetUnknown,
)
from models_library.progress_bar import ProgressReport
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_messages import ProgressRabbitMessageProject, ProgressType
from models_library.services import ServicePortKey
from models_library.users import UserID
from pydantic import NonNegativeInt
from servicelib.progress_bar import ProgressBarData
from servicelib.rabbitmq import RabbitMQClient, RPCServerError
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler import services
from servicelib.utils import logged_gather

from ..rabbitmq import get_rabbitmq_client, get_rabbitmq_rpc_client
from .settings import DynamicSchedulerSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


async def list_dynamic_services(
    app: web.Application,
    *,
    user_id: UserID | None = None,
    project_id: ProjectID | None = None,
) -> list[DynamicServiceGet]:
    """
    Returns:
        list of currently running dynamic services
    """
    return await services.list_tracked_dynamic_services(
        get_rabbitmq_rpc_client(app), user_id=user_id, project_id=project_id
    )


async def get_dynamic_service(
    app: web.Application, *, node_id: NodeID
) -> NodeGetIdle | NodeGetUnknown | DynamicServiceGet | NodeGet:
    try:
        return await services.get_service_status(
            get_rabbitmq_rpc_client(app), node_id=node_id
        )
    except RPCServerError as e:
        _logger.debug("Responding state unknown. Received error: %s", e)
        return NodeGetUnknown.from_node_id(node_id)


async def run_dynamic_service(
    app: web.Application, *, dynamic_service_start: DynamicServiceStart
) -> DynamicServiceGet | NodeGet:
    return await services.run_dynamic_service(
        get_rabbitmq_rpc_client(app),
        dynamic_service_start=dynamic_service_start,
    )


async def stop_dynamic_service(
    app: web.Application,
    *,
    dynamic_service_stop: DynamicServiceStop,
    progress: ProgressBarData | None = None,
) -> None:
    async with AsyncExitStack() as stack:
        if progress:
            await stack.enter_async_context(progress)

        settings: DynamicSchedulerSettings = get_plugin_settings(app)
        await services.stop_dynamic_service(
            get_rabbitmq_rpc_client(app),
            dynamic_service_stop=dynamic_service_stop,
            timeout_s=int(
                settings.DYNAMIC_SCHEDULER_STOP_SERVICE_TIMEOUT.total_seconds()
            ),
        )


async def _post_progress_message(
    rabbitmq_client: RabbitMQClient,
    user_id: UserID,
    project_id: ProjectID,
    report: ProgressReport,
) -> None:
    progress_message = ProgressRabbitMessageProject(
        user_id=user_id,
        project_id=project_id,
        progress_type=ProgressType.PROJECT_CLOSING,
        report=report,
    )

    await rabbitmq_client.publish(progress_message.channel_name, progress_message)


async def stop_dynamic_services_in_project(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    simcore_user_agent: str,
    save_state: bool,
) -> None:
    """Stops all dynamic services in the project"""
    running_dynamic_services = await list_dynamic_services(
        app, user_id=user_id, project_id=project_id
    )

    async with AsyncExitStack() as stack:
        progress_bar = await stack.enter_async_context(
            ProgressBarData(
                num_steps=len(running_dynamic_services),
                progress_report_cb=partial(
                    _post_progress_message,
                    get_rabbitmq_client(app),
                    user_id,
                    project_id,
                ),
                description="stopping services",
            )
        )

        services_to_stop = [
            stop_dynamic_service(
                app=app,
                dynamic_service_stop=DynamicServiceStop(
                    user_id=user_id,
                    project_id=service.project_id,
                    node_id=service.node_uuid,
                    simcore_user_agent=simcore_user_agent,
                    save_state=save_state,
                ),
                progress=progress_bar.sub_progress(
                    1, description=f"{service.node_uuid}"
                ),
            )
            for service in running_dynamic_services
        ]

        await logged_gather(*services_to_stop)


async def get_project_inactivity(
    app: web.Application,
    *,
    project_id: ProjectID,
    max_inactivity_seconds: NonNegativeInt,
) -> GetProjectInactivityResponse:
    return await services.get_project_inactivity(
        get_rabbitmq_rpc_client(app),
        project_id=project_id,
        max_inactivity_seconds=max_inactivity_seconds,
    )


async def restart_user_services(app: web.Application, *, node_id: NodeID) -> None:
    """Restarts the user service(s) started by the the node_uuid's sidecar

    NOTE: this operation will NOT restart
    sidecar services (``dy-sidecar`` or ``dy-proxy`` services),
    but ONLY user services (the ones defined by the compose spec).
    """
    settings: DynamicSchedulerSettings = get_plugin_settings(app)
    await services.restart_user_services(
        get_rabbitmq_rpc_client(app),
        node_id=node_id,
        timeout_s=int(
            settings.DYNAMIC_SCHEDULER_RESTART_USER_SERVICES_TIMEOUT.total_seconds()
        ),
    )


async def retrieve_inputs(
    app: web.Application, node_id: NodeID, port_keys: list[ServicePortKey]
) -> RetrieveDataOutEnveloped:
    settings: DynamicSchedulerSettings = get_plugin_settings(app)
    return await services.retrieve_inputs(
        get_rabbitmq_rpc_client(app),
        node_id=node_id,
        port_keys=port_keys,
        timeout_s=int(
            settings.DYNAMIC_SCHEDULER_SERVICE_UPLOAD_DOWNLOAD_TIMEOUT.total_seconds()
        ),
    )


async def update_projects_networks(
    app: web.Application, *, project_id: ProjectID
) -> None:
    await services.update_projects_networks(
        get_rabbitmq_rpc_client(app), project_id=project_id
    )
