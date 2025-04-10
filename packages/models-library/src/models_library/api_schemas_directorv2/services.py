from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.config import JsonDict
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

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        examples = [
            *(
                {"node_requirements": node_example}
                for node_example in NodeRequirements.model_json_schema()["examples"]
            ),
            *(
                {
                    "node_requirements": node_example,
                    "service_build_details": {
                        "build_date": "2021-08-13T12:56:28Z",
                        "vcs_ref": "8251ade",
                        "vcs_url": "git@github.com:ITISFoundation/osparc-simcore.git",
                    },
                }
                for node_example in NodeRequirements.model_json_schema()["examples"]
            ),
            *(
                {
                    "node_requirements": node_example,
                    "service_build_details": {
                        "build_date": "2021-08-13T12:56:28Z",
                        "vcs_ref": "8251ade",
                        "vcs_url": "git@github.com:ITISFoundation/osparc-simcore.git",
                    },
                    "container_spec": {"Command": ["run", "subcommand"]},
                }
                for node_example in NodeRequirements.model_json_schema()["examples"]
            ),
        ]
        schema.update({"examples": examples})

    model_config = ConfigDict(json_schema_extra=_update_json_schema_extra)


CHARS_IN_VOLUME_NAME_BEFORE_DIR_NAME: Final[NonNegativeInt] = 89


DYNAMIC_SIDECAR_SERVICE_PREFIX: Final[str] = "dy-sidecar"
DYNAMIC_PROXY_SERVICE_PREFIX: Final[str] = "dy-proxy"
