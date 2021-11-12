# FIXME: move to settings-library or refactor

import json
import logging
from dataclasses import dataclass, fields
from typing import Final, List, Optional, Union

from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from pydantic.types import NonNegativeFloat
from simcore_postgres_database.models.comp_tasks import NodeClass
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

log = logging.getLogger(__file__)


_MINUTE: Final[int] = 60


class RabbitMQRetryPolicyUponInitialization:
    """Retry policy upon service initialization"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        logger = logger or log

        self.kwargs = dict(
            wait=wait_fixed(2),
            stop=stop_after_delay(3 * _MINUTE),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )


@dataclass
class RabbitMessageBase:
    node_id: NodeID
    user_id: UserID
    project_id: ProjectID

    @classmethod
    def from_message(cls, message: Union[str, bytes]):
        decoded_message = json.loads(message)

        converted_message = {}
        for field in fields(cls):
            if isinstance(decoded_message[field.name], (tuple, list)):
                conv = [field.type.__args__[0](e) for e in decoded_message[field.name]]
                converted_message[field.name] = conv
            else:
                converted_message[field.name] = field.type(decoded_message[field.name])

        return cls(**converted_message)


@dataclass
class LoggerRabbitMessage(RabbitMessageBase):
    messages: List[str]


@dataclass
class ProgressRabbitMessage(RabbitMessageBase):
    progress: NonNegativeFloat


@dataclass
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
