from pydantic import BaseModel, Extra

from ..api_schemas_directorv2 import clusters
from ..clusters import ClusterID
from ._base import InputSchema, OutputSchema


class ClusterPathParams(BaseModel):
    cluster_id: ClusterID

    class Config:
        allow_population_by_field_name = True
        extra = Extra.forbid


class ClusterGet(clusters.ClusterGet):
    class Config(OutputSchema.Config):
        ...


class ClusterCreate(clusters.ClusterCreate):
    class Config(InputSchema.Config):
        ...


class ClusterPatch(clusters.ClusterPatch):
    class Config(InputSchema.Config):
        ...


class ClusterPing(clusters.ClusterPing):
    class Config(InputSchema.Config):
        ...


class ClusterDetails(clusters.ClusterDetails):
    class Config(OutputSchema.Config):
        ...
