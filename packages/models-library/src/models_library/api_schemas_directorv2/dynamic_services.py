from typing import Annotated, TypeAlias

from pydantic import AnyHttpUrl, BaseModel, ByteSize, ConfigDict, Field
from pydantic.config import JsonDict

from ..resource_tracker import HardwareInfo, PricingInfo
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

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"data": {"size_bytes": 42}}]}
    )


class DynamicServiceCreate(ServiceDetails):
    service_resources: ServiceResourcesDict

    product_name: Annotated[str, Field(..., description="Current product name")]
    product_api_base_url: Annotated[
        AnyHttpUrl,
        Field(
            ...,
            description="Base url of the product",
        ),
    ]
    can_save: Annotated[
        bool, Field(..., description="the service data must be saved when closing")
    ]
    wallet_info: Annotated[
        WalletInfo | None,
        Field(
            default=None,
            description="contains information about the wallet used to bill the running service",
        ),
    ]
    pricing_info: Annotated[
        PricingInfo | None,
        Field(
            default=None,
            description="contains pricing information (ex. pricing plan and unit ids)",
        ),
    ]
    hardware_info: Annotated[
        HardwareInfo | None,
        Field(
            default=None,
            description="contains hardware information (ex. aws_ec2_instances)",
        ),
    ]

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "example": {
                    "key": "simcore/services/dynamic/3dviewer",
                    "version": "2.4.5",
                    "user_id": 234,
                    "project_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                    "node_uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "basepath": "/x/75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                    "product_name": "osparc",
                    "product_api_base_url": "https://api.local",
                    "can_save": True,
                    "service_resources": ServiceResourcesDictHelpers.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                    "wallet_info": WalletInfo.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                    "pricing_info": PricingInfo.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                    "hardware_info": HardwareInfo.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                }
            }
        )

    model_config = ConfigDict(
        json_schema_extra=_update_json_schema_extra,
    )


DynamicServiceGet: TypeAlias = RunningDynamicServiceDetails


class GetProjectInactivityResponse(BaseModel):
    is_inactive: bool

    model_config = ConfigDict(json_schema_extra={"example": {"is_inactive": "false"}})
