from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator
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
        validate_default=True,
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
        validate_default=True,
    )

    @field_validator("vram", "gpu", mode="before")
    @classmethod
    def check_0_is_none(cls, v):
        if v == 0:
            v = None
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"CPU": 1.0, "RAM": 4194304},
                {"CPU": 1.0, "GPU": 1, "RAM": 4194304},
                {
                    "CPU": 1.0,
                    "RAM": 4194304,
                },
            ]
        }
    )


class ServiceExtras(BaseModel):
    node_requirements: NodeRequirements
    service_build_details: ServiceBuildDetails | None = None
    container_spec: ContainerSpec | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"node_requirements": node_example}
                for node_example in NodeRequirements.model_config["json_schema_extra"][
                    "examples"
                ]  # type: ignore[index,union-attr]
            ]
            + [
                {
                    "node_requirements": node_example,
                    "service_build_details": {
                        "build_date": "2021-08-13T12:56:28Z",
                        "vcs_ref": "8251ade",
                        "vcs_url": "git@github.com:ITISFoundation/osparc-simcore.git",
                    },
                }
                for node_example in NodeRequirements.model_config["json_schema_extra"][
                    "examples"
                ]  # type: ignore[index,dict-item, union-attr]
            ]
            + [
                {
                    "node_requirements": node_example,
                    "service_build_details": {
                        "build_date": "2021-08-13T12:56:28Z",
                        "vcs_ref": "8251ade",
                        "vcs_url": "git@github.com:ITISFoundation/osparc-simcore.git",
                    },
                    "container_spec": {"Command": ["run", "subcommand"]},
                }
                for node_example in NodeRequirements.model_config["json_schema_extra"][
                    "examples"
                ]  # type: ignore[index,union-attr]
            ]
        }
    )


CHARS_IN_VOLUME_NAME_BEFORE_DIR_NAME: Final[NonNegativeInt] = 89
