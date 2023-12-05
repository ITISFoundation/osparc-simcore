from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.projects_nodes_io import NodeID

from ...services.director_v2 import DirectorV2Client
from ._dependencies import get_director_v2_client

router = APIRouter()


@router.get("/{node_id}", response_model=DynamicServiceGet)
async def get_status(
    node_id: NodeID,
    director_v2_client: Annotated[DirectorV2Client, Depends(get_director_v2_client)],
) -> DynamicServiceGet:
    return await director_v2_client.get_status(node_id)
