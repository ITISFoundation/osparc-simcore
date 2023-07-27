from pydantic import BaseModel, Extra

from ..api_schemas_directorv2 import clusters
from ..clusters import ClusterID
from ._base import InputSchema, OutputSchema


class ClusterPathParams(BaseModel):
    cluster_id: ClusterID

    class Config:
        allow_population_by_field_name = True
        extra = Extra.forbid


class ClusterGet(clusters.ClusterGet, OutputSchema):
    ...


class ClusterCreate(clusters.ClusterCreate, InputSchema):
    ...


class ClusterPatch(clusters.ClusterPatch, InputSchema):
    ...


class ClusterPing(clusters.ClusterPing, InputSchema):
    ...


class ClusterDetails(clusters.ClusterDetails, OutputSchema):
    ...
