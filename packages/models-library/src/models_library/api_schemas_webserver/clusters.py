from pydantic import BaseModel, Extra

from ..api_schemas_directorv2 import clusters as directorv2_clusters
from ..clusters import ClusterID
from ._base import InputSchema, OutputSchema


class ClusterPathParams(BaseModel):
    cluster_id: ClusterID

    class Config:
        allow_population_by_field_name = True
        extra = Extra.forbid


class ClusterGet(directorv2_clusters.ClusterGet):
    class Config(OutputSchema.Config):
        ...


class ClusterCreate(directorv2_clusters.ClusterCreate):
    class Config(InputSchema.Config):
        ...


class ClusterPatch(directorv2_clusters.ClusterPatch):
    class Config(InputSchema.Config):
        ...


class ClusterPing(directorv2_clusters.ClusterPing):
    class Config(InputSchema.Config):
        ...


class ClusterDetails(directorv2_clusters.ClusterDetails):
    class Config(OutputSchema.Config):
        ...
