from typing import Any, ClassVar, TypeAlias

from pydantic import BaseModel, ByteSize, Field

from ..services import ServicePortKey
from ..services_resources import ServiceResourcesDict, ServiceResourcesDictHelpers
from ..wallets import WalletInfo
from .dynamic_services_service import RunningDynamicServiceDetails, ServiceDetails


class RetrieveDataIn(BaseModel):
    port_keys: list[ServicePortKey] = Field(
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
        return cls(data=RetrieveDataOut(size_bytes=ByteSize(transferred_bytes)))

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [{"data": {"size_bytes": 42}}]
        }


class DynamicServiceCreate(ServiceDetails):
    service_resources: ServiceResourcesDict

    product_name: str = Field(..., description="Current product name")
    can_save: bool = Field(
        ..., description="the service data must be saved when closing"
    )
    wallet_info: WalletInfo | None = Field(
        default=None,
        description="contains information about the wallet used to bill the running service",
    )

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "key": "simcore/services/dynamic/3dviewer",
                "version": "2.4.5",
                "user_id": 234,
                "project_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                "node_uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                "basepath": "/x/75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                "product_name": "osparc",
                "can_save": True,
                "service_resources": ServiceResourcesDictHelpers.Config.schema_extra[
                    "examples"
                ][0],
                "wallet_info": WalletInfo.Config.schema_extra["examples"][0],
            }
        }


DynamicServiceGet: TypeAlias = RunningDynamicServiceDetails
