from typing import Any, Dict, Optional

from models_library.users import GroupID
from pydantic import BaseModel, Extra, Field, validator
from pydantic.networks import AnyUrl, HttpUrl
from pydantic.types import PositiveInt
from simcore_postgres_database.models.clusters import ClusterType


class ClusterAccessRights(BaseModel):
    read: bool = Field(..., description="allows to run pipelines on that cluster")
    write: bool = Field(..., description="allows to modify the cluster")
    delete: bool = Field(..., description="allows to delete a cluster")

    class Config:
        extra = Extra.forbid


CLUSTER_ADMIN_RIGHTS = ClusterAccessRights(read=True, write=True, delete=True)
CLUSTER_MANAGER_RIGHTS = ClusterAccessRights(read=True, write=True, delete=False)
CLUSTER_USER_RIGHTS = ClusterAccessRights(read=True, write=False, delete=False)
CLUSTER_NO_RIGHTS = ClusterAccessRights(read=False, write=False, delete=False)


class ClusterBase(BaseModel):
    name: str = Field(..., description="The human readable name of the cluster")
    description: Optional[str] = None
    type: ClusterType
    owner: GroupID
    thumbnail: Optional[HttpUrl] = Field(
        None,
        description="url to the image describing this cluster",
        examples=["https://placeimg.com/171/96/tech/grayscale/?0.jpg"],
    )
    endpoint: AnyUrl
    authentication: Dict[str, Any] = Field(
        description="For now it is undefined how the authentication is going to be used"
    )
    access_rights: Dict[GroupID, ClusterAccessRights] = Field(default_factory=dict)

    class Config:
        extra = Extra.forbid
        use_enum_values = True


class Cluster(ClusterBase):
    id: PositiveInt = Field(..., description="The cluster ID")

    class Config(ClusterBase.Config):
        schema_extra = {
            "examples": [
                {
                    "id": 432,
                    "name": "My awesome cluster",
                    "type": ClusterType.ON_PREMISE,
                    "owner": 12,
                    "endpoint": "registry.osparc-development.fake.dev",
                    "authentication": {
                        "simple": {"username": "someuser", "password": "somepassword"}
                    },
                },
                {
                    "id": 432546,
                    "name": "My AWS cluster",
                    "description": "a AWS cluster administered by me",
                    "type": ClusterType.AWS,
                    "owner": 154,
                    "endpoint": "registry.osparc-development.fake.dev",
                    "authentication": {
                        "simple": {"username": "someuser", "password": "somepassword"}
                    },
                    "access_rights": {
                        154: CLUSTER_ADMIN_RIGHTS,
                        12: CLUSTER_MANAGER_RIGHTS,
                        7899: CLUSTER_USER_RIGHTS,
                    },
                },
            ]
        }

    @validator("access_rights", always=True, pre=True)
    @classmethod
    def check_owner_has_access_rights(cls, v, values):
        owner_gid = values["owner"]
        # check owner is in the access rights, if not add it
        if owner_gid not in v:
            v[owner_gid] = CLUSTER_ADMIN_RIGHTS
        # check owner has full access
        if v[owner_gid] != CLUSTER_ADMIN_RIGHTS:
            raise ValueError("the cluster owner access rights are incorrectly set")
        return v

    @validator("authentication", always=True)
    @classmethod
    def authentication_is_one_of_gateway_authorized_ones(cls, v):
        if not isinstance(v, dict):
            raise ValueError(
                "the authentication value is not following simple, kerberos or jupyterhub authentication schemes"
            )
        POSSIBLE_KEYS = ["simple", "kerberos", "jupyterhub"]
        for authentication_type in POSSIBLE_KEYS:
            if authentication_type in v:
                if not isinstance(v[authentication_type], dict):
                    raise ValueError(
                        f"{authentication_type} authentication requires a dictionary"
                    )
                return v
        raise ValueError(
            "the authentication value is not following simple, kerberos or jupyterhub authentication schemes"
        )


class ClusterCreate(ClusterBase):
    owner: Optional[GroupID]

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

    class Config(ClusterBase.Config):
        schema_extra = {
            "examples": [
                {
                    "name": "My awesome cluster",
                    "type": ClusterType.ON_PREMISE,
                },
                {
                    "name": "My AWS cluster",
                    "description": "a AWS cluster administered by me",
                    "type": ClusterType.AWS,
                    "owner": 154,
                    "access_rights": {
                        154: CLUSTER_ADMIN_RIGHTS,
                        12: CLUSTER_MANAGER_RIGHTS,
                        7899: CLUSTER_USER_RIGHTS,
                    },
                },
            ]
        }


class ClusterPatch(ClusterBase):
    name: Optional[str]
    description: Optional[str]
    type: Optional[ClusterType]
    owner: Optional[GroupID]
    thumbnail: Optional[HttpUrl]
    access_rights: Optional[Dict[GroupID, ClusterAccessRights]] = Field(
        alias="accessRights"
    )
