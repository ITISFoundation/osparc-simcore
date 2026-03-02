from dataclasses import dataclass

from models_library.products import ProductName
from models_library.user_preferences import NotificationsUserPreference
from models_library.users import UserID

from ..repositories import UserPreferencesRepository


@dataclass(frozen=True)
class UserPreferencesService:
    user_preferences_repo: UserPreferencesRepository

    async def get_user_preference(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        preference_class: type[NotificationsUserPreference],
    ) -> NotificationsUserPreference | None:
        return await self.user_preferences_repo.get_user_preferences(
            user_id=user_id,
            product_name=product_name,
            preference_class=preference_class,
        )
