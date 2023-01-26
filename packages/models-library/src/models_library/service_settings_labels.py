# pylint: disable=unsubscriptable-object

import json
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Any, Final, Iterator, Literal, Optional, Union

from pydantic import BaseModel, Extra, Field, Json, PrivateAttr, validator

from .basic_types import PortInt
from .generics import ListModel
from .services_resources import DEFAULT_SINGLE_SERVICE_NAME

# well known DNS server ran by address by Cloudflare
DEFAULT_DNS_SERVER_ADDRESS: Final[str] = "1.1.1.1"  # NOSONAR
# standard domain name system port
DEFAULT_DNS_SERVER_PORT: Final[PortInt] = 53


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

    class Config(_BaseConfig):
        schema_extra = {
            "example": {
                "outputs_path": "/tmp/outputs",  # nosec
                "inputs_path": "/tmp/inputs",  # nosec
                "state_paths": ["/tmp/save_1", "/tmp_save_2"],  # nosec
                "state_exclude": ["/tmp/strip_me/*", "*.py"],  # nosec
            }
        }


ComposeSpecLabel = dict[str, Any]


class RestartPolicy(str, Enum):
    NO_RESTART = "no-restart"
    ON_INPUTS_DOWNLOADED = "on-inputs-downloaded"


class PortRange(BaseModel):
    """`lower` and `upper` are included"""

    lower: PortInt
    upper: PortInt

    @validator("upper")
    @classmethod
    def lower_less_than_upper(cls, v, values) -> PortInt:
        upper = v
        lower: Optional[PortInt] = values.get("lower")
        if lower is None or lower >= upper:
            raise ValueError(f"Condition not satisfied: {lower=} < {upper=}")
        return v


class DNResolver(BaseModel):
    address: str
    port: PortInt

    class Config(_BaseConfig):
        extra = Extra.allow
        schema_extra = {
            "examples": [
                {"address": "1.1.1.1", "port": 53},
                {"address": "ns1.example.com", "port": 53},
            ]
        }


class HostPermitListPolicy(BaseModel):
    hostname: str
    tcp_ports: list[Union[PortRange, PortInt]]
    dns_resolver: DNResolver = Field(
        default_factory=lambda: DNResolver(
            address=DEFAULT_DNS_SERVER_ADDRESS, port=DEFAULT_DNS_SERVER_PORT
        ),
        description="specify a DNS resolver address and port",
    )

    def iter_tcp_ports(self) -> Iterator[PortInt]:
        for port in self.tcp_ports:
            if type(port) == PortRange:
                yield from range(port.lower, port.upper + 1)
            else:
                yield port


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

    containers_allowed_outgoing_permit_list: Optional[
        Json[dict[str, list[HostPermitListPolicy]]]
    ] = Field(
        None,
        alias="simcore.service.containers-allowed-outgoing-permit-list",
        description="allow internet access to certain domain names and ports per container",
    )

    containers_allowed_outgoing_internet: Optional[Json[set[str]]] = Field(
        None,
        alias="simcore.service.containers-allowed-outgoing-internet",
        description="allow complete internet access to containers in here",
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

    @validator("containers_allowed_outgoing_permit_list")
    @classmethod
    def _containers_allowed_outgoing_permit_list_in_compose_spec(  # pylint: disable = inconsistent-return-statements
        cls, v, values
    ):
        if v is None:
            return

        compose_spec: Optional[dict] = values.get("compose_spec")
        if compose_spec is None:
            keys = set(v.keys())
            if len(keys) != 1 or DEFAULT_SINGLE_SERVICE_NAME not in v:
                raise ValueError(
                    f"Expected only one entry '{DEFAULT_SINGLE_SERVICE_NAME}' not '{keys.pop()}'"
                )
        else:
            containers_in_compose_spec = set(compose_spec["services"].keys())
            for container in v.keys():
                if container not in containers_in_compose_spec:
                    raise ValueError(
                        f"Trying to permit list {container=} which was not found in {compose_spec=}"
                    )

        return v

    @validator("containers_allowed_outgoing_internet")
    @classmethod
    def _containers_allowed_outgoing_internet_in_compose_spec(  # pylint: disable = inconsistent-return-statements
        cls, v, values
    ):
        if v is None:
            return

        compose_spec: Optional[dict] = values.get("compose_spec")
        if compose_spec is None:
            if {DEFAULT_SINGLE_SERVICE_NAME} != v:
                raise ValueError(
                    f"Expected only 1 entry '{DEFAULT_SINGLE_SERVICE_NAME}' not '{v}'"
                )
        else:
            containers_in_compose_spec = set(compose_spec["services"].keys())
            for container in v:
                if container not in containers_in_compose_spec:
                    raise ValueError(f"{container=} not found in {compose_spec=}")
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
