from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    RPCDynamicServiceCreate,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.errors import (
    ServiceWaitingForManualInterventionError,
    ServiceWasNotFoundError,
)

from ...services.services_tracker import api as services_tracker_api

router = RPCRouter()


@router.expose()
async def get_service_status(
    app: FastAPI, *, node_id: NodeID
) -> NodeGet | DynamicServiceGet | NodeGetIdle:
    return await services_tracker_api.get_service_status(
        services_tracker_api.get_services_tracker(app), node_id=node_id
    )


@router.expose()
async def run_dynamic_service(
    app: FastAPI, *, rpc_dynamic_service_create: RPCDynamicServiceCreate
) -> NodeGet | DynamicServiceGet:
    return await services_tracker_api.run_dynamic_service(
        services_tracker_api.get_services_tracker(app),
        rpc_dynamic_service_create=rpc_dynamic_service_create,
    )


@router.expose(
    reraise_if_error_type=(
        ServiceWaitingForManualInterventionError,
        ServiceWasNotFoundError,
    )
)
async def stop_dynamic_service(
    app: FastAPI,
    *,
    node_id: NodeID,
    simcore_user_agent: str,
    save_state: bool,
    user_id: UserID,
) -> None:
    await services_tracker_api.stop_dynamic_service(
        services_tracker_api.get_services_tracker(app),
        node_id=node_id,
        simcore_user_agent=simcore_user_agent,
        save_state=save_state,
        user_id=user_id,
    )
