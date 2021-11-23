from typing import Dict, List, Optional, Union, Any
from enum import Enum

from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from pydantic import BaseModel, Field
from pydantic.types import NonNegativeFloat
from simcore_postgres_database.models.comp_tasks import NodeClass


class RabbitEventMessageType(str, Enum):
    RELOAD_IFRAME = "RELOAD_IFRAME"


class RabbitMessageBase(BaseModel):
    node_id: NodeID
    user_id: UserID
    project_id: ProjectID


class LoggerRabbitMessage(RabbitMessageBase):
    messages: List[str]


class EventRabbitMessage(RabbitMessageBase):
    action: RabbitEventMessageType
    payload: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "each action will define a different set of parameters it "
            "requires to be present"
        ),
    )


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
