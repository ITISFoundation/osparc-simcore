from typing import List

from models_library.services import PropertyName
from pydantic import BaseModel, Field

from ..schemas.dynamic_services import DynamicServiceBase, DynamicServiceState


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


class DynamicServiceCreate(DynamicServiceBase):
    pass


class DynamicServiceOut(DynamicServiceState):
    pass
