import logging

from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.agent.errors import (
    NoServiceVolumesFoundRPCError,
)

from ...services.volumes_manager import VolumesManager

_logger = logging.getLogger(__name__)

router = RPCRouter()


@router.expose(reraise_if_error_type=(NoServiceVolumesFoundRPCError,))
async def remove_volumes_without_backup_for_service(
    app: FastAPI, *, node_id: NodeID
) -> None:
    with log_context(_logger, logging.INFO, f"removing volumes for service: {node_id}"):
        await VolumesManager.get_from_app_state(app).remove_service_volumes(node_id)


@router.expose()
async def backup_and_remove_volumes_for_all_services(app: FastAPI) -> None:
    with log_context(_logger, logging.INFO, "removing all service volumes from node"):
        await VolumesManager.get_from_app_state(app).remove_all_volumes()
