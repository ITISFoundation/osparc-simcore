from typing import TypeAlias

from pydantic import BaseModel, ByteSize, ConfigDict, Field

from ..resource_tracker import HardwareInfo, PricingInfo
from ..services import ServicePortKey
from ..services_resources import ServiceResourcesDict
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

    model_config = ConfigDict()


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
    pricing_info: PricingInfo | None = Field(
        default=None,
        description="contains pricing information (ex. pricing plan and unit ids)",
    )
    hardware_info: HardwareInfo | None = Field(
        default=None,
        description="contains harware information (ex. aws_ec2_instances)",
    )
    model_config = ConfigDict()


DynamicServiceGet: TypeAlias = RunningDynamicServiceDetails


class GetProjectInactivityResponse(BaseModel):
    is_inactive: bool
