# pylint: disable=unsubscriptable-object

import json
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Extra, Field, Json, PrivateAttr, validator

from .generics import ListModel


class _BaseConfig:
    extra = Extra.forbid
    keep_untouched = (cached_property,)


class ContainerSpec(BaseModel):
    """Implements entries that can be overriden for https://docs.docker.com/engine/api/v1.41/#operation/ServiceCreate
    request body: TaskTemplate -> ContainerSpec
    """

    command: list[str] = Field(
        alias="Command",
        description="Used to override the container's command",
        # NOTE: currently constraint to our use cases. Might mitigate some security issues.
        min_items=1,
        max_items=2,
    )

    class Config(_BaseConfig):
        schema_extra = {
            "examples": [
                {"Command": ["executable"]},
                {"Command": ["executable", "subcommand"]},
                {"Command": ["ofs", "linear-regression"]},
            ]
        }


class SimcoreServiceSettingLabelEntry(BaseModel):
    """These values are used to build the request body of https://docs.docker.com/engine/api/v1.41/#operation/ServiceCreate
    Specifically the section under ``TaskTemplate``
    """

    _destination_containers: list[str] = PrivateAttr()
    name: str = Field(..., description="The name of the service setting")
    setting_type: Literal[
        "string",
        "int",
        "integer",
        "number",
        "object",
        "ContainerSpec",
        "Resources",
    ] = Field(
        ...,
        description="The type of the service setting (follows Docker REST API naming scheme)",
        alias="type",
    )
    value: Any = Field(
        ...,
        description="The value of the service setting (shall follow Docker REST API scheme for services",
    )

    @validator("setting_type", pre=True)
    @classmethod
    def ensure_backwards_compatible_setting_type(cls, v):
        if v == "resources":
            # renamed in the latest version as
            return "Resources"
        return v

    class Config(_BaseConfig):
        schema_extra = {
            "examples": [
                # constraints
                {
                    "name": "constraints",
                    "type": "string",
                    "value": ["node.platform.os == linux"],
                },
                # SEE service_settings_labels.py::ContainerSpec
                {
                    "name": "ContainerSpec",
                    "type": "ContainerSpec",
                    "value": {"Command": ["run"]},
                },
                # SEE services_resources.py::ResourceValue
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
                # SEE 'simcore.service.settings' label annotations for simcore/services/dynamic/jupyter-octave-python-math:1.6.5
                {"name": "ports", "type": "int", "value": 8888},
                {
                    "name": "resources",
                    "type": "resources",
                    "value": {
                        "Limits": {"NanoCPUs": 4000000000, "MemoryBytes": 8589934592}
                    },
                },
            ]
        }


SimcoreServiceSettingsLabel = ListModel[SimcoreServiceSettingLabelEntry]

_BASE_DOCKER_SIZE: set[str] = {"b", "k", "m", "g", "t", "p"}
ALLOWED_DOCKER_SIZE: set[str] = _BASE_DOCKER_SIZE | {
    x.upper() for x in _BASE_DOCKER_SIZE
}


class PathMappingsLabel(BaseModel):
    inputs_path: Path = Field(
        ..., description="folder path where the service expects all the inputs"
    )
    outputs_path: Path = Field(
        ...,
        description="folder path where the service is expected to provide all its outputs",
    )
    state_paths: list[Path] = Field(
        [],
        description="optional list of paths which contents need to be persisted",
    )

    state_exclude: Optional[set[str]] = Field(
        None,
        description="optional list unix shell rules used to exclude files from the state",
    )

    volume_size_limits: Optional[dict[str, str]] = Field(
        None,
        description=(
            "Apply volume size limits to entries in `inputs_path` `outputs_path` "
            "and `state_paths`. Limits are expressed as docker sizes"
        ),
    )

    @validator("volume_size_limits")
    @classmethod
    def validate_volume_limits(cls, v, values) -> Optional[str]:
        if v is None:
            return v

        for path_str, size_str in v.items():
            last_char = size_str[-1]
            if not last_char.isnumeric():
                if last_char not in ALLOWED_DOCKER_SIZE:
                    raise ValueError(
                        f"Provided size='{size_str}' contains unsupported '{last_char}' "
                        f"docker size. Supported values are: {ALLOWED_DOCKER_SIZE}."
                    )

            inputs_path: Optional[Path] = values.get("inputs_path")
            outputs_path: Optional[Path] = values.get("outputs_path")
            state_paths: Optional[list[Path]] = values.get("state_paths")
            path = Path(path_str)
            if not (
                path == inputs_path
                or path == outputs_path
                or (state_paths is not None and path in state_paths)
            ):
                raise ValueError(
                    f"{path=} not found in {inputs_path=}, {outputs_path=}, {state_paths=}"
                )

        return v

    class Config(_BaseConfig):
        schema_extra = {
            "examples": [
                {
                    "outputs_path": "/tmp/outputs",  # nosec
                    "inputs_path": "/tmp/inputs",  # nosec
                    "state_paths": ["/tmp/save_1", "/tmp_save_2"],  # nosec
                    "state_exclude": ["/tmp/strip_me/*", "*.py"],  # nosec
                },
                {
                    "outputs_path": "/t_out",
                    "inputs_path": "/t_inp",
                    "state_paths": [f"/s{x}" for x in range(len(ALLOWED_DOCKER_SIZE))]
                    + ["/s"],
                    "volume_size_limits": {
                        f"/s{k}": f"1{x}" for k, x in enumerate(ALLOWED_DOCKER_SIZE)
                    }
                    | {"/s": "1"},
                },
            ]
        }


ComposeSpecLabel = dict[str, Any]


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
                # WARNING: do not change order. Used in tests!
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
                        PathMappingsLabel.Config.schema_extra["examples"][0]
                    ),
                    "simcore.service.restart-policy": RestartPolicy.NO_RESTART.value,
                },
                # dynamic-service with compose spec
                {
                    "simcore.service.settings": json.dumps(
                        SimcoreServiceSettingLabelEntry.Config.schema_extra["examples"]
                    ),
                    "simcore.service.paths-mapping": json.dumps(
                        PathMappingsLabel.Config.schema_extra["examples"][0]
                    ),
                    "simcore.service.compose-spec": json.dumps(
                        {
                            "version": "2.3",
                            "services": {
                                "rt-web": {
                                    "image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/sim4life:${SERVICE_VERSION}",
                                    "init": True,
                                    "depends_on": ["s4l-core"],
                                },
                                "s4l-core": {
                                    "image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/s4l-core:${SERVICE_VERSION}",
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
