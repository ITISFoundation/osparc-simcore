import datetime
from contextlib import suppress
from typing import Any

from dask_task_models_library.container_tasks.protocol import ContainerEnvsDict
from models_library.api_schemas_directorv2.services import NodeRequirements
from models_library.basic_regex import SIMPLE_VERSION_RE
from models_library.errors import ErrorDict
from models_library.projects import ProjectID
from models_library.projects_nodes import InputsDict, OutputsDict
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.resource_tracker import HardwareInfo
from models_library.services import ServiceInputsDict, ServiceOutput, ServicePortKey
from models_library.services_regex import SERVICE_KEY_RE
from models_library.services_resources import BootMode
from pydantic import (
    TypeAdapter, ValidationInfo, field_validator, ConfigDict, BaseModel,
    ByteSize,
    Field,
    PositiveInt,
)
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_tasks import NodeClass

from ..utils.db import DB_TO_RUNNING_STATE, RUNNING_STATE_TO_DB


class Image(BaseModel):
    name: str = Field(..., pattern=SERVICE_KEY_RE.pattern)
    tag: str = Field(..., pattern=SIMPLE_VERSION_RE)

    requires_gpu: bool | None = Field(
        default=None, deprecated=True, description="Use instead node_requirements"
    )
    requires_mpi: bool | None = Field(
        default=None, deprecated=True, description="Use instead node_requirements"
    )
    node_requirements: NodeRequirements | None = Field(
        default=None, description="the requirements for the service to run on a node", validate_default=True
    )
    boot_mode: BootMode = BootMode.CPU
    command: list[str] = Field(
        default=[
            "run",
        ],
        description="command to run container. Can override using ContainerSpec service labels",
    )
    envs: ContainerEnvsDict = Field(
        default_factory=dict, description="The environment to use to run the service"
    )

    @field_validator("node_requirements", mode="before")
    @classmethod
    def migrate_from_requirements(cls, v, info: ValidationInfo):
        if v is None:
            # NOTE: 'node_requirements' field's default=None although is NOT declared as nullable.
            # Then this validator with `pre=True, always=True` is used to create a default
            # based on that accounts for an old version.
            # This strategy guarantees backwards compatibility
            v = NodeRequirements(
                CPU=1.0,
                GPU=1 if info.data.get("requires_gpu") else 0,
                RAM=TypeAdapter(ByteSize).validate_python("128 MiB"),
            )
        return v
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "name": "simcore/services/dynamic/jupyter-octave-python-math",
                    "tag": "1.3.1",
                    "node_requirements": node_req_example,
                }
                for node_req_example in NodeRequirements.model_config["json_schema_extra"]["examples"]
            ]
            +
            # old version
            [
                {
                    "name": "simcore/services/dynamic/jupyter-octave-python-math",
                    "tag": "0.0.1",
                    "requires_gpu": True,
                    "requires_mpi": False,
                }
            ]
        }
    )


# NOTE: for a long time defaultValue field was added to ServiceOutput wrongly in the DB.
# this flags allows parsing of the outputs without error. This MUST not leave the director-v2!
class _ServiceOutputOverride(ServiceOutput):
    model_config = ConfigDict(
        extra = "ignore"
    )


_ServiceOutputsOverride = dict[ServicePortKey, _ServiceOutputOverride]


class NodeSchema(BaseModel):
    inputs: ServiceInputsDict = Field(..., description="the inputs scheam")
    outputs: _ServiceOutputsOverride = Field(..., description="the outputs schema")
    model_config = ConfigDict(extra="ignore", extra="forbid", from_attributes=True)


class CompTaskAtDB(BaseModel):
    project_id: ProjectID
    node_id: NodeID
    job_id: str | None = Field(default=None, description="The worker job ID")
    node_schema: NodeSchema = Field(..., alias="schema")
    inputs: InputsDict | None = Field(..., description="the inputs payload")
    outputs: OutputsDict | None = Field(
        default_factory=dict, description="the outputs payload"
    )
    run_hash: str | None = Field(
        default=None,
        description="the hex digest of the resolved inputs +outputs hash at the time when the last outputs were generated",
    )
    image: Image
    submit: datetime.datetime
    start: datetime.datetime | None = Field(default=None)
    end: datetime.datetime | None = Field(default=None)
    state: RunningState
    task_id: PositiveInt | None = Field(default=None)
    internal_id: PositiveInt
    node_class: NodeClass
    errors: list[ErrorDict] | None = Field(default=None)
    progress: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="current progress of the task if available",
    )
    last_heartbeat: datetime.datetime | None = Field(
        ..., description="Last time the running task was checked by the backend"
    )
    created: datetime.datetime
    modified: datetime.datetime
    # Additional information about price and hardware (ex. AWS EC2 instance type)
    pricing_info: dict | None = None
    hardware_info: HardwareInfo

    @field_validator("state", mode="before")
    @classmethod
    def convert_state_from_state_type_enum_if_needed(cls, v):
        if isinstance(v, str):
            # try to convert to a StateType, if it fails the validations will continue
            # and pydantic will try to convert it to a RunninState later on
            with suppress(ValueError):
                v = StateType(v)
        if isinstance(v, StateType):
            return RunningState(DB_TO_RUNNING_STATE[StateType(v)])
        return v

    @field_validator("start", "end", "submit")
    @classmethod
    def ensure_utc(cls, v: datetime.datetime | None) -> datetime.datetime | None:
        if v is not None and v.tzinfo is None:
            v = v.replace(tzinfo=datetime.timezone.utc)
        return v

    @field_validator("hardware_info", mode="before")
    @classmethod
    def backward_compatible_null_value(cls, v: HardwareInfo | None) -> HardwareInfo:
        if v is None:
            return HardwareInfo(aws_ec2_instances=[])
        return v

    def to_db_model(self, **exclusion_rules) -> dict[str, Any]:
        comp_task_dict = self.model_dump(by_alias=True, exclude_unset=True, **exclusion_rules)
        if "state" in comp_task_dict:
            comp_task_dict["state"] = RUNNING_STATE_TO_DB[comp_task_dict["state"]].value
        return comp_task_dict
    model_config = ConfigDict(extra="forbid", from_attributes=True)
