from typing import Dict, Optional

from models_library.users import GroupID
from pydantic import BaseModel, Extra, Field, validator
from pydantic.networks import HttpUrl
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
                },
                {
                    "id": 432546,
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


class ClusterPatch(ClusterBase):
    name: Optional[str]
    description: Optional[str]
    type: Optional[ClusterType]
    owner: Optional[GroupID]
    thumbnail: Optional[HttpUrl]
    access_rights: Optional[Dict[GroupID, ClusterAccessRights]] = Field(
        alias="accessRights"
    )
