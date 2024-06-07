from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    RPCDynamicServiceCreate,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.errors import (
    ServiceWaitingForManualInterventionError,
    ServiceWasNotFoundError,
)

from ...core.settings import ApplicationSettings
from ...services.director_v2 import DirectorV2Client
from ...services.service_tracker import set_request_as_running, set_request_as_stopped

router = RPCRouter()


@router.expose()
async def get_service_status(
    app: FastAPI, *, node_id: NodeID
) -> NodeGet | DynamicServiceGet | NodeGetIdle:
    director_v2_client = DirectorV2Client.get_from_app_state(app)
    return await director_v2_client.get_status(node_id)


@router.expose()
async def run_dynamic_service(
    app: FastAPI, *, rpc_dynamic_service_create: RPCDynamicServiceCreate
) -> NodeGet | DynamicServiceGet:
    director_v2_client = DirectorV2Client.get_from_app_state(app)
    result = await director_v2_client.run_dynamic_service(rpc_dynamic_service_create)

    await set_request_as_running(app, rpc_dynamic_service_create)
    return result


@router.expose(
    reraise_if_error_type=(
        ServiceWaitingForManualInterventionError,
        ServiceWasNotFoundError,
    )
)
async def stop_dynamic_service(
    app: FastAPI, *, rpc_dynamic_service_stop: RPCDynamicServiceStop
) -> NodeGet | DynamicServiceGet:
    director_v2_client = DirectorV2Client.get_from_app_state(app)
    settings: ApplicationSettings = app.state.settings
    result = await director_v2_client.stop_dynamic_service(
        node_id=rpc_dynamic_service_stop.node_id,
        simcore_user_agent=rpc_dynamic_service_stop.simcore_user_agent,
        save_state=rpc_dynamic_service_stop.save_state,
        timeout=settings.DYNAMIC_SCHEDULER_STOP_SERVICE_TIMEOUT,
    )

    await set_request_as_stopped(
        app,
        user_id=rpc_dynamic_service_stop.user_id,
        project_id=rpc_dynamic_service_stop.project_id,
        node_id=rpc_dynamic_service_stop.node_id,
    )
    return result
