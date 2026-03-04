from dataclasses import dataclass
from typing import Any

from models_library.products import ProductName
from models_library.user_preferences import NotificationsUserPreference
from models_library.users import UserID
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from simcore_postgres_database.utils_user_preferences import NotificationsUserPreferencesRepo
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


@dataclass(frozen=True)
class UserPreferencesRepository:
    async_engine: AsyncEngine

    async def get_user_preferences(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
        product_name: ProductName,
        preference_classes: list[type[NotificationsUserPreference]],
    ) -> list[NotificationsUserPreference]:
        """Get multiple user preferences at once. Returns None for preferences that don't exist."""
        if not preference_classes:
            return []

        preference_names = [cls.get_preference_name() for cls in preference_classes]

        async with pass_or_acquire_connection(self.async_engine, connection) as conn:
            payloads: dict[str, Any] = await NotificationsUserPreferencesRepo.load_many(
                conn,
                user_id=user_id,
                product_name=product_name,
                preference_names=preference_names,
            )

        return [
            # NOTE: request order is guaranteed here
            preference_class.model_validate(payload)
            if (payload := payloads.get(preference_class.get_preference_name()))
            else preference_class()
            for preference_class in preference_classes
        ]
