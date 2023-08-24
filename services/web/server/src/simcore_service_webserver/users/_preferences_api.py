from typing import Any, Final

from aiohttp import web
from models_library.user_preferences import BaseFrontendUserPreference
from models_library.users import UserID
from pydantic import NonNegativeInt, parse_obj_as
from servicelib.utils import logged_gather

from ._preferences_db import get_user_preference, set_user_preference
from ._preferences_models import ALL_FRONTEND_PREFERENCES

_MAX_PARALLEL_DB_QUERIES: Final[NonNegativeInt] = 2


async def get_frontend_user_preferences(
    app: web.Application,
    *,
    user_id: UserID,
) -> list[BaseFrontendUserPreference]:
    saved_user_preferences: list[
        BaseFrontendUserPreference | None
    ] = await logged_gather(
        *(
            get_user_preference(app, user_id=user_id, preference_class=preference_class)
            for preference_class in ALL_FRONTEND_PREFERENCES
        ),
        max_concurrency=_MAX_PARALLEL_DB_QUERIES,
    )

    return [
        preference_class() if result is None else result
        for (result, preference_class) in zip(
            saved_user_preferences, ALL_FRONTEND_PREFERENCES, strict=True
        )
    ]


async def set_frontend_user_preference(
    app: web.Application, *, user_id: UserID, preference_name: str, value: Any
) -> None:
    preference_class = BaseFrontendUserPreference.get_preference_class_from_name(
        preference_name
    )

    await set_user_preference(
        app,
        user_id=user_id,
        preference=parse_obj_as(preference_class, {"value": value}),
    )
