"""
Adds type hints to data structures in responses from docker daemon (typically included in docker sdk and aiodocker libraries)
"""

from typing import Dict, List, TypedDict

UrlStr = str
DateTimeStr = str


class ServiceSpecDict(TypedDict):
    """
    docker service inspect $(id) | jq ".[0].Spec | keys"
    """

    EndpointSpec: Dict
    Labels: Dict[str, str]
    Mode: Dict
    Name: str
    RollbackConfig: Dict
    TaskTemplate: Dict
    UpdateConfig: Dict


class ServiceDict(TypedDict):
    """
    docker service inspect $(id) | jq ".[0] | keys"
    """

    ID: str
    Version: Dict
    CreatedAt: DateTimeStr
    UpdatedAt: DateTimeStr
    Spec: ServiceSpecDict
    Endpoint: Dict


class ContainerSpec(TypedDict):
    Image: str
    Labels: Dict[str, str]
    Hostname: str


class TaskSpecDict(TypedDict):
    ContainerSpec: ContainerSpec


class StatusDict(TypedDict):
    State: str


class TaskDict(TypedDict):
    ID: str
    Version: str
    CreatedAt: DateTimeStr
    UpdatedAt: DateTimeStr
    Labels: str
    Spec: TaskSpecDict
    ServiceID: str
    Slot: int
    Status: Dict
    DesiredState: str
    NetworkAttachments: List[Dict]


UrlStr = str
