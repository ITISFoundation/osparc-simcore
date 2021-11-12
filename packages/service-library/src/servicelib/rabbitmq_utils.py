# FIXME: move to settings-library or refactor

import logging
from dataclasses import dataclass
from typing import Final, List, Optional

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
