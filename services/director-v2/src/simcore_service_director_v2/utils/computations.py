import logging
import re
from typing import List, Set

from models_library.projects_state import RunningState
from models_library.services import SERVICE_KEY_RE

from ..models.domains.comp_tasks import CompTaskAtDB
from ..modules.db.tables import NodeClass

log = logging.getLogger(__file__)

_COMPLETED_STATES = {RunningState.ABORTED, RunningState.FAILED, RunningState.SUCCESS}
_RUNNING_STATES = {RunningState.STARTED, RunningState.RETRY}


def get_pipeline_state_from_task_states(tasks: List[CompTaskAtDB]) -> RunningState:

    # compute pipeline state from task states
    if tasks:
        # put in a set of unique values
        set_states: Set[RunningState] = {task.state for task in tasks}
        if len(set_states) == 1:
            # this is typically for success, pending, published
            the_state = next(iter(set_states))
            return the_state

        # tasks are initially in NOT_STARTED state, then they transition to published
        if set_states.issubset({RunningState.PUBLISHED, RunningState.NOT_STARTED}):
            return RunningState.PUBLISHED

        # if there are PENDING states that means the pipeline was published and is awaiting sidecars
        if set_states.issubset(
            {RunningState.PENDING, RunningState.PUBLISHED, RunningState.NOT_STARTED}
        ):
            return RunningState.PENDING

        # if there are only completed states without FAILED
        if set_states.issubset(
            {RunningState.SUCCESS, RunningState.ABORTED, RunningState.NOT_STARTED}
        ):
            return RunningState.ABORTED

        # if there are only completed states with FAILED --> FAILED
        if set_states.issubset(
            {
                *_COMPLETED_STATES,
                RunningState.NOT_STARTED,
            }
        ):
            return RunningState.FAILED

        # the generic case where we have a combination of completed states, running states,
        # or published/pending tasks, not_started is a started pipeline
        return RunningState.STARTED
    return RunningState.UNKNOWN


_node_key_re = re.compile(SERVICE_KEY_RE)
_STR_TO_NODECLASS = {
    "comp": NodeClass.COMPUTATIONAL,
    "dynamic": NodeClass.INTERACTIVE,
    "frontend": NodeClass.FRONTEND,
}


def to_node_class(service_key: str) -> NodeClass:
    match = _node_key_re.match(service_key)
    if match:
        node_class = _STR_TO_NODECLASS.get(match.group(3))
        if node_class:
            return node_class
    raise ValueError


def is_pipeline_running(pipeline_state: RunningState) -> bool:
    return pipeline_state in [
        RunningState.PUBLISHED,
        RunningState.PENDING,
        RunningState.STARTED,
        RunningState.RETRY,
    ]


def is_pipeline_stopped(pipeline_state: RunningState) -> bool:
    return not is_pipeline_running(pipeline_state)
