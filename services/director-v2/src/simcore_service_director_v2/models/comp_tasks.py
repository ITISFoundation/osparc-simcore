import datetime as dt
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
    BaseModel,
    ByteSize,
    ConfigDict,
    Field,
    PositiveInt,
    TypeAdapter,
    ValidationInfo,
    field_validator,
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
        default=None,
        description="the requirements for the service to run on a node",
        validate_default=True,
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
    def _migrate_from_requirements(cls, v, info: ValidationInfo):
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
            "examples": [  # type: ignore
                {
                    "name": "simcore/services/dynamic/jupyter-octave-python-math",
                    "tag": "1.3.1",
                    "node_requirements": node_req_example,
                }
                for node_req_example in NodeRequirements.model_config[  # type: ignore
                    "json_schema_extra"
                ]["examples"]
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
        },
    )


class _ServiceOutputOverride(ServiceOutput):
    # NOTE: for a long time defaultValue field was added to ServiceOutput wrongly in the DB.
    # this flags allows parsing of the outputs without error. This MUST not leave the director-v2!
    model_config = ConfigDict(extra="ignore")


_ServiceOutputsOverride = dict[ServicePortKey, _ServiceOutputOverride]


class NodeSchema(BaseModel):
    inputs: ServiceInputsDict = Field(..., description="the inputs scheam")
    outputs: _ServiceOutputsOverride = Field(..., description="the outputs schema")
    model_config = ConfigDict(extra="forbid", from_attributes=True)


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
    submit: dt.datetime
    start: dt.datetime | None = None
    end: dt.datetime | None = None
    state: RunningState
    task_id: PositiveInt | None = None
    internal_id: PositiveInt
    node_class: NodeClass
    errors: list[ErrorDict] | None = None
    progress: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="current progress of the task if available",
    )
    last_heartbeat: dt.datetime | None = Field(
        ..., description="Last time the running task was checked by the backend"
    )
    created: dt.datetime
    modified: dt.datetime
    # Additional information about price and hardware (ex. AWS EC2 instance type)
    pricing_info: dict | None
    hardware_info: HardwareInfo

    @field_validator("state", mode="before")
    @classmethod
    def _convert_state_from_state_type_enum_if_needed(cls, v):
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
    def _ensure_utc(cls, v: dt.datetime | None) -> dt.datetime | None:
        if v is not None and v.tzinfo is None:
            v = v.replace(tzinfo=dt.UTC)
        return v

    @field_validator("hardware_info", mode="before")
    @classmethod
    def _backward_compatible_null_value(cls, v: HardwareInfo | None) -> HardwareInfo:
        if v is None:
            return HardwareInfo(aws_ec2_instances=[])
        return v

    def to_db_model(self, **exclusion_rules) -> dict[str, Any]:
        comp_task_dict = self.model_dump(
            mode="json", by_alias=True, exclude_unset=True, **exclusion_rules
        )
        if "state" in comp_task_dict:
            comp_task_dict["state"] = RUNNING_STATE_TO_DB[comp_task_dict["state"]].value
        return comp_task_dict

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        json_schema_extra={
            "examples": [
                # DB model
                {
                    "task_id": 324,
                    "project_id": "341351c4-23d1-4366-95d0-bc01386001a7",
                    "node_id": "7f62be0e-1298-4fe4-be76-66b6e859c260",
                    "job_id": None,
                    "internal_id": 3,
                    "schema": {
                        "inputs": {
                            "input_1": {
                                "label": "input_files",
                                "description": "Any input files. One or serveral files compressed in a zip will be downloaded in an inputs folder.",
                                "type": "data:*/*",
                                "displayOrder": 1.0,
                            }
                        },
                        "outputs": {
                            "output_1": {
                                "label": "Output files",
                                "description": "Output files uploaded from the outputs folder",
                                "type": "data:*/*",
                                "displayOrder": 1.0,
                            }
                        },
                    },
                    "inputs": {
                        "input_1": {
                            "nodeUuid": "48a7ac7a-cfc3-44a6-ba9b-5a1a578b922c",
                            "output": "output_1",
                        }
                    },
                    "outputs": {
                        "output_1": {
                            "store": 0,
                            "path": "341351c4-23d1-4366-95d0-bc01386001a7/7f62be0e-1298-4fe4-be76-66b6e859c260/output_1.zip",
                        }
                    },
                    "image": image_example,
                    "submit": "2021-03-01 13:07:34.19161",
                    "node_class": "INTERACTIVE",
                    "state": "NOT_STARTED",
                    "progress": 0.44,
                    "last_heartbeat": None,
                    "created": "2022-05-20 13:28:31.139",
                    "modified": "2023-06-23 15:58:32.833081",
                    "pricing_info": {
                        "pricing_plan_id": 1,
                        "pricing_unit_id": 1,
                        "pricing_unit_cost_id": 1,
                    },
                    "hardware_info": next(iter(HardwareInfo.model_config["json_schema_extra"]["examples"])),  # type: ignore
                }
                for image_example in Image.model_config["json_schema_extra"]["examples"]  # type: ignore
            ]
        },
    )
