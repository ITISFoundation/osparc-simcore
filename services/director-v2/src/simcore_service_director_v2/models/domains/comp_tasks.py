from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, Optional

from models_library.basic_regex import VERSION_RE
from models_library.errors import ErrorDict
from models_library.projects import ProjectID
from models_library.projects_nodes import InputsDict, NodeID, OutputsDict
from models_library.projects_state import RunningState
from models_library.services import (
    KEY_RE,
    PropertyName,
    ServiceInputsDict,
    ServiceOutput,
)
from pydantic import BaseModel, Extra, Field, validator
from pydantic.types import PositiveInt
from simcore_postgres_database.models.comp_tasks import NodeClass, StateType

from ...utils.db import DB_TO_RUNNING_STATE, RUNNING_STATE_TO_DB
from ..schemas.services import NodeRequirements


class Image(BaseModel):
    name: str = Field(..., regex=KEY_RE)
    tag: str = Field(..., regex=VERSION_RE)
    requires_gpu: Optional[bool] = Field(None, deprecated=True)
    requires_mpi: Optional[bool] = Field(None, deprecated=True)
    node_requirements: NodeRequirements = Field(
        None, description="the requirements for the service to run on a node"
    )

    @validator("node_requirements", pre=True, always=True)
    @classmethod
    def migrate_from_requirements(cls, v, values):
        if v is None:
            v = NodeRequirements(
                CPU=1.0,
                GPU=1 if values.get("requires_gpu") else 0,
                RAM="128 MiB",
                MPI=1 if values.get("requires_mpi") else 0,
            )
        return v

    class Config:
        orm_mode = True
        schema_extra = {
            "examples": [
                {
                    "name": "simcore/services/dynamic/jupyter-octave-python-math",
                    "tag": "1.3.1",
                    "node_requirements": node_req_example,
                }
                for node_req_example in NodeRequirements.Config.schema_extra["examples"]
            ]
        }


# NOTE: for a long time defaultValue field was added to ServiceOutput wrongly in the DB.
# this flags allows parsing of the outputs without error. This MUST not leave the director-v2!
class _ServiceOutputOverride(ServiceOutput):
    class Config(ServiceOutput.Config):
        extra = Extra.ignore


_ServiceOutputsOverride = Dict[PropertyName, _ServiceOutputOverride]


class NodeSchema(BaseModel):
    inputs: ServiceInputsDict = Field(..., description="the inputs scheam")
    outputs: _ServiceOutputsOverride = Field(..., description="the outputs schema")

    class Config:
        extra = Extra.forbid
        orm_mode = True


class CompTaskAtDB(BaseModel):
    project_id: ProjectID
    node_id: NodeID
    job_id: Optional[str] = Field(None, description="The worker job ID")
    node_schema: NodeSchema = Field(..., alias="schema")
    inputs: Optional[InputsDict] = Field(..., description="the inputs payload")
    outputs: Optional[OutputsDict] = Field({}, description="the outputs payload")
    run_hash: Optional[str] = Field(
        None,
        description="the hex digest of the resolved inputs +outputs hash at the time when the last outputs were generated",
    )
    image: Image
    submit: datetime
    start: Optional[datetime]
    end: Optional[datetime]
    state: RunningState
    task_id: Optional[PositiveInt]
    internal_id: PositiveInt
    node_class: NodeClass
    errors: Optional[list[ErrorDict]]

    @validator("state", pre=True)
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

    def to_db_model(self, **exclusion_rules) -> Dict[str, Any]:
        comp_task_dict = self.dict(by_alias=True, exclude_unset=True, **exclusion_rules)
        if "state" in comp_task_dict:
            comp_task_dict["state"] = RUNNING_STATE_TO_DB[comp_task_dict["state"]].value
        return comp_task_dict

    class Config:
        extra = Extra.forbid
        orm_mode = True
        schema_extra = {
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
                            "store": "0",
                            "path": "341351c4-23d1-4366-95d0-bc01386001a7/7f62be0e-1298-4fe4-be76-66b6e859c260/output_1.zip",
                        }
                    },
                    "image": image_example,
                    "submit": "2021-03-01 13:07:34.19161",
                    "node_class": "INTERACTIVE",
                    "state": "NOT_STARTED",
                }
                for image_example in Image.Config.schema_extra["examples"]
            ]
        }
