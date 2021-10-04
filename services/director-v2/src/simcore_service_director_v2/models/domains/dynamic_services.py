from typing import List

from models_library.services import PropertyName
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


DynamicServiceCreate = ServiceDetails
DynamicServiceOut = RunningDynamicServiceDetails
