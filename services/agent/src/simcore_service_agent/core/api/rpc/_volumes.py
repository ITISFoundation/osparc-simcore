import logging

from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RPCRouter
from simcore_service_agent.services.volumes_manager import get_volumes_manager

_logger = logging.getLogger(__name__)

router = RPCRouter()


@router.expose()
async def remove_volumes_without_backup_for_service(
    app: FastAPI, *, node_id: NodeID
) -> None:
    with log_context(_logger, logging.INFO, f"removing volumes for service: {node_id}"):
        await get_volumes_manager(app).remove_service_volumes(node_id)


@router.expose()
async def backup_and_remove_volumes_for_all_services(app: FastAPI) -> None:
    with log_context(_logger, logging.INFO, "removing all service volumes from node"):
        await get_volumes_manager(app).remove_all_volumes()
