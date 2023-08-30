from typing import Any, Final, cast

from aiohttp import web
from models_library.api_schemas_webserver.users_preferences import (
    FrontendUserPreference,
    FrontendUserPreferencesGet,
)
from models_library.products import ProductName
from models_library.user_preferences import (
    AnyBaseUserPreference,
    BaseFrontendUserPreference,
    PreferenceIdentifier,
    PreferenceName,
)
from models_library.users import UserID
from pydantic import NonNegativeInt, parse_obj_as
from servicelib.utils import logged_gather

from ._preferences_db import get_user_preference, set_user_preference
from ._preferences_models import (
    ALL_FRONTEND_PREFERENCES,
    get_preference_identifier_to_preference_name_map,
)

_MAX_PARALLEL_DB_QUERIES: Final[NonNegativeInt] = 2


class FrontendUserPreferenceIsNotDefinedError(Exception):
    def __init__(self, frontend_preference_name: str):
        super().__init__(f"Provided {frontend_preference_name=} not found")
        self.frontend_preference_name = frontend_preference_name


async def _get_frontend_user_preferences_list(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
) -> list[BaseFrontendUserPreference]:
    saved_user_preferences: list[
        BaseFrontendUserPreference | None
    ] = await logged_gather(
        *(
            get_user_preference(
                app,
                user_id=user_id,
                product_name=product_name,
                preference_class=preference_class,
            )
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


async def get_frontend_user_preferences(
    app: web.Application, *, user_id: UserID, product_name: ProductName
) -> FrontendUserPreferencesGet:
    return {
        p.preference_identifier: FrontendUserPreference.parse_obj(
            {"value": p.value, "default_value": p.get_default_value()}
        )
        for p in await _get_frontend_user_preferences_list(app, user_id, product_name)
    }


async def set_frontend_user_preference(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    frontend_preference_identifier: PreferenceIdentifier,
    value: Any,
) -> None:
    try:
        preference_name: PreferenceName = (
            get_preference_identifier_to_preference_name_map()[
                frontend_preference_identifier
            ]
        )
    except KeyError as e:
        raise FrontendUserPreferenceIsNotDefinedError(
            frontend_preference_identifier
        ) from e

    preference_class = cast(
        type[AnyBaseUserPreference],
        BaseFrontendUserPreference.get_preference_class_from_name(preference_name),
    )

    await set_user_preference(
        app,
        user_id=user_id,
        preference=parse_obj_as(preference_class, {"value": value}),
        product_name=product_name,
    )
