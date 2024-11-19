from typing import Literal, TypeAlias

from models_library.projects import ProjectID
from models_library.rabbitmq_messages import RabbitMessageBase
from models_library.users import UserID
from pydantic import PositiveInt

Iteration: TypeAlias = PositiveInt


class SchedulePipelineRabbitMessage(RabbitMessageBase):
    channel_name: Literal[
        "simcore.services.director-v2.scheduling"
    ] = "simcore.services.director-v2.scheduling"
    user_id: UserID
    project_id: ProjectID
    iteration: Iteration

    def routing_key(self) -> str | None:
        return None
