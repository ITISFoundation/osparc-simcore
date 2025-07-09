from models_library.products import ProductName
from models_library.user_preferences import FrontendUserPreference, PreferenceName
from models_library.users import UserID
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from simcore_postgres_database.utils_user_preferences import FrontendUserPreferencesRepo
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.base_repository import BaseRepository


class UserPreferencesRepository(BaseRepository):
    @staticmethod
    def _get_user_preference_name(
        user_id: UserID, preference_name: PreferenceName
    ) -> str:
        return f"{user_id}/{preference_name}"

    async def get_user_preference(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
        product_name: ProductName,
        preference_class: type[FrontendUserPreference],
    ) -> FrontendUserPreference | None:
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            preference_payload: dict | None = await FrontendUserPreferencesRepo.load(
                conn,
                user_id=user_id,
                preference_name=self._get_user_preference_name(
                    user_id, preference_class.get_preference_name()
                ),
                product_name=product_name,
            )

        return (
            None
            if preference_payload is None
            else preference_class.model_validate(preference_payload)
        )

    async def set_user_preference(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
        product_name: ProductName,
        preference: FrontendUserPreference,
    ) -> None:
        async with transaction_context(self.engine, connection) as conn:
            await FrontendUserPreferencesRepo.save(
                conn,
                user_id=user_id,
                preference_name=self._get_user_preference_name(
                    user_id, preference.get_preference_name()
                ),
                product_name=product_name,
                payload=preference.to_db(),
            )
