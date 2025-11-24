from copy import deepcopy
from typing import Final

from servicelib.long_running_tasks.models import TaskData

TEST_CHECK_STALE_INTERVAL_S: Final[float] = 1


def without_marked_for_removal_at(task_data: TaskData) -> TaskData:
    data = deepcopy(task_data)
    data.marked_for_removal_at = None
    return data
