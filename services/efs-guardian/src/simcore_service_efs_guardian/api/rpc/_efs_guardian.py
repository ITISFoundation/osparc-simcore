from pathlib import Path

from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from servicelib.rabbitmq import RPCRouter

from ...services.efs_manager_setup import get_efs_manager

router = RPCRouter()


@router.expose(reraise_if_error_type=())
async def create_project_specific_data_dir(
    app: FastAPI, *, project_id: ProjectID, node_id: NodeID, storage_directory_name: str
) -> Path:
    _efs_manager = get_efs_manager(app)

    return await _efs_manager.create_project_specific_data_dir(
        project_id=project_id,
        node_id=node_id,
        storage_directory_name=storage_directory_name,
    )
