from typing import Annotated, Any, TypeAlias

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    NonNegativeFloat,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic.networks import AnyUrl
from pydantic.types import ByteSize, PositiveFloat

from ..clusters import (
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
from ..generics import DictModel
from ..users import GroupID


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
    @model_validator(mode="before")
    @classmethod
    def ensure_negative_value_is_zero(cls, values: dict[str, Any]):
        # dasks adds/remove resource values and sometimes
        # they end up being negative instead of 0
        for res_key, res_value in values.items():
            if res_value < 0:
                values[res_key] = 0
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

    @field_validator("workers", mode="before")
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
    access_rights: Annotated[
        dict[GroupID, ClusterAccessRights],
        Field(
            alias="accessRights",
            default_factory=dict,
            json_schema_extra={"default": {}},
        ),
    ]

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        json_schema_extra={
            # NOTE: make openapi-specs fails because
            # Cluster.model_config.json_schema_extra is raises `TypeError: unhashable type: 'ClusterAccessRights'`
        },
    )

    @model_validator(mode="before")
    @classmethod
    def ensure_access_rights_converted(cls, values):
        if "access_rights" in values:
            access_rights = values.pop("access_rights")
            values["accessRights"] = access_rights
        return values


class ClusterDetailsGet(ClusterDetails):
    ...


class ClusterCreate(BaseCluster):
    owner: GroupID | None = None  # type: ignore[assignment]
    authentication: ExternalClusterAuthentication = Field(discriminator="type")
    access_rights: dict[GroupID, ClusterAccessRights] = Field(
        alias="accessRights", default_factory=dict
    )

    model_config = ConfigDict(
        json_schema_extra={
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
                        154: CLUSTER_ADMIN_RIGHTS.model_dump(),  # type:ignore[dict-item]
                        12: CLUSTER_MANAGER_RIGHTS.model_dump(),  # type:ignore[dict-item]
                        7899: CLUSTER_USER_RIGHTS.model_dump(),  # type:ignore[dict-item]
                    },
                },
            ]
        }
    )

    @field_validator("thumbnail", mode="before")
    @classmethod
    def set_default_thumbnail_if_empty(cls, v, info: ValidationInfo):
        if v is None:
            cluster_type = info.data["type"]
            default_thumbnails = {
                ClusterTypeInModel.AWS.value: "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Amazon_Web_Services_Logo.svg/250px-Amazon_Web_Services_Logo.svg.png",
                ClusterTypeInModel.ON_PREMISE.value: "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/Crystal_Clear_app_network_local.png/120px-Crystal_Clear_app_network_local.png",
                ClusterTypeInModel.ON_DEMAND.value: "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Amazon_Web_Services_Logo.svg/250px-Amazon_Web_Services_Logo.svg.png",
            }
            return default_thumbnails[cluster_type]
        return v


class ClusterPatch(BaseCluster):
    name: str | None = None  # type: ignore[assignment]
    description: str | None = None
    type: ClusterTypeInModel | None = None  # type: ignore[assignment]
    owner: GroupID | None = None  # type: ignore[assignment]
    thumbnail: HttpUrl | None = None
    endpoint: AnyUrl | None = None  # type: ignore[assignment]
    authentication: ExternalClusterAuthentication | None = Field(None, discriminator="type")  # type: ignore[assignment]
    access_rights: dict[GroupID, ClusterAccessRights] | None = Field(  # type: ignore[assignment]
        default=None, alias="accessRights"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Changing the name of my cluster",
                },
                {
                    "description": "adding a better description",
                },
                {
                    "accessRights": {
                        154: CLUSTER_ADMIN_RIGHTS.model_dump(),  # type:ignore[dict-item]
                        12: CLUSTER_MANAGER_RIGHTS.model_dump(),  # type:ignore[dict-item]
                        7899: CLUSTER_USER_RIGHTS.model_dump(),  # type:ignore[dict-item]
                    },
                },
            ]
        }
    )


class ClusterPing(BaseModel):
    endpoint: AnyHttpUrl
    authentication: ClusterAuthentication = Field(
        ...,
        description="Dask gateway authentication",
        discriminator="type",
    )
