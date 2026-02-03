from typing import Final

from ...base_repository import BaseRepository
from .runs import RunsRepository
from .runs_store import RunsStoreRepository
from .steps import StepsRepository
from .steps_history import StepsHistoryRepository
from .steps_lease import StepsLeaseRepository
from .user_requests import UserRequestsRepository

repositories: Final[set[type[BaseRepository]]] = {
    RunsRepository,
    RunsStoreRepository,
    StepsRepository,
    StepsHistoryRepository,
    StepsLeaseRepository,
    UserRequestsRepository,
}


__all__: tuple[str, ...] = (
    "RunsRepository",
    "RunsStoreRepository",
    "StepsHistoryRepository",
    "StepsLeaseRepository",
    "StepsRepository",
    "UserRequestsRepository",
    "repositories",
)
