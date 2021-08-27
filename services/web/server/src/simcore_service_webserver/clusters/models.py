from datetime import datetime
from typing import Dict, Optional

from models_library.users import GroupID
from pydantic import BaseModel, Field
from simcore_postgres_database.models.clusters import ClusterType


class ClusterAccessRights(BaseModel):
    read: bool
    write: bool
    delete: bool


class Cluster(BaseModel):
    name: str
    description: Optional[str] = None
    type: ClusterType
    owner: GroupID
    access_rights: Dict[GroupID, ClusterAccessRights]


class ClusterAtDB(Cluster):
    id: int
    created: datetime
    modified: datetime
