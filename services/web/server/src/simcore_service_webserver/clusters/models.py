from typing import Any, Dict, Literal, Optional, Union

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


class BaseAuthentication(BaseModel):
    type: str

    class Config:
        extra = Extra.forbid


class SimpleAuthentication(BaseAuthentication):
    type: Literal["simple"] = "simple"
    username: str
    password: str


class KerberosAuthentication(BaseAuthentication):
    type: Literal["kerberos"] = "kerberos"
    # NOTE: the entries here still need to be defined


class JupyterHubTokenAuthentication(BaseAuthentication):
    type: Literal["jupyterhub"] = "jupyterhub"
    # NOTE: the entries here still need to be defined


ClusterAuthentication = Union[
    SimpleAuthentication, KerberosAuthentication, JupyterHubTokenAuthentication
]


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
    authentication: ClusterAuthentication = Field(
        ..., description="Dask gateway authentication"
    )
    access_rights: Dict[GroupID, ClusterAccessRights] = Field(default_factory=dict)

    class Config:
        extra = Extra.forbid
        use_enum_values = True

    def to_clusters_db(self, only_update: bool) -> Dict[str, Any]:
        db_model = self.dict(
            by_alias=True,
            exclude={"id", "access_rights"},
            exclude_unset=only_update,
            exclude_none=only_update,
        )
        return db_model


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
                    "endpoint": "https://registry.osparc-development.fake.dev",
                    "authentication": {
                        "type": "simple",
                        "username": "someuser",
                        "password": "somepassword",
                    },
                },
                {
                    "id": 432546,
                    "name": "My AWS cluster",
                    "description": "a AWS cluster administered by me",
                    "type": ClusterType.AWS,
                    "owner": 154,
                    "endpoint": "https://registry.osparc-development.fake.dev",
                    "authentication": {"type": "kerberos"},
                    "access_rights": {
                        154: CLUSTER_ADMIN_RIGHTS,
                        12: CLUSTER_MANAGER_RIGHTS,
                        7899: CLUSTER_USER_RIGHTS,
                    },
                },
                {
                    "id": 325436,
                    "name": "My AWS cluster",
                    "description": "a AWS cluster administered by me",
                    "type": ClusterType.AWS,
                    "owner": 2321,
                    "endpoint": "https://registry.osparc-development.fake2.dev",
                    "authentication": {"type": "jupyterhub"},
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


class ClusterPatch(ClusterBase):
    name: Optional[str]
    description: Optional[str]
    type: Optional[ClusterType]
    owner: Optional[GroupID]
    thumbnail: Optional[HttpUrl]
    endpoint: Optional[AnyUrl]
    authentication: Optional[ClusterAuthentication]
    access_rights: Optional[Dict[GroupID, ClusterAccessRights]] = Field(
        alias="accessRights"
    )
