from typing import Final

from pydantic import PositiveFloat

MINUTE: Final[PositiveFloat] = 60
APP_LONG_RUNNING_MANAGER_KEY: Final[str] = (
    f"{__name__ }.long_running_tasks.tasks_manager"
)
RQT_LONG_RUNNING_TASKS_CONTEXT_KEY: Final[str] = (
    f"{__name__}.long_running_tasks.context"
)
