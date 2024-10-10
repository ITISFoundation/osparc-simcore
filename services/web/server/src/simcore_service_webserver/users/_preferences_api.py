from typing import Any, Final, cast

from aiohttp import web
from models_library.api_schemas_webserver.users_preferences import (
    AggregatedPreferences,
    Preference,
)
from models_library.products import ProductName
from models_library.user_preferences import (
    AnyUserPreference,
    FrontendUserPreference,
    PreferenceIdentifier,
    PreferenceName,
)
from models_library.users import UserID
from pydantic import NonNegativeInt, TypeAdapter
from servicelib.utils import logged_gather
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraPropertiesRepo,
)

from ..db.plugin import get_database_engine
from . import _preferences_db
from ._preferences_models import (
    ALL_FRONTEND_PREFERENCES,
    TelemetryLowDiskSpaceWarningThresholdFrontendUserPreference,
    get_preference_identifier,
    get_preference_name,
)
from .exceptions import FrontendUserPreferenceIsNotDefinedError

_MAX_PARALLEL_DB_QUERIES: Final[NonNegativeInt] = 2


async def _get_frontend_user_preferences(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
) -> list[FrontendUserPreference]:
    saved_user_preferences: list[FrontendUserPreference | None] = await logged_gather(
        *(
            _preferences_db.get_user_preference(
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


async def get_frontend_user_preference(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    preference_class: type[FrontendUserPreference],
) -> AnyUserPreference | None:
    return await _preferences_db.get_user_preference(
        app,
        user_id=user_id,
        product_name=product_name,
        preference_class=preference_class,
    )


async def get_frontend_user_preferences_aggregation(
    app: web.Application, *, user_id: UserID, product_name: ProductName
) -> AggregatedPreferences:
    async with get_database_engine(app).acquire() as conn:
        group_extra_properties = (
            await GroupExtraPropertiesRepo.get_aggregated_properties_for_user(
                conn, user_id=user_id, product_name=product_name
            )
        )

    is_telemetry_enabled: bool = group_extra_properties.enable_telemetry

    low_disk_warning_identifier = get_preference_identifier(
        TelemetryLowDiskSpaceWarningThresholdFrontendUserPreference.get_preference_name()
    )

    def include_preference(identifier: PreferenceIdentifier) -> bool:
        # NOTE: some preferences are included or excluded based on
        # the configuration specified in the backend
        if identifier == low_disk_warning_identifier:
            return is_telemetry_enabled
        return True

    aggregated_preferences: AggregatedPreferences = {
        p.preference_identifier: Preference.model_validate(
            {"value": p.value, "default_value": p.get_default_value()}
        )
        for p in await _get_frontend_user_preferences(app, user_id, product_name)
        if include_preference(p.preference_identifier)
    }
    return aggregated_preferences


async def set_frontend_user_preference(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    frontend_preference_identifier: PreferenceIdentifier,
    value: Any,
) -> None:
    try:
        preference_name: PreferenceName = get_preference_name(
            frontend_preference_identifier
        )
    except KeyError as e:
        raise FrontendUserPreferenceIsNotDefinedError(
            frontend_preference_identifier
        ) from e

    preference_class = cast(
        type[AnyUserPreference],
        FrontendUserPreference.get_preference_class_from_name(preference_name),
    )

    await _preferences_db.set_user_preference(
        app,
        user_id=user_id,
        preference=TypeAdapter(preference_class).validate_python({"value": value}),  # type: ignore[arg-type] # GitHK this is suspicious
        product_name=product_name,
    )
