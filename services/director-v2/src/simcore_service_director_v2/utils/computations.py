import logging
import re
from datetime import datetime
from typing import List, Set

from models_library.project_nodes import KEY_RE, RunningState

from ..models.domains.comp_tasks import CompTaskAtDB
from ..modules.db.tables import NodeClass

log = logging.getLogger(__file__)


def get_pipeline_state_from_task_states(
    tasks: List[CompTaskAtDB], publication_timeout: int
) -> RunningState:

    # compute pipeline state from task states
    now = datetime.utcnow()
    if tasks:
        # put in a set of unique values
        set_states: Set[RunningState] = {task.state for task in tasks}
        last_update = max([t.submit for t in tasks])
        if len(set_states) == 1:
            # this is typically for success, pending, published
            the_state = next(iter(set_states))
            if the_state == RunningState.PUBLISHED:
                # FIXME: this should be done automatically after the timeout!!
                if (now - last_update).seconds > publication_timeout:
                    return RunningState.NOT_STARTED
            return the_state

        if all(s in [RunningState.SUCCESS, RunningState.PENDING] for s in set_states):
            # this is a started pipeline
            return RunningState.STARTED

        # we have more than one state, let's check by order of priority
        for state in [
            RunningState.FAILED,  # task is failed -> pipeline as well
            RunningState.ABORTED,  # task aborted
            RunningState.STARTED,  # task is started or retrying
            RunningState.PENDING,
        ]:
            if state in set_states:
                return state

    return RunningState.NOT_STARTED


_node_key_re = re.compile(KEY_RE)
_STR_TO_NODECLASS = {
    "comp": NodeClass.COMPUTATIONAL,
    "dynamic": NodeClass.INTERACTIVE,
    "frontend": NodeClass.FRONTEND,
}


def to_node_class(service_key: str) -> NodeClass:
    match = _node_key_re.match(service_key)
    if match:
        return _STR_TO_NODECLASS.get(match.group(3))
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
