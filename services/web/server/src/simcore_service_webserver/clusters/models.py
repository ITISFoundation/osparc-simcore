from typing import Dict, Optional

from models_library.users import GroupID
from pydantic import BaseModel, Extra, Field, validator
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


class Cluster(BaseModel):
    name: str = Field(..., description="The human readable name of the cluster")
    description: Optional[str] = None
    type: ClusterType
    owner: GroupID
    access_rights: Dict[GroupID, ClusterAccessRights] = Field(default_factory=dict)

    class Config:
        extra = Extra.forbid
        use_enum_values = True
        schema_extra = {
            "examples": [
                {
                    "name": "My awesome cluster",
                    "type": ClusterType.ON_PREMISE,
                    "owner": 12,
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
