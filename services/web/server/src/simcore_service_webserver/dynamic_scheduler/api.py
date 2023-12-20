from contextlib import AsyncExitStack
from functools import partial

from aiohttp import web
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    RPCDynamicServiceCreate,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_messages import ProgressRabbitMessageProject, ProgressType
from pydantic.types import NonNegativeFloat, PositiveInt
from servicelib.progress_bar import ProgressBarData
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler import services
from servicelib.utils import logged_gather

from ..director_v2.api import list_dynamic_services
from ..rabbitmq import get_rabbitmq_client, get_rabbitmq_rpc_client


async def get_dynamic_service(
    app: web.Application, *, node_id: NodeID
) -> NodeGetIdle | DynamicServiceGet | NodeGet:
    return await services.get_service_status(
        get_rabbitmq_rpc_client(app), node_id=node_id
    )


async def run_dynamic_service(
    app: web.Application, *, rpc_dynamic_service_create: RPCDynamicServiceCreate
) -> DynamicServiceGet | NodeGet:
    return await services.run_dynamic_service(
        get_rabbitmq_rpc_client(app),
        rpc_dynamic_service_create=rpc_dynamic_service_create,
    )


async def stop_dynamic_service(
    app: web.Application,
    *,
    node_id: NodeID,
    simcore_user_agent: str,
    save_state: bool,
    progress: ProgressBarData | None = None,
) -> None:
    async with AsyncExitStack() as stack:
        if progress:
            await stack.enter_async_context(progress)

        await services.stop_dynamic_service(
            get_rabbitmq_rpc_client(app),
            node_id=node_id,
            simcore_user_agent=simcore_user_agent,
            save_state=save_state,
        )


async def _post_progress_message(
    rabbitmq_client: RabbitMQClient,
    user_id: PositiveInt,
    project_id: str,
    progress_value: NonNegativeFloat,
) -> None:
    progress_message = ProgressRabbitMessageProject(
        user_id=user_id,
        project_id=ProjectID(project_id),
        progress_type=ProgressType.PROJECT_CLOSING,
        progress=progress_value,
    )

    await rabbitmq_client.publish(progress_message.channel_name, progress_message)


async def stop_dynamic_services_in_project(
    app: web.Application,
    *,
    user_id: PositiveInt,
    project_id: str,
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
            )
        )

        services_to_stop = [
            stop_dynamic_service(
                app=app,
                node_id=service["service_uuid"],
                simcore_user_agent=simcore_user_agent,
                save_state=save_state,
                progress=progress_bar.sub_progress(1),
            )
            for service in running_dynamic_services
        ]

        await logged_gather(*services_to_stop)
