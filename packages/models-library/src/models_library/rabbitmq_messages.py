from enum import Enum
from typing import Optional, Union

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from pydantic import BaseModel
from pydantic.types import NonNegativeFloat
from simcore_postgres_database.models.comp_tasks import NodeClass


class RabbitEventMessageType(str, Enum):
    RELOAD_IFRAME = "RELOAD_IFRAME"


class RabbitMessageBase(BaseModel):
    node_id: NodeID
    user_id: UserID
    project_id: ProjectID


class LoggerRabbitMessage(RabbitMessageBase):
    messages: list[str]


class EventRabbitMessage(RabbitMessageBase):
    action: RabbitEventMessageType


class ProgressRabbitMessage(RabbitMessageBase):
    progress: NonNegativeFloat


class InstrumentationRabbitMessage(RabbitMessageBase):
    metrics: str
    service_uuid: NodeID
    service_type: NodeClass
    service_key: str
    service_tag: str
    result: Optional[RunningState] = None


RabbitMessageTypes = Union[
    LoggerRabbitMessage, ProgressRabbitMessage, InstrumentationRabbitMessage
]
