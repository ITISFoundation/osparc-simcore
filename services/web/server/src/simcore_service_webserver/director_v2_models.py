from typing import Dict, Optional

from models_library.clusters import (
    CLUSTER_ADMIN_RIGHTS,
    CLUSTER_MANAGER_RIGHTS,
    CLUSTER_USER_RIGHTS,
    BaseCluster,
    ClusterAccessRights,
    ExternalClusterAuthentication,
)
from models_library.users import GroupID
from pydantic import AnyHttpUrl, BaseModel, Field, validator
from pydantic.networks import AnyUrl, HttpUrl
from simcore_postgres_database.models.clusters import ClusterType


class ClusterPing(BaseModel):
    endpoint: AnyHttpUrl
    authentication: ExternalClusterAuthentication


class ClusterCreate(BaseCluster):
    owner: Optional[GroupID]
    authentication: ExternalClusterAuthentication
    access_rights: Dict[GroupID, ClusterAccessRights] = Field(
        alias="accessRights", default_factory=dict
    )

    @validator("thumbnail", always=True, pre=True)
    @classmethod
    def set_default_thumbnail_if_empty(cls, v, values):
        if v is None:
            cluster_type = values["type"]
            default_thumbnails = {
                ClusterType.AWS.value: "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Amazon_Web_Services_Logo.svg/250px-Amazon_Web_Services_Logo.svg.png",
                ClusterType.ON_PREMISE.value: "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/Crystal_Clear_app_network_local.png/120px-Crystal_Clear_app_network_local.png",
            }
            return default_thumbnails[cluster_type]
        return v

    class Config(BaseCluster.Config):
        schema_extra = {
            "examples": [
                {
                    "name": "My awesome cluster",
                    "type": ClusterType.ON_PREMISE,
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
                    "type": ClusterType.AWS,
                    "owner": 154,
                    "endpoint": "https://registry.osparc-development.fake.dev",
                    "authentication": {
                        "type": "simple",
                        "username": "someuser",
                        "password": "somepassword",
                    },
                    "access_rights": {
                        154: CLUSTER_ADMIN_RIGHTS,
                        12: CLUSTER_MANAGER_RIGHTS,
                        7899: CLUSTER_USER_RIGHTS,
                    },
                },
            ]
        }


class ClusterPatch(BaseCluster):
    name: Optional[str]
    description: Optional[str]
    type: Optional[ClusterType]
    owner: Optional[GroupID]
    thumbnail: Optional[HttpUrl]
    endpoint: Optional[AnyUrl]
    authentication: Optional[ExternalClusterAuthentication]
    access_rights: Optional[Dict[GroupID, ClusterAccessRights]] = Field(
        alias="accessRights"
    )
