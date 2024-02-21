from models_library.projects_nodes_io import NodeID
from pydantic import BaseModel


class ServiceNoMoreCredits(BaseModel):
    node_id: NodeID
