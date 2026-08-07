from dataclasses import dataclass
from typing import Literal

from models_library.projects import ProjectID
from models_library.rabbitmq_messages import RabbitMessageBase
from models_library.users import UserID
from pydantic import PositiveInt

from ...models.comp_runs import Iteration, RunMetadataDict
from ...models.comp_tasks import CompTaskAtDB


class SchedulePipelineRabbitMessage(RabbitMessageBase):
    channel_name: Literal["simcore.services.director-v2.scheduling"] = "simcore.services.director-v2.scheduling"
    user_id: UserID
    project_id: ProjectID
    iteration: Iteration

    def routing_key(self) -> str | None:  # pylint: disable=no-self-use # abstract
        return None


class ReleaseTaskResultRabbitMessage(RabbitMessageBase):
    channel_name: Literal["simcore.services.director-v2.release-task-result"] = (
        "simcore.services.director-v2.release-task-result"
    )
    user_id: UserID
    project_id: ProjectID
    run_id: PositiveInt
    use_on_demand_clusters: bool
    run_metadata: RunMetadataDict
    job_ids: list[str]

    def routing_key(self) -> str | None:  # pylint: disable=no-self-use # abstract
        return None


@dataclass(frozen=True, slots=True)
class TaskStateTracker:
    previous: CompTaskAtDB
    current: CompTaskAtDB
