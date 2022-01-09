"""
Adds type hints to data structures in responses from docker daemon (typically included in docker sdk and aiodocker libraries)
"""

from typing import Dict, List, TypedDict

UrlStr = str
DateTimeStr = str


#
# Docker API JSON bodies
#  NOTE: These are incomplete but we are building them upon need
#


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
    Timestamp: str
    State: str
    Message: str

    # TODO: represent each state of StatusDict as
    # class TaskDict:
    #    Status: Union[ StatusDict0, StatusDict1, etc]?
    # e.g. in StatusDict1 we add
    # ContainerStatus:

    PortStatus: Dict


class VersionDict(TypedDict):
    Index: int


class TaskDict(TypedDict):
    """
    docker inspect $(docker service ps $(docker service ls --filter="name=pytest-simcore_storage" -q) -q)
    """

    ID: str
    Version: VersionDict
    CreatedAt: DateTimeStr
    UpdatedAt: DateTimeStr
    Labels: str
    Spec: TaskSpecDict
    ServiceID: str
    NodeID: str
    Slot: int
    Status: Dict
    DesiredState: str
    NetworkAttachments: List[Dict]
    # ...


UrlStr = str
