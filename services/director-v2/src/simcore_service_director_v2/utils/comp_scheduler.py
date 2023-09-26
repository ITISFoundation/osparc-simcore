from typing import TypeAlias

from models_library.docker import DockerGenericTag
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_state import RunningState
from models_library.services_resources import (
    ResourceValue,
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from models_library.users import UserID
from pydantic import PositiveInt
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB

SCHEDULED_STATES: set[RunningState] = {
    RunningState.PUBLISHED,
    RunningState.PENDING,
    RunningState.WAITING_FOR_RESOURCES,
    RunningState.STARTED,
    RunningState.WAITING_FOR_CLUSTER,
}

TASK_TO_START_STATES: set[RunningState] = {
    RunningState.PUBLISHED,
    RunningState.WAITING_FOR_CLUSTER,
}

WAITING_FOR_START_STATES: set[RunningState] = {
    RunningState.PUBLISHED,
    RunningState.PENDING,
    RunningState.WAITING_FOR_RESOURCES,
    RunningState.WAITING_FOR_CLUSTER,
}

PROCESSING_STATES: set[RunningState] = {
    RunningState.PENDING,
    RunningState.WAITING_FOR_RESOURCES,
    RunningState.STARTED,
}

RUNNING_STATES: set[RunningState] = {
    RunningState.STARTED,
}

COMPLETED_STATES: set[RunningState] = {
    RunningState.ABORTED,
    RunningState.SUCCESS,
    RunningState.FAILED,
    RunningState.UNKNOWN,
}


Iteration: TypeAlias = PositiveInt


def get_resource_tracking_run_id(
    user_id: UserID, project_id: ProjectID, node_id: NodeID, iteration: Iteration
) -> str:
    return f"comp_{user_id}_{project_id}_{node_id}_{iteration}"


def create_service_resources_from_task(task: CompTaskAtDB) -> ServiceResourcesDict:
    assert task.image.node_requirements  # nosec
    return ServiceResourcesDictHelpers.create_from_single_service(
        DockerGenericTag(f"{task.image.name}:{task.image.tag}"),
        {
            res_name: ResourceValue(limit=res_value, reservation=res_value)
            for res_name, res_value in task.image.node_requirements.dict(
                by_alias=True
            ).items()
            if res_value is not None
        },
        [task.image.boot_mode],
    )
