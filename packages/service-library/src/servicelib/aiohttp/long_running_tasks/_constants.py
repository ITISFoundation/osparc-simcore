from typing import Final

from pydantic import PositiveFloat

MINUTE: Final[PositiveFloat] = 60
APP_LONG_RUNNING_TASKS_MANAGER_KEY: Final[str] = f"{__name__ }.long_running_tasks"
