from enum import Enum
from typing import Literal, Optional, Union

from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from pydantic import BaseModel
from pydantic.types import NonNegativeFloat
from simcore_postgres_database.models.comp_tasks import NodeClass


class RabbitEventMessageType(str, Enum):
    RELOAD_IFRAME = "RELOAD_IFRAME"


class RabbitMessageBase(BaseModel):
    channel_name: str
    node_id: NodeID
    user_id: UserID
    project_id: ProjectID


class LoggerRabbitMessage(RabbitMessageBase):
    channel_name: Literal["simcore.services.logs"] = "simcore.services.logs"
    messages: list[str]


class EventRabbitMessage(RabbitMessageBase):
    channel_name: Literal["simcore.services.events"] = "simcore.services.events"
    action: RabbitEventMessageType


class ProgressRabbitMessage(RabbitMessageBase):
    channel_name: Literal["simcore.services.progress"] = "simcore.services.progress"
    progress: NonNegativeFloat


class InstrumentationRabbitMessage(RabbitMessageBase):
    channel_name: Literal[
        "simcore.services.instrumentation"
    ] = "simcore.services.instrumentation"
    metrics: str
    service_uuid: NodeID
    service_type: NodeClass
    service_key: str
    service_tag: str
    result: Optional[RunningState] = None


RabbitMessageTypes = Union[
    LoggerRabbitMessage, ProgressRabbitMessage, InstrumentationRabbitMessage
]
