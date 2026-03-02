from dataclasses import dataclass

from ..repositories import UserPreferencesRepository


@dataclass(frozen=True)
class UserPreferencesService:
    user_preferences_repo: UserPreferencesRepository
