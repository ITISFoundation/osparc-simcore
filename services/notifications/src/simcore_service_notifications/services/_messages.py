from dataclasses import dataclass

from ._templates import TemplatesService
from ._user_preferences import UserPreferencesService


@dataclass(frozen=True)
class MessagesService:
    templates_service: TemplatesService
    user_preferences_service: UserPreferencesService
