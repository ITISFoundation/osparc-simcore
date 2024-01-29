from pydantic import BaseModel, ConfigDict, Field, validator
from pydantic.types import ByteSize, NonNegativeInt

from ..service_settings_labels import ContainerSpec


class ServiceBuildDetails(BaseModel):
    build_date: str
    vcs_ref: str
    vcs_url: str


class NodeRequirements(BaseModel):
    cpu: float = Field(
        ...,
        description="defines the required (maximum) CPU shares for running the services",
        alias="CPU",
        gt=0.0,
    )
    gpu: NonNegativeInt | None = Field(
        None,
        description="defines the required (maximum) GPU for running the services",
        alias="GPU",
    )
    ram: ByteSize = Field(
        ...,
        description="defines the required (maximum) amount of RAM for running the services",
        alias="RAM",
    )
    vram: ByteSize | None = Field(
        default=None,
        description="defines the required (maximum) amount of VRAM for running the services",
        alias="VRAM",
    )

    # TODO[pydantic]: We couldn't refactor the `validator`, please replace it by `field_validator` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-validators for more information.
    @validator("vram", "gpu", always=True, pre=True)
    @classmethod
    def check_0_is_none(cls, v):
        if v == 0:
            v = None
        return v

    model_config = ConfigDict()


class ServiceExtras(BaseModel):
    node_requirements: NodeRequirements
    service_build_details: ServiceBuildDetails | None = None
    container_spec: ContainerSpec | None = None
    model_config = ConfigDict()
