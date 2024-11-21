import datetime as dt
import logging
from typing import Any

import arrow
from models_library.projects_state import RunningState
from models_library.services import ServiceKeyVersion
from models_library.services_regex import SERVICE_KEY_RE
from models_library.users import UserID
from servicelib.utils import logged_gather

from ..models.comp_tasks import CompTaskAtDB
from ..modules.catalog import CatalogClient
from ..modules.db.tables import NodeClass

_logger = logging.getLogger(__name__)

_COMPLETED_STATES = (RunningState.ABORTED, RunningState.FAILED, RunningState.SUCCESS)
_RUNNING_STATES = (RunningState.STARTED,)
_TASK_TO_PIPELINE_CONVERSIONS = {
    # tasks are initially in NOT_STARTED state, then they transition to published
    (RunningState.PUBLISHED, RunningState.NOT_STARTED): RunningState.PUBLISHED,
    # if there are tasks waiting for clusters, then the pipeline is also waiting for a cluster
    (
        RunningState.PUBLISHED,
        RunningState.NOT_STARTED,
        RunningState.WAITING_FOR_CLUSTER,
    ): RunningState.WAITING_FOR_CLUSTER,
    # if there are PENDING states that means the pipeline was published and is awaiting sidecars
    (
        RunningState.PENDING,
        RunningState.PUBLISHED,
        RunningState.NOT_STARTED,
    ): RunningState.PENDING,
    # if there are only completed states without FAILED and NOT_STARTED -> ABORTED
    (
        RunningState.SUCCESS,
        RunningState.ABORTED,
    ): RunningState.ABORTED,
    # if there are only completed states without FAILED -> NOT_STARTED
    (
        RunningState.SUCCESS,
        RunningState.ABORTED,
        RunningState.NOT_STARTED,
    ): RunningState.NOT_STARTED,
    # if there are only completed states with FAILED --> FAILED
    (*_COMPLETED_STATES,): RunningState.FAILED,
    # if there are only completed states with FAILED and not started ones --> NOT_STARTED
    (
        *_COMPLETED_STATES,
        RunningState.NOT_STARTED,
    ): RunningState.NOT_STARTED,
    # the generic case where we have a combination of completed states, running states,
    # or published/pending tasks, not_started is a started pipeline
    (
        *_COMPLETED_STATES,
        *_RUNNING_STATES,
        RunningState.PUBLISHED,
        RunningState.PENDING,
        RunningState.NOT_STARTED,
        RunningState.WAITING_FOR_CLUSTER,
    ): RunningState.STARTED,
}


def get_pipeline_state_from_task_states(tasks: list[CompTaskAtDB]) -> RunningState:
    # compute pipeline state from task states
    if not tasks:
        return RunningState.UNKNOWN
    # put in a set of unique values
    set_states: set[RunningState] = {task.state for task in tasks}
    if len(set_states) == 1:
        # there is only one state, so it's the one
        return next(iter(set_states))

    for option, result in _TASK_TO_PIPELINE_CONVERSIONS.items():
        if set_states.issubset(option):
            return result

    return RunningState.UNKNOWN


_STR_TO_NODECLASS = {
    "comp": NodeClass.COMPUTATIONAL,
    "dynamic": NodeClass.INTERACTIVE,
    "frontend": NodeClass.FRONTEND,
}


def to_node_class(service_key: str) -> NodeClass:
    match = SERVICE_KEY_RE.match(service_key)
    if match:
        node_class = _STR_TO_NODECLASS.get(match.group("type"))
        if node_class:
            return node_class
    raise ValueError


def is_pipeline_running(pipeline_state: RunningState) -> bool:
    is_running: bool = pipeline_state.is_running()
    return is_running


def is_pipeline_stopped(pipeline_state: RunningState) -> bool:
    return not pipeline_state.is_running()


async def find_deprecated_tasks(
    user_id: UserID,
    product_name: str,
    task_key_versions: list[ServiceKeyVersion],
    catalog_client: CatalogClient,
) -> list[ServiceKeyVersion]:
    services_details = await logged_gather(
        *(
            catalog_client.get_service(
                user_id=user_id,
                service_key=key_version.key,
                service_version=key_version.version,
                product_name=product_name,
            )
            for key_version in set(task_key_versions)
        )
    )
    service_key_version_to_details = {
        ServiceKeyVersion.model_construct(
            key=details["key"], version=details["version"]
        ): details
        for details in services_details
    }
    today = dt.datetime.now(tz=dt.UTC)

    def _is_service_deprecated(service: dict[str, Any]) -> bool:
        if deprecation_date := service.get("deprecated"):
            deprecation_date = arrow.get(deprecation_date).datetime.replace(
                tzinfo=dt.UTC
            )
            is_deprecated: bool = today > deprecation_date
            return is_deprecated
        return False

    return [
        task
        for task in task_key_versions
        if _is_service_deprecated(service_key_version_to_details[task])
    ]
