from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from servicelib.rabbitmq import RPCRouter
from simcore_service_agent.services.volume_manager import get_volume_manager

router = RPCRouter()


@router.expose()
async def remove_volumes_without_backup_for_service(
    app: FastAPI, *, node_id: NodeID
) -> None:
    await get_volume_manager(app).remove_service_volumes(node_id)


@router.expose()
async def backup_and_remove_volumes_for_all_services(app: FastAPI) -> None:
    await get_volume_manager(app).remove_all_volumes()
