import logging

from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RPCRouter

from ...services.containers_manager import ContainersManager

_logger = logging.getLogger(__name__)

router = RPCRouter()


@router.expose()
async def force_container_cleanup(app: FastAPI, *, node_id: NodeID) -> None:
    with log_context(
        _logger, logging.INFO, f"removing all orphan container for {node_id=}"
    ):
        await ContainersManager.get_from_app_state(app).force_container_cleanup(node_id)
