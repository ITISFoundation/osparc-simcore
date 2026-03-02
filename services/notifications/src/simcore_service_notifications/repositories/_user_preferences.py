from dataclasses import dataclass

from models_library.products import ProductName
from models_library.user_preferences import NotificationsUserPreference, PreferenceName
from models_library.users import UserID
from simcore_postgres_database.utils_user_preferences import NotificationsUserPreferencesRepo
from sqlalchemy.ext.asyncio import AsyncEngine


def _get_user_preference_name(user_id: UserID, preference_name: PreferenceName) -> str:
    return f"{user_id}/{preference_name}"


@dataclass(frozen=True)
class UserPreferencesRepository:
    async_engine: AsyncEngine

    async def get(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        preference_class: type[NotificationsUserPreference],
    ) -> NotificationsUserPreference | None:
        async with self.async_engine.connect() as conn:
            preference_payload: dict | None = await NotificationsUserPreferencesRepo.load(
                conn,
                user_id=user_id,
                preference_name=_get_user_preference_name(user_id, preference_class.get_preference_name()),
                product_name=product_name,
            )

        return None if preference_payload is None else preference_class.model_validate(preference_payload)
