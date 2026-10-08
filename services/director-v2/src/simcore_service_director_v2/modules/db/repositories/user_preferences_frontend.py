from models_library.products import ProductName
from models_library.user_preferences import FrontendUserPreference, PreferenceName
from models_library.users import UserID
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from simcore_postgres_database.utils_user_preferences import FrontendUserPreferencesRepo
from sqlalchemy.ext.asyncio import AsyncConnection

from ._base import BaseRepository


def _get_user_preference_name(user_id: UserID, preference_name: PreferenceName) -> str:
    return f"{user_id}/{preference_name}"


class UserPreferencesFrontendRepository(BaseRepository):
    async def get_user_preference(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        preference_class: type[FrontendUserPreference],
        connection: AsyncConnection | None = None,
    ) -> FrontendUserPreference | None:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            preference_payload: dict | None = await FrontendUserPreferencesRepo.load(
                conn,
                user_id=user_id,
                preference_name=_get_user_preference_name(user_id, preference_class.get_preference_name()),
                product_name=product_name,
            )

        return None if preference_payload is None else preference_class.model_validate(preference_payload)
