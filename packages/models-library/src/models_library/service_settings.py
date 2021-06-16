# pylint: disable=unsubscriptable-object
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Extra, Field, Json, validator, PrivateAttr


class _BaseConfig:
    extra = Extra.ignore


class SimcoreServiceSetting(BaseModel):
    _destination_container: str = PrivateAttr()
    name: str = Field(..., description="The name of the service setting")
    setting_type: str = Field(
        ...,
        description="The type of the service setting (follows Docker REST API naming scheme)",
        alias="type",
    )
    value: Any = Field(
        ...,
        description="The value of the service setting (shall follow Docker REST API scheme for services",
    )

    class Config(_BaseConfig):
        schema_extra = {
            "examples": [
                # constraints
                {
                    "name": "constraints",
                    "type": "string",
                    "value": ["node.platform.os == linux"],
                },
                # resources
                {
                    "name": "Resources",
                    "type": "Resources",
                    "value": {
                        "Limits": {"NanoCPUs": 4000000000, "MemoryBytes": 17179869184},
                        "Reservations": {
                            "NanoCPUs": 100000000,
                            "MemoryBytes": 536870912,
                            "GenericResources": [
                                {"DiscreteResourceSpec": {"Kind": "VRAM", "Value": 1}}
                            ],
                        },
                    },
                },
                # mounts
                {
                    "name": "mount",
                    "type": "object",
                    "value": [
                        {
                            "ReadOnly": True,
                            "Source": "/tmp/.X11-unix",  # nosec
                            "Target": "/tmp/.X11-unix",  # nosec
                            "Type": "bind",
                        }
                    ],
                },
                # environments
                {"name": "env", "type": "string", "value": ["DISPLAY=:0"]},
            ]
        }


class SimcoreServiceSettings(BaseModel):
    __root__: List[SimcoreServiceSetting]

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, item):
        return self.__root__[item]


class PathsMapping(BaseModel):
    inputs_path: Path = Field(
        ..., description="path where the service expects all the inputs folder"
    )
    outputs_path: Path = Field(
        ..., description="path where the service expects all the outputs folder"
    )
    other_paths: List[Path] = Field(
        [],
        description="optional list of path which contents need to be saved and restored",
    )

    @validator("other_paths", always=True)
    @classmethod
    def convert_none_to_empty_list(cls, v):
        return [] if v is None else v

    class Config(_BaseConfig):
        schema_extra = {
            "examples": {
                "outputs_path": "/tmp/outputs",  # nosec
                "inputs_path": "/tmp/inputs",  # nosec
            }
        }


ComposeSpecModel = Optional[Dict[str, Any]]


class SimcoreService(BaseModel):
    """Validate all the simcores.services.* labels on a service"""

    settings: Json[SimcoreServiceSettings] = Field(
        ...,
        alias="simcore.service.settings",
        description=(
            "Contains setting like environment variables and "
            "resource constraints which are required by the service"
        ),
    )

    paths_mapping: Json[Optional[PathsMapping]] = Field(
        None,
        alias="simcore.service.paths-mapping",
        description="json encoded, determines where the outputs and inputs directories are",
    )

    compose_spec: Json[ComposeSpecModel] = Field(
        None,
        alias="simcore.service.compose-spec",
        description="json encoded docker-compose spec",
    )
    container_http_entry: Optional[str] = Field(
        None,
        alias="simcore.service.container-http-entrypoint",
        description=(
            "When a compose spec is provided, a container where the proxy "
            "needs to send http traffic must be specified"
        ),
    )

    needs_dynamic_sidecar: Optional[bool] = Field(
        None, description="true if dynamic sidecar is needed to start that service"
    )

    @validator("needs_dynamic_sidecar", pre=True, always=True)
    @classmethod
    def auto_fill_dynamic_sidecar(cls, v, values):
        if not v:
            return values.get("paths_mapping") is not None
        return v

    @validator("container_http_entry", always=True)
    @classmethod
    def compose_spec_requires_container_http_entry(cls, v, values):
        if v is None and values.get("compose_spec") is not None:
            raise ValueError(
                "Field `container_http_entry` must be defined but is missing"
            )
        return v

    class Config(_BaseConfig):
        schema_extra = {
            "examples": [
                # legacy service
                {
                    "simcore.service.settings": json.dumps(
                        SimcoreServiceSetting.Config.schema_extra["examples"]
                    )
                },
                # dynamic-service
                {
                    "simcore.service.settings": json.dumps(
                        SimcoreServiceSetting.Config.schema_extra["examples"]
                    ),
                    "simcore.service.paths-mapping": json.dumps(
                        PathsMapping.Config.schema_extra["examples"]
                    ),
                },
                # dynamic-service with compose spec
                {
                    "simcore.service.settings": json.dumps(
                        SimcoreServiceSetting.Config.schema_extra["examples"]
                    ),
                    "simcore.service.paths-mapping": json.dumps(
                        PathsMapping.Config.schema_extra["examples"]
                    ),
                    "simcore.service.compose-spec": json.dumps(
                        {
                            "version": "2.3",
                            "services": {
                                "rt-web": {
                                    "image": "${REGISTRY_URL}/simcore/services/dynamic/sim4life:${SERVICE_TAG}",
                                    "init": True,
                                    "depends_on": ["s4l-core"],
                                },
                                "s4l-core": {
                                    "image": "${REGISTRY_URL}/simcore/services/dynamic/s4l-core:${SERVICE_TAG}",
                                    "runtime": "nvidia",
                                    "init": True,
                                    "environment": ["DISPLAY=${DISPLAY}"],
                                    "volumes": [
                                        "/tmp/.X11-unix:/tmp/.X11-unix"
                                    ],  # nosec
                                },
                            },
                        }
                    ),
                    "simcore.service.container-http-entrypoint": "rt-web",
                },
            ]
        }
