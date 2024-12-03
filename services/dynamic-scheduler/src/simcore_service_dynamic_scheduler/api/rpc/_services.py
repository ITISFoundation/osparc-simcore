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

from ...services import scheduler

router = RPCRouter()


@router.expose()
async def get_service_status(
    app: FastAPI, *, node_id: NodeID
) -> NodeGet | DynamicServiceGet | NodeGetIdle:
    return await scheduler.get_service_status(app, node_id=node_id)


@router.expose()
async def run_dynamic_service(
    app: FastAPI, *, dynamic_service_start: DynamicServiceStart
) -> NodeGet | DynamicServiceGet:
    return await scheduler.run_dynamic_service(
        app, dynamic_service_start=dynamic_service_start
    )


@router.expose(
    reraise_if_error_type=(
        ServiceWaitingForManualInterventionError,
        ServiceWasNotFoundError,
    )
)
async def stop_dynamic_service(
    app: FastAPI, *, dynamic_service_stop: DynamicServiceStop
) -> None:
    return await scheduler.stop_dynamic_service(
        app, dynamic_service_stop=dynamic_service_stop
    )
