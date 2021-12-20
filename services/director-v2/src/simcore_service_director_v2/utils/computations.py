import logging
import re
from typing import List, Set

from models_library.projects_state import RunningState
from models_library.services import SERVICE_KEY_RE

from ..models.domains.comp_tasks import CompTaskAtDB
from ..modules.db.tables import NodeClass

log = logging.getLogger(__file__)

_COMPLETED_STATES = (RunningState.ABORTED, RunningState.FAILED, RunningState.SUCCESS)
_RUNNING_STATES = (RunningState.STARTED, RunningState.RETRY)
_TASK_TO_PIPELINE_CONVERSIONS = {
    # tasks are initially in NOT_STARTED state, then they transition to published
    (RunningState.PUBLISHED, RunningState.NOT_STARTED): RunningState.PUBLISHED,
    # if there are PENDING states that means the pipeline was published and is awaiting sidecars
    (
        RunningState.PENDING,
        RunningState.PUBLISHED,
        RunningState.NOT_STARTED,
    ): RunningState.PENDING,
    # if there are only completed states without FAILED
    (
        RunningState.SUCCESS,
        RunningState.ABORTED,
        RunningState.NOT_STARTED,
    ): RunningState.ABORTED,
    # if there are only completed states with FAILED --> FAILED
    (
        *_COMPLETED_STATES,
        RunningState.NOT_STARTED,
    ): RunningState.FAILED,
    # the generic case where we have a combination of completed states, running states,
    # or published/pending tasks, not_started is a started pipeline
    (
        *_COMPLETED_STATES,
        *_RUNNING_STATES,
        RunningState.PUBLISHED,
        RunningState.PENDING,
        RunningState.NOT_STARTED,
    ): RunningState.STARTED,
}


def get_pipeline_state_from_task_states(tasks: List[CompTaskAtDB]) -> RunningState:

    # compute pipeline state from task states
    if not tasks:
        return RunningState.UNKNOWN
    # put in a set of unique values
    set_states: Set[RunningState] = {task.state for task in tasks}
    if len(set_states) == 1:
        # there is only one state, so it's the one
        the_state = next(iter(set_states))
        return the_state

    for option, result in _TASK_TO_PIPELINE_CONVERSIONS.items():
        if set_states.issubset(option):
            return result

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
