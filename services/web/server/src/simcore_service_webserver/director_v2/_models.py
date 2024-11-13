from models_library.clusters import (
    CLUSTER_ADMIN_RIGHTS,
    CLUSTER_MANAGER_RIGHTS,
    CLUSTER_USER_RIGHTS,
    BaseCluster,
    ClusterAccessRights,
    ClusterTypeInModel,
    ExternalClusterAuthentication,
)
from models_library.users import GroupID
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator
from pydantic.networks import AnyUrl, HttpUrl
from simcore_postgres_database.models.clusters import ClusterType


class ClusterPing(BaseModel):
    endpoint: AnyHttpUrl
    authentication: ExternalClusterAuthentication


_DEFAULT_THUMBNAILS = {
    f"{ClusterTypeInModel.AWS}": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Amazon_Web_Services_Logo.svg/250px-Amazon_Web_Services_Logo.svg.png",
    f"{ClusterTypeInModel.ON_PREMISE}": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/Crystal_Clear_app_network_local.png/120px-Crystal_Clear_app_network_local.png",
}


class ClusterCreate(BaseCluster):
    owner: GroupID | None  # type: ignore[assignment]
    authentication: ExternalClusterAuthentication
    access_rights: dict[GroupID, ClusterAccessRights] = Field(
        alias="accessRights", default_factory=dict
    )

    @field_validator("thumbnail", mode="before")
    @classmethod
    def set_default_thumbnail_if_empty(cls, v, values):
        if v is None and (
            cluster_type := values.get("type", f"{ClusterTypeInModel.ON_PREMISE}")
        ):
            return _DEFAULT_THUMBNAILS[f"{cluster_type}"]
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "My awesome cluster",
                    "type": f"{ClusterType.ON_PREMISE}",  # can use also values from equivalent enum
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
                    "type": f"{ClusterType.AWS}",
                    "owner": 154,
                    "endpoint": "https://registry.osparc-development.fake.dev",
                    "authentication": {
                        "type": "simple",
                        "username": "someuser",
                        "password": "somepassword",
                    },
                    "access_rights": {
                        154: CLUSTER_ADMIN_RIGHTS.model_dump(),  # type:ignore[dict-item]
                        12: CLUSTER_MANAGER_RIGHTS.model_dump(),  # type:ignore[dict-item]
                        7899: CLUSTER_USER_RIGHTS.model_dump(),  # type:ignore[dict-item]
                    },
                },
            ]
        }
    )


class ClusterPatch(BaseCluster):
    name: str | None  # type: ignore[assignment]
    description: str | None
    type: ClusterType | None  # type: ignore[assignment]
    owner: GroupID | None  # type: ignore[assignment]
    thumbnail: HttpUrl | None
    endpoint: AnyUrl | None  # type: ignore[assignment]
    authentication: ExternalClusterAuthentication | None  # type: ignore[assignment]
    access_rights: dict[GroupID, ClusterAccessRights] | None = Field(  # type: ignore[assignment]
        alias="accessRights"
    )
