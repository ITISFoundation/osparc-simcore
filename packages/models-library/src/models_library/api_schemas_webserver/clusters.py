from pydantic import BaseModel, ConfigDict

from ..api_schemas_directorv2 import clusters as directorv2_clusters
from ..clusters import ClusterID
from ._base import InputSchema, OutputSchema


class ClusterPathParams(BaseModel):
    cluster_id: ClusterID
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ClusterGet(directorv2_clusters.ClusterGet):
    # TODO[pydantic]: The `Config` class inherits from another class, please create the `model_config` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-config for more information.
    class Config(OutputSchema.Config):
        ...


class ClusterCreate(directorv2_clusters.ClusterCreate):
    # TODO[pydantic]: The `Config` class inherits from another class, please create the `model_config` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-config for more information.
    class Config(InputSchema.Config):
        ...


class ClusterPatch(directorv2_clusters.ClusterPatch):
    # TODO[pydantic]: The `Config` class inherits from another class, please create the `model_config` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-config for more information.
    class Config(InputSchema.Config):
        ...


class ClusterPing(directorv2_clusters.ClusterPing):
    # TODO[pydantic]: The `Config` class inherits from another class, please create the `model_config` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-config for more information.
    class Config(InputSchema.Config):
        ...


class ClusterDetails(directorv2_clusters.ClusterDetails):
    # TODO[pydantic]: The `Config` class inherits from another class, please create the `model_config` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-config for more information.
    class Config(OutputSchema.Config):
        ...
