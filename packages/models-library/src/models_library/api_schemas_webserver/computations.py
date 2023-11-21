from pydantic import BaseModel

from ..clusters import ClusterID


class ComputationStart(BaseModel):
    force_restart: bool = False
    cluster_id: ClusterID = 0
    subgraph: set[str] = set()


__all__: tuple[str, ...] = ("ComputationStart",)
