from dataclasses import dataclass

from models_library.products import ProductName
from models_library.user_preferences import NotificationsUserPreference, PreferenceName
from models_library.users import UserID
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from simcore_postgres_database.utils_user_preferences import NotificationsUserPreferencesRepo
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


def _get_user_preference_name(user_id: UserID, preference_name: PreferenceName) -> str:
    return f"{user_id}/{preference_name}"


@dataclass(frozen=True)
class UserPreferencesRepository:
    engine: AsyncEngine

    async def get_user_preferences(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
        product_name: ProductName,
        preference_class: type[NotificationsUserPreference],
    ) -> NotificationsUserPreference | None:
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            preference_payload: dict | None = await NotificationsUserPreferencesRepo.load(
                conn,
                user_id=user_id,
                product_name=product_name,
                preference_name=_get_user_preference_name(user_id, preference_class.get_preference_name()),
            )

        return None if preference_payload is None else preference_class.model_validate(preference_payload)
