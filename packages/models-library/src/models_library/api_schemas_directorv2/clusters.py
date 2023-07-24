from typing import Any, ClassVar, TypeAlias

from models_library.clusters import (
    CLUSTER_ADMIN_RIGHTS,
    CLUSTER_MANAGER_RIGHTS,
    CLUSTER_USER_RIGHTS,
    BaseCluster,
    Cluster,
    ClusterAccessRights,
    ClusterAuthentication,
    ClusterTypeInModel,
    ExternalClusterAuthentication,
)
from models_library.generics import DictModel
from models_library.users import GroupID
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    Field,
    HttpUrl,
    NonNegativeFloat,
    root_validator,
    validator,
)
from pydantic.networks import AnyUrl
from pydantic.types import ByteSize, PositiveFloat


class TaskCounts(BaseModel):
    error: int = 0
    memory: int = 0
    executing: int = 0


class WorkerMetrics(BaseModel):
    cpu: float = Field(..., description="consumed % of cpus")
    memory: ByteSize = Field(..., description="consumed memory")
    num_fds: int = Field(..., description="consumed file descriptors")
    task_counts: TaskCounts = Field(..., description="task details")


AvailableResources: TypeAlias = DictModel[str, PositiveFloat]


class UsedResources(DictModel[str, NonNegativeFloat]):
    @root_validator(pre=True)
    @classmethod
    def ensure_negative_value_is_zero(cls, values):
        # dasks adds/remove resource values and sometimes
        # they end up being negative instead of 0
        if v := values.get("__root__", {}):
            for res_key, res_value in v.items():
                if res_value < 0:
                    v[res_key] = 0
        return values


class Worker(BaseModel):
    id: str
    name: str
    resources: AvailableResources
    used_resources: UsedResources
    memory_limit: ByteSize
    metrics: WorkerMetrics


WorkersDict: TypeAlias = dict[AnyUrl, Worker]


class Scheduler(BaseModel):
    status: str = Field(..., description="The running status of the scheduler")
    workers: WorkersDict | None = Field(default_factory=dict)

    @validator("workers", pre=True, always=True)
    @classmethod
    def ensure_workers_is_empty_dict(cls, v):
        if v is None:
            return {}
        return v


class ClusterDetails(BaseModel):
    scheduler: Scheduler = Field(
        ...,
        description="This contains dask scheduler information given by the underlying dask library",
    )
    dashboard_link: AnyUrl = Field(
        ..., description="Link to this scheduler's dashboard"
    )


class ClusterGet(Cluster):
    access_rights: dict[GroupID, ClusterAccessRights] = Field(
        alias="accessRights", default_factory=dict
    )

    class Config(Cluster.Config):
        allow_population_by_field_name = True

    @root_validator(pre=True)
    @classmethod
    def ensure_access_rights_converted(cls, values):
        if "access_rights" in values:
            access_rights = values.pop("access_rights")
            values["accessRights"] = access_rights
        return values


class ClusterDetailsGet(ClusterDetails):
    ...


class ClusterCreate(BaseCluster):
    owner: GroupID | None
    authentication: ExternalClusterAuthentication
    access_rights: dict[GroupID, ClusterAccessRights] = Field(
        alias="accessRights", default_factory=dict
    )

    @validator("thumbnail", always=True, pre=True)
    @classmethod
    def set_default_thumbnail_if_empty(cls, v, values):
        if v is None:
            cluster_type = values["type"]
            default_thumbnails = {
                ClusterTypeInModel.AWS.value: "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Amazon_Web_Services_Logo.svg/250px-Amazon_Web_Services_Logo.svg.png",
                ClusterTypeInModel.ON_PREMISE.value: "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/Crystal_Clear_app_network_local.png/120px-Crystal_Clear_app_network_local.png",
            }
            return default_thumbnails[cluster_type]
        return v

    class Config(BaseCluster.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "name": "My awesome cluster",
                    "type": ClusterTypeInModel.ON_PREMISE,
                    "endpoint": "https://registry.osparc-development.fake.dev",
                    "authentication": {
                        "type": "simple",
                        "username": "someuser",
                        "password": "somepassword",
                    },
                },
                {
                    "name": "My AWS cluster",
                    "description": "a AWS cluster administered by me",
                    "type": ClusterTypeInModel.AWS,
                    "owner": 154,
                    "endpoint": "https://registry.osparc-development.fake.dev",
                    "authentication": {
                        "type": "simple",
                        "username": "someuser",
                        "password": "somepassword",
                    },
                    "accessRights": {
                        154: CLUSTER_ADMIN_RIGHTS,
                        12: CLUSTER_MANAGER_RIGHTS,
                        7899: CLUSTER_USER_RIGHTS,
                    },
                },
            ]
        }


class ClusterPatch(BaseCluster):
    name: str | None
    description: str | None
    type: ClusterTypeInModel | None
    owner: GroupID | None
    thumbnail: HttpUrl | None
    endpoint: AnyUrl | None
    authentication: ExternalClusterAuthentication | None
    access_rights: dict[GroupID, ClusterAccessRights] | None = Field(
        alias="accessRights"
    )

    class Config(BaseCluster.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "name": "Changing the name of my cluster",
                },
                {
                    "description": "adding a better description",
                },
                {
                    "accessRights": {
                        154: CLUSTER_ADMIN_RIGHTS,
                        12: CLUSTER_MANAGER_RIGHTS,
                        7899: CLUSTER_USER_RIGHTS,
                    },
                },
            ]
        }


class ClusterPing(BaseModel):
    endpoint: AnyHttpUrl
    authentication: ClusterAuthentication = Field(
        ..., description="Dask gateway authentication"
    )
