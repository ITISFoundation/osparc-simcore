from dataclasses import dataclass
from typing import Any, overload

from models_library.products import ProductName
from models_library.user_preferences import NotificationsUserPreference
from models_library.users import UserID
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from simcore_postgres_database.utils_user_preferences import NotificationsUserPreferencesRepo
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


@dataclass(frozen=True)
class UserPreferencesRepository:
    async_engine: AsyncEngine

    @overload
    async def get_user_preferences[P: NotificationsUserPreference](
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
        product_name: ProductName,
        preference_classes: tuple[type[P]],
    ) -> tuple[P]: ...

    # Two preferences
    @overload
    async def get_user_preferences[P1: NotificationsUserPreference, P2: NotificationsUserPreference](
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
        product_name: ProductName,
        preference_classes: tuple[type[P1], type[P2]],
    ) -> tuple[P1, P2]: ...

    # Three preferences
    @overload
    async def get_user_preferences[
        P1: NotificationsUserPreference,
        P2: NotificationsUserPreference,
        P3: NotificationsUserPreference,
    ](
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
        product_name: ProductName,
        preference_classes: tuple[type[P1], type[P2], type[P3]],
    ) -> tuple[P1, P2, P3]: ...

    async def get_user_preferences(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
        product_name: ProductName,
        preference_classes: tuple[type[NotificationsUserPreference], ...],
    ) -> tuple[NotificationsUserPreference, ...]:
        assert isinstance(preference_classes, tuple), "preference_classes must be a tuple, not a list or other type"

        if not preference_classes:
            return ()

        preference_names = [cls.get_preference_name() for cls in preference_classes]

        async with pass_or_acquire_connection(self.async_engine, connection) as conn:
            payloads: dict[str, Any] = await NotificationsUserPreferencesRepo.load_many(
                conn,
                user_id=user_id,
                product_name=product_name,
                preference_names=preference_names,
            )

        return tuple(
            preference_class.model_validate(payload)
            if (payload := payloads.get(preference_class.get_preference_name()))
            else preference_class()
            for preference_class in preference_classes
        )
