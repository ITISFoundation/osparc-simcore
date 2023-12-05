from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.projects_nodes_io import NodeID
from servicelib.fastapi.http_client import AppStateMixin

from ._thin_client import DirectorV2ThinClient


class DirectorV2Client(AppStateMixin):
    app_state_name: str = "director_v2_client"

    def __init__(self, app: FastAPI) -> None:
        self.thin_client = DirectorV2ThinClient(app)

    async def get_status(self, node_id: NodeID) -> DynamicServiceGet:
        response = await self.thin_client.get_status(node_id)
        return DynamicServiceGet.parse_raw(response.text)


def setup_director_v2(app: FastAPI) -> None:
    public_client = DirectorV2Client(app)
    public_client.thin_client.attach_lifespan_to(app)
    public_client.set_to_app_state(app)
