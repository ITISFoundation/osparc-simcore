from typing import Final

from ...base_repository import BaseRepository
from .runs import RunsRepository
from .runs_store import RunsStoreRepository
from .step_fail_history import StepFailHistoryRepository
from .steps import StepsRepository
from .steps_lease import StepsLeaseRepository
from .user_requests import UserRequestsRepository

repositories: Final[set[type[BaseRepository]]] = {
    RunsRepository,
    RunsStoreRepository,
    StepsRepository,
    StepFailHistoryRepository,
    StepsLeaseRepository,
    UserRequestsRepository,
}


__all__: tuple[str, ...] = (
    "RunsRepository",
    "RunsStoreRepository",
    "StepFailHistoryRepository",
    "StepsLeaseRepository",
    "StepsRepository",
    "UserRequestsRepository",
    "repositories",
)
