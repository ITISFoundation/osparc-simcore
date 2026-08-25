import logging
from typing import Any, Final

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
from pydantic import NonNegativeInt, ValidationError
from servicelib.utils import logged_gather
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraProperties,
    GroupExtraPropertiesNotFoundError,
    GroupExtraPropertiesRepo,
)
from simcore_postgres_database.utils_repos import pass_or_acquire_connection

from ..db.plugin import get_asyncpg_engine
from ._models import (
    ALL_FRONTEND_PREFERENCES,
    TelemetryLowDiskSpaceWarningThresholdFrontendUserPreference,
    get_preference_identifier,
    get_preference_name,
)
from ._repository import UserPreferencesRepository
from .errors import (
    FrontendUserPreferenceIsNotDefinedError,
    FrontendUserPreferenceValueIsInvalidError,
)

_MAX_PARALLEL_DB_QUERIES: Final[NonNegativeInt] = 2

_logger = logging.getLogger(__name__)


async def _get_frontend_user_preferences(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
) -> list[FrontendUserPreference]:
    repo = UserPreferencesRepository.create_from_app(app)

    saved_user_preferences: list[FrontendUserPreference | None] = await logged_gather(
        *(
            repo.get_user_preference(
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
        for (result, preference_class) in zip(saved_user_preferences, ALL_FRONTEND_PREFERENCES, strict=True)
    ]


async def get_frontend_user_preference(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    preference_class: type[FrontendUserPreference],
) -> AnyUserPreference | None:
    repo = UserPreferencesRepository.create_from_app(app)
    return await repo.get_user_preference(
        user_id=user_id,
        product_name=product_name,
        preference_class=preference_class,
    )


async def _get_group_extra_properties(
    app: web.Application, *, user_id: UserID, product_name: ProductName
) -> GroupExtraProperties:
    async with pass_or_acquire_connection(get_asyncpg_engine(app)) as conn:
        return await GroupExtraPropertiesRepo.get_aggregated_properties_for_user(
            conn, user_id=user_id, product_name=product_name
        )


async def get_frontend_user_preferences_aggregation(
    app: web.Application, *, user_id: UserID, product_name: ProductName
) -> AggregatedPreferences:
    group_extra_properties = await _get_group_extra_properties(app, user_id=user_id, product_name=product_name)

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

    def to_preference(preference: FrontendUserPreference) -> Preference:
        constraints = preference.get_value_constraints(
            group_extra_properties.frontend_preferences_constraints.get(preference.preference_identifier)
        )
        return Preference.model_validate(
            {
                "value": preference.value,
                "default_value": preference.get_default_value(),
                "constraints": constraints or None,
            }
        )

    aggregated_preferences: AggregatedPreferences = {
        p.preference_identifier: to_preference(p)
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
        preference_name: PreferenceName = get_preference_name(frontend_preference_identifier)
    except KeyError as e:
        raise FrontendUserPreferenceIsNotDefinedError(
            frontend_preference_identifier=frontend_preference_identifier
        ) from e

    preference_class = FrontendUserPreference.get_preference_class_from_name(preference_name)

    try:
        group_extra_properties = await _get_group_extra_properties(app, user_id=user_id, product_name=product_name)
        constraints_overrides = group_extra_properties.frontend_preferences_constraints.get(
            frontend_preference_identifier
        )
    except GroupExtraPropertiesNotFoundError:
        constraints_overrides = None

    try:
        preference_class.validate_value(value, constraints_overrides)
        preference = preference_class.model_validate({"value": value})
    except ValidationError as e:
        raise FrontendUserPreferenceValueIsInvalidError(
            frontend_preference_identifier=frontend_preference_identifier, value=value
        ) from e

    repo = UserPreferencesRepository.create_from_app(app)
    await repo.set_user_preference(
        user_id=user_id,
        product_name=product_name,
        preference=preference,
    )
