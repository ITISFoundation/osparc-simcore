from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import (
    DynamicServiceGet,
    RetrieveDataOutEnveloped,
)
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServicePortKey
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.errors import (
    ServiceWaitingForManualInterventionError,
    ServiceWasNotFoundError,
)

from ...services import scheduler_interface

router = RPCRouter()


@router.expose()
async def get_service_status(
    app: FastAPI, *, node_id: NodeID
) -> NodeGet | DynamicServiceGet | NodeGetIdle:
    return await scheduler_interface.get_service_status(app, node_id=node_id)


@router.expose()
async def run_dynamic_service(
    app: FastAPI, *, dynamic_service_start: DynamicServiceStart
) -> NodeGet | DynamicServiceGet:
    return await scheduler_interface.run_dynamic_service(
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
    return await scheduler_interface.stop_dynamic_service(
        app, dynamic_service_stop=dynamic_service_stop
    )


@router.expose()
async def retrieve_inputs(
    app: FastAPI, *, node_id: NodeID, port_keys: list[ServicePortKey]
) -> RetrieveDataOutEnveloped:
    return await scheduler_interface.retrieve_inputs(
        app, node_id=node_id, port_keys=port_keys
    )
