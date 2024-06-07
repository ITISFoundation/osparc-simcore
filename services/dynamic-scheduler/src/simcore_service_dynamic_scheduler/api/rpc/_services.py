from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
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

router = RPCRouter()


@router.expose()
async def get_service_status(
    app: FastAPI, *, node_id: NodeID
) -> NodeGet | DynamicServiceGet | NodeGetIdle:
    director_v2_client = DirectorV2Client.get_from_app_state(app)
    return await director_v2_client.get_status(node_id)


@router.expose()
async def run_dynamic_service(
    app: FastAPI, *, dynamic_service_start: DynamicServiceStart
) -> NodeGet | DynamicServiceGet:
    director_v2_client = DirectorV2Client.get_from_app_state(app)
    return await director_v2_client.run_dynamic_service(dynamic_service_start)


@router.expose(
    reraise_if_error_type=(
        ServiceWaitingForManualInterventionError,
        ServiceWasNotFoundError,
    )
)
async def stop_dynamic_service(
    app: FastAPI, *, dynamic_service_stop: DynamicServiceStop
) -> NodeGet | DynamicServiceGet:
    director_v2_client = DirectorV2Client.get_from_app_state(app)
    settings: ApplicationSettings = app.state.settings
    return await director_v2_client.stop_dynamic_service(
        node_id=dynamic_service_stop.node_id,
        simcore_user_agent=dynamic_service_stop.simcore_user_agent,
        save_state=dynamic_service_stop.save_state,
        timeout=settings.DYNAMIC_SCHEDULER_STOP_SERVICE_TIMEOUT,
    )
