# pylint: disable=unsubscriptable-object

from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Annotated, Any, Literal, TypeAlias

from common_library.json_serialization import json_dumps
from pydantic import (
    BaseModel,
    ByteSize,
    ConfigDict,
    Field,
    Json,
    PrivateAttr,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from .callbacks_mapping import CallbacksMapping
from .generics import ListModel
from .service_settings_nat_rule import NATRule
from .services_resources import DEFAULT_SINGLE_SERVICE_NAME

_BaseConfig = ConfigDict(
    extra="forbid", arbitrary_types_allowed=True, ignored_types=(cached_property,)
)


class ContainerSpec(BaseModel):
    """Implements entries that can be overriden for https://docs.docker.com/engine/api/v1.41/#operation/ServiceCreate
    request body: TaskTemplate -> ContainerSpec
    """

    command: list[str] = Field(
        alias="Command",
        description="Used to override the container's command",
        # NOTE: currently constraint to our use cases. Might mitigate some security issues.
        min_length=1,
        max_length=2,
    )

    model_config = _BaseConfig | ConfigDict(
        json_schema_extra={
            "examples": [
                {"Command": ["executable"]},
                {"Command": ["executable", "subcommand"]},
                {"Command": ["ofs", "linear-regression"]},
            ]
        },
    )


class SimcoreServiceSettingLabelEntry(BaseModel):
    """Content of "simcore.service.settings" label

    These values are used to build the request body of https://docs.docker.com/engine/api/v1.41/#operation/ServiceCreate
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

    def set_destination_containers(self, value: list[str]) -> None:
        # NOTE: private attributes cannot be transformed into properties
        # since it conflicts with pydantic's internals which treats them
        # as fields
        self._destination_containers = value

    def get_destination_containers(self) -> list[str]:
        # NOTE: private attributes cannot be transformed into properties
        # since it conflicts with pydantic's internals which treats them
        # as fields
        return self._destination_containers

    @field_validator("setting_type", mode="before")
    @classmethod
    def ensure_backwards_compatible_setting_type(cls, v):
        if v == "resources":
            # renamed in the latest version as
            return "Resources"
        return v

    model_config = _BaseConfig | ConfigDict(
        populate_by_name=True,
        json_schema_extra={
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
                            "Source": "/tmp/.X11-unix",  # nosec  # noqa: S108
                            "Target": "/tmp/.X11-unix",  # nosec  # noqa: S108
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
        },
    )


SimcoreServiceSettingsLabel = ListModel[SimcoreServiceSettingLabelEntry]


class PathMappingsLabel(BaseModel):
    """Content of "simcore.service.paths-mapping" label"""

    inputs_path: Path = Field(
        ..., description="folder path where the service expects all the inputs"
    )
    outputs_path: Path = Field(
        ...,
        description="folder path where the service is expected to provide all its outputs",
    )
    state_paths: list[Path] = Field(
        default_factory=list,
        description="optional list of paths which contents need to be persisted",
    )

    state_exclude: set[str] | None = Field(
        None,
        description="optional list unix shell rules used to exclude files from the state",
    )

    volume_size_limits: dict[str, str] | None = Field(
        None,
        description=(
            "Apply volume size limits to entries in: `inputs_path`, `outputs_path` "
            "and `state_paths`. Limits must be parsable by Pydantic's ByteSize."
        ),
    )

    @field_validator("volume_size_limits")
    @classmethod
    def validate_volume_limits(cls, v, info: ValidationInfo) -> str | None:
        if v is None:
            return v

        for path_str, size_str in v.items():
            # checks that format is correct
            try:
                TypeAdapter(ByteSize).validate_python(size_str)
            except ValidationError as e:
                msg = f"Provided size='{size_str}' contains invalid charactes: {e!s}"
                raise ValueError(msg) from e

            inputs_path: Path | None = info.data.get("inputs_path")
            outputs_path: Path | None = info.data.get("outputs_path")
            state_paths: list[Path] | None = info.data.get("state_paths")
            path = Path(path_str)
            if not (
                path in (inputs_path, outputs_path)
                or (state_paths is not None and path in state_paths)
            ):
                msg = f"path={path!r} not found in inputs_path={inputs_path!r}, outputs_path={outputs_path!r}, state_paths={state_paths!r}"
                raise ValueError(msg)
        output: str | None = v
        return output

    model_config = _BaseConfig | ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "outputs_path": "/tmp/outputs",  # noqa: S108 nosec
                    "inputs_path": "/tmp/inputs",  # noqa: S108 nosec
                    "state_paths": ["/tmp/save_1", "/tmp_save_2"],  # noqa: S108 nosec
                    "state_exclude": ["/tmp/strip_me/*"],  # noqa: S108 nosec
                },
                {
                    "outputs_path": "/t_out",
                    "inputs_path": "/t_inp",
                    "state_paths": [
                        "/s",
                        "/s0",
                        "/s1",
                        "/s2",
                        "/s3",
                        "/i_have_no_limit",
                    ],
                    "volume_size_limits": {
                        "/s": "1",
                        "/s0": "1m",
                        "/s1": "1kib",
                        "/s2": "1TIB",
                        "/s3": "1G",
                        "/t_out": "12",
                        "/t_inp": "1EIB",
                    },
                },
            ]
        },
    )


ComposeSpecLabelDict: TypeAlias = dict[str, Any]


class RestartPolicy(str, Enum):
    """Content of "simcore.service.restart-policy" label"""

    NO_RESTART = "no-restart"
    ON_INPUTS_DOWNLOADED = "on-inputs-downloaded"


class DynamicSidecarServiceLabels(BaseModel):
    """All "simcore.service.*" labels including keys"""

    paths_mapping: Json[PathMappingsLabel] | None = Field(
        None,
        alias="simcore.service.paths-mapping",
        description=(
            "json encoded, determines how the folders are mapped in "
            "the service. Required by dynamic-sidecar."
        ),
    )

    compose_spec: Json[ComposeSpecLabelDict | None] | None = Field(
        None,
        alias="simcore.service.compose-spec",
        description=(
            "json encoded docker-compose specifications. see "
            "https://docs.docker.com/compose/compose-file/, "
            "only used by dynamic-sidecar."
        ),
    )
    container_http_entry: str | None = Field(
        None,
        alias="simcore.service.container-http-entrypoint",
        description=(
            "When a docker-compose specifications is provided, "
            "the container where the traffic must flow has to be "
            "specified. Required by dynamic-sidecar when "
            "compose_spec is set."
        ),
        validate_default=True,
    )

    user_preferences_path: Path | None = Field(
        None,
        alias="simcore.service.user-preferences-path",
        description=(
            "path where the user user preferences folder "
            "will be mounted in the user services"
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

    containers_allowed_outgoing_permit_list: Annotated[
        None | (Json[dict[str, list[NATRule]]]),
        Field(
            None,
            alias="simcore.service.containers-allowed-outgoing-permit-list",
            description="allow internet access to certain domain names and ports per container",
        ),
    ]

    containers_allowed_outgoing_internet: Json[set[str]] | None = Field(
        None,
        alias="simcore.service.containers-allowed-outgoing-internet",
        description="allow complete internet access to containers in here",
    )

    callbacks_mapping: Json[CallbacksMapping] | None = Field(
        default_factory=CallbacksMapping,  # type: ignore[arg-type] # this one ANE I am not sure about
        alias="simcore.service.callbacks-mapping",
        description="exposes callbacks from user services to the sidecar",
    )

    @cached_property
    def needs_dynamic_sidecar(self) -> bool:
        """if paths mapping is present the service needs to be ran via dynamic-sidecar"""
        return self.paths_mapping is not None

    @field_validator("container_http_entry")
    @classmethod
    def compose_spec_requires_container_http_entry(
        cls, v, info: ValidationInfo
    ) -> str | None:
        v = None if v == "" else v
        if v is None and info.data.get("compose_spec") is not None:
            msg = "Field `container_http_entry` must be defined but is missing"
            raise ValueError(msg)
        if v is not None and info.data.get("compose_spec") is None:
            msg = "`container_http_entry` not allowed if `compose_spec` is missing"
            raise ValueError(msg)
        return f"{v}" if v else v

    @field_validator("containers_allowed_outgoing_permit_list")
    @classmethod
    def _containers_allowed_outgoing_permit_list_in_compose_spec(
        cls, v, info: ValidationInfo
    ):
        if v is None:
            return v

        compose_spec: dict | None = info.data.get("compose_spec")
        if compose_spec is None:
            keys = set(v.keys())
            if len(keys) != 1 or DEFAULT_SINGLE_SERVICE_NAME not in keys:
                err_msg = f"Expected only one entry '{DEFAULT_SINGLE_SERVICE_NAME}' not '{keys.pop()}'"
                raise ValueError(err_msg)
        else:
            containers_in_compose_spec = set(compose_spec["services"].keys())
            for container in v:
                if container not in containers_in_compose_spec:
                    err_msg = f"Trying to permit list {container=} which was not found in {compose_spec=}"
                    raise ValueError(err_msg)

        return v

    @field_validator("containers_allowed_outgoing_internet")
    @classmethod
    def _containers_allowed_outgoing_internet_in_compose_spec(
        cls, v, info: ValidationInfo
    ):
        if v is None:
            return None

        compose_spec: dict | None = info.data.get("compose_spec")
        if compose_spec is None:
            if {DEFAULT_SINGLE_SERVICE_NAME} != v:
                err_msg = (
                    f"Expected only 1 entry '{DEFAULT_SINGLE_SERVICE_NAME}' not '{v}'"
                )
                raise ValueError(err_msg)
        else:
            containers_in_compose_spec = set(compose_spec["services"].keys())
            for container in v:
                if container not in containers_in_compose_spec:
                    err_msg = f"{container=} not found in {compose_spec=}"
                    raise ValueError(err_msg)
        return v

    @field_validator("callbacks_mapping")
    @classmethod
    def _ensure_callbacks_mapping_container_names_defined_in_compose_spec(
        cls, v: CallbacksMapping, info: ValidationInfo
    ):
        if v is None:
            return {}

        defined_services: set[str] = {x.service for x in v.before_shutdown}
        if v.metrics:
            defined_services.add(v.metrics.service)

        if len(defined_services) == 0:
            return v

        compose_spec: dict | None = info.data.get("compose_spec")
        if compose_spec is None:
            if {DEFAULT_SINGLE_SERVICE_NAME} != defined_services:
                err_msg = f"Expected only 1 entry '{DEFAULT_SINGLE_SERVICE_NAME}' not '{defined_services}'"
                raise ValueError(err_msg)
        else:
            containers_in_compose_spec = set(compose_spec["services"].keys())
            for service_name in defined_services:
                if service_name not in containers_in_compose_spec:
                    err_msg = f"{service_name=} not found in {compose_spec=}"
                    raise ValueError(err_msg)
        return v

    @field_validator("user_preferences_path", mode="before")
    @classmethod
    def _deserialize_from_json(cls, v):
        return f"{v}".removeprefix('"').removesuffix('"') if v else None

    @field_validator("user_preferences_path")
    @classmethod
    def _user_preferences_path_no_included_in_other_volumes(
        cls, v: CallbacksMapping, info: ValidationInfo
    ):
        paths_mapping: PathMappingsLabel | None = info.data.get("paths_mapping", None)
        if paths_mapping is None:
            return v

        for test_path in [
            paths_mapping.inputs_path,
            paths_mapping.outputs_path,
            *paths_mapping.state_paths,
        ]:
            if f"{test_path}".startswith(f"{v}"):
                msg = f"user_preferences_path={v} cannot be a subpath of {test_path}"
                raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _not_allowed_in_both_specs(self):
        match_keys = {
            "containers_allowed_outgoing_internet",
            "containers_allowed_outgoing_permit_list",
        }
        if match_keys & set(self.model_fields) != match_keys:
            err_msg = f"Expected the following keys {match_keys} to be present {self.model_fields=}"
            raise ValueError(err_msg)

        if (
            self.containers_allowed_outgoing_internet is None
            or self.containers_allowed_outgoing_permit_list is None
        ):
            return self

        common_containers = set(self.containers_allowed_outgoing_internet) & set(
            self.containers_allowed_outgoing_permit_list.keys()
        )
        if len(common_containers) > 0:
            err_msg = (
                f"Not allowed {common_containers=} detected between "
                "`containers-allowed-outgoing-permit-list` and "
                "`containers-allowed-outgoing-internet`."
            )
            raise ValueError(err_msg)

        return self

    model_config = _BaseConfig


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
        default_factory=dict,
        alias="simcore.service.settings",
        description=(
            "Json encoded. Contains setting like environment variables and "
            "resource constraints which are required by the service. "
            "Should be compatible with Docker REST API."
        ),
    )

    model_config = _BaseConfig | ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [
                # WARNING: do not change order. Used in tests!
                # legacy service
                {
                    "simcore.service.settings": json_dumps(
                        SimcoreServiceSettingLabelEntry.model_config[
                            "json_schema_extra"
                        ][
                            "examples"
                        ]  # type: ignore[index]
                    )
                },
                # dynamic-service
                {
                    "simcore.service.settings": json_dumps(
                        SimcoreServiceSettingLabelEntry.model_config[
                            "json_schema_extra"
                        ][
                            "examples"
                        ]  # type: ignore[index]
                    ),
                    "simcore.service.paths-mapping": json_dumps(
                        PathMappingsLabel.model_config["json_schema_extra"]["examples"][0]  # type: ignore [index]
                    ),
                    "simcore.service.restart-policy": RestartPolicy.NO_RESTART.value,
                    "simcore.service.callbacks-mapping": json_dumps(
                        {
                            "metrics": {
                                "service": DEFAULT_SINGLE_SERVICE_NAME,
                                "command": "ls",
                                "timeout": 1,
                            }
                        }
                    ),
                    "simcore.service.user-preferences-path": json_dumps(
                        "/tmp/path_to_preferences"  # noqa: S108
                    ),
                },
                # dynamic-service with compose spec
                {
                    "simcore.service.settings": json_dumps(
                        SimcoreServiceSettingLabelEntry.model_config[
                            "json_schema_extra"
                        ][
                            "examples"
                        ]  # type: ignore[index]
                    ),
                    "simcore.service.paths-mapping": json_dumps(
                        PathMappingsLabel.model_config["json_schema_extra"]["examples"][0],  # type: ignore[index]
                    ),
                    "simcore.service.compose-spec": json_dumps(
                        {
                            "version": "2.3",
                            "services": {
                                "rt-web": {
                                    "image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/sim4life:${SERVICE_VERSION}",
                                    "init": True,
                                    "depends_on": ["s4l-core"],
                                    "storage_opt": {"size": "10M"},
                                },
                                "s4l-core": {
                                    "image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/s4l-core:${SERVICE_VERSION}",
                                    "runtime": "nvidia",
                                    "storage_opt": {"size": "5G"},
                                    "init": True,
                                    "environment": ["DISPLAY=${DISPLAY}"],
                                    "volumes": [
                                        "/tmp/.X11-unix:/tmp/.X11-unix"  # nosec  # noqa: S108
                                    ],
                                },
                            },
                        }
                    ),
                    "simcore.service.container-http-entrypoint": "rt-web",
                    "simcore.service.restart-policy": RestartPolicy.ON_INPUTS_DOWNLOADED.value,
                    "simcore.service.callbacks-mapping": json_dumps(
                        CallbacksMapping.model_config["json_schema_extra"]["examples"][3]  # type: ignore [index]
                    ),
                },
            ]
        },
    )
