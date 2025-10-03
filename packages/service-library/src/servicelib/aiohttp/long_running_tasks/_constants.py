from typing import Final

from pydantic import PositiveFloat

MINUTE: Final[PositiveFloat] = 60

RQT_LONG_RUNNING_TASKS_CONTEXT_KEY: Final[str] = (
    f"{__name__}.long_running_tasks.context"
)
