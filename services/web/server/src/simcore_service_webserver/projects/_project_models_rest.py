# generated by datamodel-codegen:
#   filename:  project-v0.0.1.json
#   timestamp: 2022-01-07T13:12:29+00:00

from __future__ import annotations

import warnings
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import AnyUrl, BaseModel, EmailStr, Extra, Field, confloat, constr


class AccessRights(BaseModel):
    """
    the group id
    """

    class Config:
        extra = Extra.forbid

    read: bool = Field(..., description="gives read access")
    write: bool = Field(..., description="gives write access")
    delete: bool = Field(..., description="gives deletion rights")


class Input(BaseModel):
    class Config:
        extra = Extra.forbid

    node_uuid: UUID = Field(..., alias="nodeUuid")
    output: constr(regex=r"^[-_a-zA-Z0-9]+$")


class Input1(BaseModel):
    class Config:
        extra = Extra.forbid

    store: Union[str, int]
    dataset: Optional[str] = None
    path: str
    label: Optional[str] = None
    e_tag: Optional[str] = Field(None, alias="eTag")


class Input2(BaseModel):
    class Config:
        extra = Extra.forbid

    download_link: AnyUrl = Field(..., alias="downloadLink")
    label: Optional[str] = None


class InputAccess(Enum):
    invisible = "Invisible"
    read_only = "ReadOnly"
    read_and_write = "ReadAndWrite"


class Output(BaseModel):
    class Config:
        extra = Extra.forbid

    store: Union[str, int]
    dataset: Optional[str] = None
    path: str
    label: Optional[str] = None
    e_tag: Optional[str] = Field(None, alias="eTag")


class Output1(BaseModel):
    class Config:
        extra = Extra.forbid

    download_link: AnyUrl = Field(..., alias="downloadLink")
    label: Optional[str] = None


class Position(BaseModel):
    class Config:
        extra = Extra.forbid

    x: int = Field(..., description="The x position", example=["12"])
    y: int = Field(..., description="The y position", example=["15"])


class CurrentStatus(Enum):
    """
    the node's current state
    """

    unknown = "UNKNOWN"
    published = "PUBLISHED"
    not_started = "NOT_STARTED"
    pending = "PENDING"
    started = "STARTED"
    retry = "RETRY"
    success = "SUCCESS"
    failed = "FAILED"
    aborted = "ABORTED"


class State(BaseModel):
    class Config:
        extra = Extra.forbid

    modified: Optional[bool] = Field(
        True,
        description="true if the node's outputs need to be re-computed",
        title="Modified",
    )
    dependencies: Optional[List[UUID]] = Field(
        None,
        description="contains the node inputs dependencies if they need to be computed first",
        title="Dependencies",
    )
    current_status: Optional[CurrentStatus] = Field(
        "NOT_STARTED",
        alias="currentStatus",
        description="the node's current state",
        examples=["RUNNING", "FAILED"],
    )


class Workbench(BaseModel):
    class Config:
        extra = Extra.forbid

    key: constr(
        regex=r"^(simcore)/(services)/(comp|dynamic|frontend)(/[\w/-]+)+$"
    ) = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        examples=[
            "simcore/services/comp/sleeper",
            "simcore/services/dynamic/3dviewer",
            "simcore/services/frontend/file-picker",
        ],
    )
    version: constr(
        regex=r"^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$"
    ) = Field(
        ...,
        description="semantic version number of the node",
        examples=["1.0.0", "0.0.1"],
    )
    label: str = Field(
        ..., description="The short name of the node", example=["JupyterLab"]
    )
    progress: Optional[confloat(ge=0.0, le=100.0)] = Field(
        None, description="the node progress value"
    )
    thumbnail: Optional[AnyUrl] = Field(
        None,
        description="url of the latest screenshot of the node",
        examples=["https://placeimg.com/171/96/tech/grayscale/?0.jpg"],
    )
    run_hash: Optional[Optional[str]] = Field(
        None,
        alias="runHash",
        description="the hex digest of the resolved inputs +outputs hash at the time when the last outputs were generated",
        examples=["a4337bc45a8fc544c03f52dc550cd6e1e87021bc896588bd79e901e2"],
    )
    inputs: Optional[
        Dict[
            constr(regex=r"^[-_a-zA-Z0-9]+$"),
            Union[Optional[Union[int, bool, str, float]], Input, Input1, Input2],
        ]
    ] = Field(None, description="values of input properties")
    input_access: Optional[
        Dict[constr(regex=r"^[-_a-zA-Z0-9]+$"), InputAccess]
    ] = Field(
        None, alias="inputAccess", description="map with key - access level pairs"
    )
    input_nodes: Optional[List[UUID]] = Field(
        None,
        alias="inputNodes",
        description="node IDs of where the node is connected to",
        examples=["nodeUuid1", "nodeUuid2"],
    )
    outputs: Optional[
        Dict[
            constr(regex=r"^[-_a-zA-Z0-9]+$"),
            Union[Optional[Union[int, bool, str, float]], Output, Output1],
        ]
    ] = {}
    output_node: Optional[bool] = Field(None, alias="outputNode")
    output_nodes: Optional[List[UUID]] = Field(
        None,
        alias="outputNodes",
        description="Used in group-nodes. Node IDs of those connected to the output",
        examples=["nodeUuid1", "nodeUuid2"],
    )
    parent: Optional[Optional[str]] = Field(
        None,
        description="Parent's (group-nodes') node ID s.",
        examples=["nodeUuid1", "nodeUuid2"],
    )
    position: Optional[Position] = None
    state: Optional[State] = Field(None, title="NodeState")


class Position1(BaseModel):
    class Config:
        extra = Extra.forbid

    x: int = Field(..., description="The x position", example=["12"])
    y: int = Field(..., description="The y position", example=["15"])


class Workbench1(BaseModel):
    class Config:
        extra = Extra.forbid

    position: Position1


class Slideshow(BaseModel):
    class Config:
        extra = Extra.forbid

    position: int = Field(..., description="Slide's position", examples=[0, 2])
    description: str = Field(
        ...,
        description="Description or instructions about what to do in this step",
        examples=[
            "This is a **sleeper**",
            "Please, select the config file defined [in this link](asdf)"
        ]
    )


class Ui(BaseModel):
    class Config:
        extra = Extra.allow

    workbench: Optional[
        Dict[
            constr(
                regex=r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?4[0-9a-fA-F]{3}-?[89abAB][0-9a-fA-F]{3}-?[0-9a-fA-F]{12}$"
            ),
            Workbench1,
        ]
    ] = None
    slideshow: Optional[
        Dict[
            constr(
                regex=r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?4[0-9a-fA-F]{3}-?[89abAB][0-9a-fA-F]{3}-?[0-9a-fA-F]{12}$"
            ),
            Slideshow,
        ]
    ] = None
    current_node_id: Optional[UUID] = Field(None, alias="currentNodeId")


class Owner(BaseModel):
    """
    If locked, the user that owns the lock
    """

    user_id: int = Field(
        ...,
        description="Owner's identifier when registered in the user's database table",
        example=[2],
        title="User Id",
    )
    first_name: str = Field(
        ..., description="Owner first name", example=["John"], title="First Name"
    )
    last_name: str = Field(
        ..., description="Owner last name", example=["Smith"], title="Last Name"
    )


class Status(Enum):
    """
    The status of the project
    """

    closed = "CLOSED"
    closing = "CLOSING"
    cloning = "CLONING"
    opening = "OPENING"
    exporting = "EXPORTING"
    opened = "OPENED"


class Locked(BaseModel):
    """
    The project lock state
    """

    value: bool = Field(..., description="True if the project is locked", title="Value")
    owner: Optional[Owner] = Field(
        None, description="If locked, the user that owns the lock", title="Owner"
    )
    status: Status = Field(..., description="The status of the project", title="Status")


class Value(Enum):
    """
    An enumeration.
    """

    unknown = "UNKNOWN"
    not_started = "NOT_STARTED"
    published = "PUBLISHED"
    pending = "PENDING"
    started = "STARTED"
    retry = "RETRY"
    success = "SUCCESS"
    failed = "FAILED"
    aborted = "ABORTED"


class State1(BaseModel):
    """
    The project running state
    """

    value: Value = Field(..., description="An enumeration.", title="RunningState")


class StateItem(BaseModel):
    class Config:
        extra = Extra.forbid

    locked: Locked = Field(..., description="The project lock state", title="Locked")
    state: State1 = Field(..., description="The project running state", title="State")


class SimcoreProject(BaseModel):
    """
    Description of a simcore project
    """

    class Config:
        extra = Extra.forbid

    uuid: UUID = Field(
        ...,
        description="project unique identifier",
        examples=[
            "07640335-a91f-468c-ab69-a374fa82078d",
            "9bcf8feb-c1b1-41b6-b201-639cd6ccdba8",
        ],
    )
    name: str = Field(
        ..., description="project name", examples=["Temporal Distortion Simulator"]
    )
    description: str = Field(
        ...,
        description="longer one-line description about the project",
        examples=["Dabbling in temporal transitions ..."],
    )
    prj_owner: EmailStr = Field(..., alias="prjOwner", description="user email")
    access_rights: Dict[constr(regex=r"^\S+$"), AccessRights] = Field(
        ...,
        alias="accessRights",
        description="object containing the GroupID as key and read/write/execution permissions as value",
    )
    creation_date: constr(
        regex=r"\d{4}-(12|11|10|0?[1-9])-(31|30|[0-2]?\d)T(2[0-3]|1\d|0?[0-9])(:(\d|[0-5]\d)){2}(\.\d{3})?Z"
    ) = Field(
        ...,
        alias="creationDate",
        description="project creation date",
        examples=["2018-07-01T11:13:43Z"],
    )
    last_change_date: constr(
        regex=r"\d{4}-(12|11|10|0?[1-9])-(31|30|[0-2]?\d)T(2[0-3]|1\d|0?[0-9])(:(\d|[0-5]\d)){2}(\.\d{3})?Z"
    ) = Field(
        ...,
        alias="lastChangeDate",
        description="last save date",
        examples=["2018-07-01T11:13:43Z"],
    )
    thumbnail: AnyUrl = Field(
        ...,
        description="url of the latest screenshot of the project",
        examples=["https://placeimg.com/171/96/tech/grayscale/?0.jpg"],
    )
    workbench: Dict[
        constr(
            regex=r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?4[0-9a-fA-F]{3}-?[89abAB][0-9a-fA-F]{3}-?[0-9a-fA-F]{12}$"
        ),
        Workbench,
    ]
    ui: Optional[Ui] = None
    tags: Optional[List[int]] = None
    classifiers: Optional[List[str]] = Field(
        None,
        description="Contains the reference to the project classifiers",
        examples=["some:id:to:a:classifier"],
    )
    dev: Optional[Dict[str, Any]] = Field(
        None, description="object used for development purposes only"
    )
    state: Optional[Optional[StateItem]] = Field(
        None, description="Project state", title="State"
    )
    quality: Optional[Dict[str, Any]] = Field(
        None,
        description="Object containing Quality Assessment related data",
        title="Quality",
    )


warnings.warn("DO NOT USE IN PRODUCTION, STILL UNDER DEVELOPMENT")
ProjectSchema = SimcoreProject
