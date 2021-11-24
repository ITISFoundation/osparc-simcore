# pylint: disable=unsubscriptable-object
from enum import Enum
import json
from functools import cached_property
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Extra, Field, Json, PrivateAttr, validator


class _BaseConfig:
    extra = Extra.forbid
    keep_untouched = (cached_property,)


class SimcoreServiceSettingLabelEntry(BaseModel):
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


class SimcoreServiceSettingsLabel(BaseModel):
    __root__: List[SimcoreServiceSettingLabelEntry]

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, item):
        return self.__root__[item]

    def __len__(self):
        return len(self.__root__)


class PathMappingsLabel(BaseModel):
    inputs_path: Path = Field(
        ..., description="folder path where the service expects all the inputs"
    )
    outputs_path: Path = Field(
        ...,
        description="folder path where the service is expected to provide all its outputs",
    )
    state_paths: List[Path] = Field(
        [],
        description="optional list of paths which contents need to be persisted",
    )

    class Config(_BaseConfig):
        schema_extra = {
            "example": {
                "outputs_path": "/tmp/outputs",  # nosec
                "inputs_path": "/tmp/inputs",  # nosec
                "state_paths": ["/tmp/save_1", "/tmp_save_2"],  # nosec
            }
        }


ComposeSpecLabel = Dict[str, Any]


class RestartPolicy(str, Enum):
    NO_RESTART = "no-restart"
    ON_INPUTS_DOWNLOADED = "on-inputs-downloaded"


class DynamicSidecarServiceLabels(BaseModel):
    paths_mapping: Optional[Json[PathMappingsLabel]] = Field(
        None,
        alias="simcore.service.paths-mapping",
        description=(
            "json encoded, determines how the folders are mapped in "
            "the service. Required by dynamic-sidecar."
        ),
    )

    compose_spec: Optional[Json[ComposeSpecLabel]] = Field(
        None,
        alias="simcore.service.compose-spec",
        description=(
            "json encoded docker-compose specifications. see "
            "https://docs.docker.com/compose/compose-file/, "
            "only used by dynamic-sidecar."
        ),
    )
    container_http_entry: Optional[str] = Field(
        None,
        alias="simcore.service.container-http-entrypoint",
        description=(
            "When a docker-compose specifications is provided, "
            "the container where the traffic must flow has to be "
            "specified. Required by dynamic-sidecar when "
            "compose_spec is set."
        ),
    )

    restart_policy: RestartPolicy = Field(
        RestartPolicy.NO_RESTART,
        alias="simcore.service.restart-policy",
        description=(
            "the dynamic-sidecar can restart all running containers "
            "on certain events. Supported events:\n"
            "- `no-restart` default\n"
            "- `on-inputs-downloaded` after inputs are downloaded\n"
        ),
    )

    @cached_property
    def needs_dynamic_sidecar(self) -> bool:
        """if paths mapping is present the service needs to be ran via dynamic-sidecar"""
        return self.paths_mapping is not None

    @validator("container_http_entry", always=True)
    @classmethod
    def compose_spec_requires_container_http_entry(cls, v, values) -> Optional[str]:
        v = None if v == "" else v
        if v is None and values.get("compose_spec") is not None:
            raise ValueError(
                "Field `container_http_entry` must be defined but is missing"
            )
        if v is not None and values.get("compose_spec") is None:
            raise ValueError(
                "`container_http_entry` not allowed if `compose_spec` is missing"
            )
        return v

    class Config(_BaseConfig):
        pass


class SimcoreServiceLabels(DynamicSidecarServiceLabels):
    """
    Validate all the simcores.services.* labels on a service.

    When no other fields expect `settings` are present
    the service will be started as legacy by director-v0.

    If `paths_mapping` is present the service will be started
    via dynamic-sidecar by director-v2.

    When starting via dynamic-sidecar, if `compose_spec` is
    present, also `container_http_entry` must be present.
    When both of these fields are missing a docker-compose
    spec will be generated before starting the service.
    """

    settings: Json[SimcoreServiceSettingsLabel] = Field(
        ...,
        alias="simcore.service.settings",
        description=(
            "Json encoded. Contains setting like environment variables and "
            "resource constraints which are required by the service. "
            "Should be compatible with Docker REST API."
        ),
    )

    class Config(_BaseConfig):
        extra = Extra.allow
        schema_extra = {
            "examples": [
                # legacy service
                {
                    "simcore.service.settings": json.dumps(
                        SimcoreServiceSettingLabelEntry.Config.schema_extra["examples"]
                    )
                },
                # dynamic-service
                {
                    "simcore.service.settings": json.dumps(
                        SimcoreServiceSettingLabelEntry.Config.schema_extra["examples"]
                    ),
                    "simcore.service.paths-mapping": json.dumps(
                        PathMappingsLabel.Config.schema_extra["example"]
                    ),
                    "simcore.service.restart-policy": RestartPolicy.NO_RESTART.value,
                },
                # dynamic-service with compose spec
                {
                    "simcore.service.settings": json.dumps(
                        SimcoreServiceSettingLabelEntry.Config.schema_extra["examples"]
                    ),
                    "simcore.service.paths-mapping": json.dumps(
                        PathMappingsLabel.Config.schema_extra["example"]
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
                                        "/tmp/.X11-unix:/tmp/.X11-unix"  # nosec
                                    ],
                                },
                            },
                        }
                    ),
                    "simcore.service.container-http-entrypoint": "rt-web",
                    "simcore.service.restart-policy": RestartPolicy.ON_INPUTS_DOWNLOADED.value,
                },
            ]
        }
