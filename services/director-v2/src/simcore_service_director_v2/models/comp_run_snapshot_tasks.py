from contextlib import suppress
from datetime import datetime
from typing import Annotated, Any

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.resource_tracker import HardwareInfo
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    PositiveInt,
    field_validator,
)
from simcore_postgres_database.models.comp_pipeline import StateType

from ..utils.db import DB_TO_RUNNING_STATE
from .comp_tasks import BaseCompTaskAtDB, Image


class CompRunSnapshotTaskAtDBGet(BaseCompTaskAtDB):
    snapshot_task_id: PositiveInt
    run_id: PositiveInt

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        json_schema_extra={
            "examples": [
                # DB model
                {
                    "snapshot_task_id": 324,
                    "run_id": 123,
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
                    "hardware_info": next(
                        iter(HardwareInfo.model_config["json_schema_extra"]["examples"])  # type: ignore
                    ),
                }
                for image_example in Image.model_config["json_schema_extra"]["examples"]  # type: ignore
            ]
        },
    )


class CompRunSnapshotTaskAtDBCreate(BaseCompTaskAtDB):
    run_id: PositiveInt


def _none_to_zero_float_pre_validator(value: Any):
    if value is None:
        return 0.0
    return value


class CompRunSnapshotTaskDBGet(BaseModel):
    snapshot_task_id: PositiveInt
    run_id: PositiveInt
    project_uuid: ProjectID
    node_id: NodeID
    state: RunningState
    progress: Annotated[float, BeforeValidator(_none_to_zero_float_pre_validator)]
    image: dict[str, Any]
    started_at: datetime | None
    ended_at: datetime | None
    iteration: PositiveInt

    @field_validator("state", mode="before")
    @classmethod
    def convert_result_from_state_type_enum_if_needed(cls, v):
        if isinstance(v, str):
            # try to convert to a StateType, if it fails the validations will continue
            # and pydantic will try to convert it to a RunninState later on
            with suppress(ValueError):
                v = StateType(v)
        if isinstance(v, StateType):
            return RunningState(DB_TO_RUNNING_STATE[StateType(v)])
        return v
