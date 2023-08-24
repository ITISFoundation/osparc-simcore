from aiohttp import web
from models_library.user_preferences import AnyBaseUserPreference, PreferenceName
from models_library.users import UserID
from simcore_postgres_database.utils_user_preferences import UserPreferencesRepo

from ..db.plugin import get_database_engine


def _get_user_preference_name(user_id: UserID, preference_name: PreferenceName) -> str:
    return f"{user_id}/{preference_name}"


async def get_user_preference(
    app: web.Application,
    *,
    user_id: UserID,
    preference_class: type[AnyBaseUserPreference],
) -> AnyBaseUserPreference | None:
    async with get_database_engine(app).acquire() as conn:
        preference_payload: bytes | None = (
            await UserPreferencesRepo().get_preference_payload(
                conn,
                user_id=user_id,
                preference_name=_get_user_preference_name(
                    user_id, preference_class.get_preference_name()
                ),
            )
        )

    return (
        None
        if preference_payload is None
        else preference_class.parse_raw(preference_payload)
    )


async def set_user_preference(
    app: web.Application,
    *,
    user_id: UserID,
    preference: AnyBaseUserPreference,
) -> None:
    async with get_database_engine(app).acquire() as conn:
        await UserPreferencesRepo().save_preference(
            conn,
            user_id=user_id,
            preference_name=_get_user_preference_name(
                user_id, preference.get_preference_name()
            ),
            payload=preference.json().encode(),
        )
