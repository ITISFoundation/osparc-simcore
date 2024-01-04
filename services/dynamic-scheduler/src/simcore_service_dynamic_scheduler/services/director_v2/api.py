from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    RPCDynamicServiceCreate,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID

from ...core.settings import ApplicationSettings
from ._public_client import DirectorV2Client


async def get_service_status(
    app: FastAPI, *, node_id: NodeID
) -> NodeGet | DynamicServiceGet | NodeGetIdle:
    director_v2_client = DirectorV2Client.get_from_app_state(app)
    return await director_v2_client.get_status(node_id)


async def run_dynamic_service(
    app: FastAPI, *, rpc_dynamic_service_create: RPCDynamicServiceCreate
) -> NodeGet | DynamicServiceGet:
    director_v2_client = DirectorV2Client.get_from_app_state(app)
    return await director_v2_client.run_dynamic_service(rpc_dynamic_service_create)


async def stop_dynamic_service(
    app: FastAPI, *, node_id: NodeID, simcore_user_agent: str, save_state: bool
) -> None:
    director_v2_client = DirectorV2Client.get_from_app_state(app)
    settings: ApplicationSettings = app.state.settings
    return await director_v2_client.stop_dynamic_service(
        node_id=node_id,
        simcore_user_agent=simcore_user_agent,
        save_state=save_state,
        timeout=settings.DYNAMIC_SCHEDULER_STOP_SERVICE_TIMEOUT,
    )
