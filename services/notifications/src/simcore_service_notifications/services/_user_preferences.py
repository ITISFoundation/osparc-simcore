from dataclasses import dataclass

from models_library.products import ProductName
from models_library.users import UserID

from ..models.user_preferences import (
    NotificationsEmailSubscriptionPreference,
    NotificationsGlobalSubscriptionPreference,
)
from ..repositories import UserPreferencesRepository


@dataclass(frozen=True)
class UserPreferencesService:
    user_preferences_repo: UserPreferencesRepository

    async def is_subscribed_to_email_notifications(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
    ) -> bool:
        (
            global_pref,
            email_pref,
        ) = await self.user_preferences_repo.get_user_preferences(
            user_id=user_id,
            product_name=product_name,
            preference_classes=(
                NotificationsGlobalSubscriptionPreference,
                NotificationsEmailSubscriptionPreference,
            ),
        )

        return global_pref.value and email_pref.value
