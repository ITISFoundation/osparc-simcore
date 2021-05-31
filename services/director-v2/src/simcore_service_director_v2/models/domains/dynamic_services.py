from pathlib import Path
from typing import List

from models_library.projects import ProjectID
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID
from models_library.services import DYNAMIC_SERVICE_KEY_RE, VERSION_RE, PropertyName
from pydantic import BaseModel, Field

from ...models.schemas.constants import UserID


class RetrieveDataIn(BaseModel):
    port_keys: List[PropertyName] = Field(
        ..., description="The port keys to retrieve data from"
    )


class RetrieveDataOut(BaseModel):
    size_bytes: int = Field(
        ..., description="The amount of data transferred by the retrieve call"
    )


class RetrieveDataOutEnveloped(BaseModel):
    data: RetrieveDataOut


class DynamicServiceBase(BaseModel):
    user_id: UserID
    project_id: ProjectID
    service_key: str = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        regex=DYNAMIC_SERVICE_KEY_RE,
        examples=[
            "simcore/services/dynamic/3dviewer",
        ],
    )
    service_version: str = Field(
        ...,
        description="semantic version number of the node",
        regex=VERSION_RE,
        examples=["1.0.0", "0.0.1"],
    )
    service_uuid: NodeID
    service_basepath: Path = Field(
        ...,
        description="predefined path where the dynamic service should be served. If empty, the service shall use the root endpoint.",
    )

    class Config:
        schema_extra = {
            "examples": [
                {
                    "user_id": 234,
                    "project_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                    "service_key": "simcore/services/dynamic/3dviewer",
                    "service_version": "2.4.5",
                    "service_uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "service_basepath": "/x/75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                }
            ]
        }


class DynamicServiceCreate(DynamicServiceBase):
    pass


class DynamicServiceOut(DynamicServiceBase):
    pass
