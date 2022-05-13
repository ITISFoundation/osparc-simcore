from typing import List

from models_library.services import PropertyName
from models_library.services_resources import ServiceResources
from pydantic import BaseModel, ByteSize, Field

from ..schemas.dynamic_services import RunningDynamicServiceDetails, ServiceDetails


class RetrieveDataIn(BaseModel):
    port_keys: List[PropertyName] = Field(
        ..., description="The port keys to retrieve data from"
    )


class RetrieveDataOut(BaseModel):
    size_bytes: ByteSize = Field(
        ..., description="The amount of data transferred by the retrieve call"
    )


class RetrieveDataOutEnveloped(BaseModel):
    data: RetrieveDataOut

    @classmethod
    def from_transferred_bytes(
        cls, transferred_bytes: int
    ) -> "RetrieveDataOutEnveloped":
        return cls(data=RetrieveDataOut(size_bytes=transferred_bytes))

    class Config:
        schema_extra = {"examples": [{"data": {"size_bytes": 42}}]}


class DynamicServiceCreate(ServiceDetails):
    service_resources: ServiceResources

    class Config:
        schema_extra = {
            "example": {
                "key": "simcore/services/dynamic/3dviewer",
                "version": "2.4.5",
                "user_id": 234,
                "project_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                "node_uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                "basepath": "/x/75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                "service_resources": ServiceResources.Config.schema_extra["examples"][
                    0
                ],
            }
        }


DynamicServiceOut = RunningDynamicServiceDetails
