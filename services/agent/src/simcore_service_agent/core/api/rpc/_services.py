from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose()
async def remove_volumes_for_service(app: FastAPI, *, node_id: NodeID) -> None:
    _ = app
    _ = node_id
    raise NotImplementedError
    return None
