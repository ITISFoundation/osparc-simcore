from models_library.projects_nodes_io import NodeID
from pydantic import BaseModel

from ..domains.comp_tasks import Image


class TaskIn(BaseModel):
    node_id: NodeID
    runtime_requirements: str

    @classmethod
    def from_node_image(cls, node_id: NodeID, node_image: Image) -> "TaskIn":
        # NOTE: to keep compatibility the queues are currently defined as .cpu, .gpu, .mpi.
        reqs = []
        if node_image.requires_gpu:
            reqs.append("gpu")
        if node_image.requires_mpi:
            reqs.append("mpi")
        req = ":".join(reqs)

        return cls(node_id=node_id, runtime_requirements=req or "cpu")
