from pydantic import BaseModel, ConfigDict

from ..api_schemas_directorv2 import clusters as directorv2_clusters
from ..clusters import ClusterID
from ._base import InputSchema, OutputSchema


class ClusterPathParams(BaseModel):
    cluster_id: ClusterID
    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
    )


class ClusterGet(directorv2_clusters.ClusterGet):
    model_config = OutputSchema.model_config


class ClusterCreate(directorv2_clusters.ClusterCreate):
    model_config = InputSchema.model_config


class ClusterPatch(directorv2_clusters.ClusterPatch):
    model_config = InputSchema.model_config


class ClusterPing(directorv2_clusters.ClusterPing):
    model_config = InputSchema.model_config


class ClusterDetails(directorv2_clusters.ClusterDetails):
    model_config = OutputSchema.model_config
