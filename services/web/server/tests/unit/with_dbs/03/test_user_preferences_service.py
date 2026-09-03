# pylint: disable=inconsistent-return-statements
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=too-many-return-statements

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Final, Literal, get_args, get_origin

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from common_library.pydantic_fields_extension import get_type
from faker import Faker
from models_library.api_schemas_webserver.users_preferences import Preference
from models_library.products import ProductName
from models_library.user_preferences import FrontendUserPreference
from models_library.users import UserID
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_login import NewUser
from simcore_postgres_database.models.groups_extra_properties import (
    groups_extra_properties,
)
from simcore_postgres_database.models.users import UserStatus
from simcore_service_webserver.user_preferences._models import (
    ALL_FRONTEND_PREFERENCES,
    BillingCenterUsageColumnOrderFrontendUserPreference,
    UserInactivityThresholdFrontendUserPreference,
)
from simcore_service_webserver.user_preferences._service import (
    _get_frontend_user_preferences,
    get_frontend_user_preference,
    get_frontend_user_preferences_aggregation,
    set_frontend_user_preference,
)
from simcore_service_webserver.user_preferences.errors import (
    FrontendUserPreferenceValueIsInvalidError,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    # disables GC
    return app_environment | setenvs_from_dict(monkeypatch, {"WEBSERVER_GARBAGE_COLLECTOR": "null"})


@pytest.fixture
def app(client: TestClient) -> web.Application:
    assert client.app
    return client.app


@pytest.fixture
async def user_id(client: TestClient, faker: Faker) -> AsyncIterator[UserID]:
    async with NewUser(
        {"email": faker.email(), "status": UserStatus.ACTIVE.name},
        client.app,
    ) as user:
        yield user["id"]


@pytest.fixture
def product_name() -> ProductName:
    return "osparc"


def _get_model_field(model_class: type[BaseModel], field_name: str) -> FieldInfo:
    return model_class.model_fields[field_name]


def _get_default_field_value(model_class: type[BaseModel]) -> Any:
    model_field = _get_model_field(model_class, "value")
    return model_field.default_factory() if model_field.default_factory else model_field.default


def _get_non_default_value(  # noqa: PLR0911
    model_class: type[FrontendUserPreference],
) -> Any:
    """given a default value transforms into something that is different"""

    model_field = _get_model_field(model_class, "value")
    value_type = get_type(model_field)
    value = _get_default_field_value(model_class)

    if isinstance(value, bool):
        return not value
    if isinstance(value, dict):
        return {**value, "non_default_key": "non_default_value"}
    if isinstance(value, list):
        return [*value, "non_default_value"]
    if isinstance(value, int | str):
        return value

    if value is None:
        if (
            model_class.get_preference_name()
            == BillingCenterUsageColumnOrderFrontendUserPreference.get_preference_name()
        ):
            return None
        if value_type is int:
            return 0
        if value_type is str:
            return ""
        # Handle TypeAliasType (e.g. `type SupportedLocale = Literal[...]`)
        resolved_type = getattr(value_type, "__value__", value_type)
        if get_origin(resolved_type) is Literal:
            return get_args(resolved_type)[0]

    pytest.fail(f"case type={type(value)}, {value=} {value_type=} not implemented. Please add it.")


async def test__get_frontend_user_preferences_list_defaults(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    drop_all_preferences: None,
):
    # get preferences which were not saved, return default values
    found_preferences = await _get_frontend_user_preferences(app, user_id=user_id, product_name=product_name)
    assert len(found_preferences) == len(ALL_FRONTEND_PREFERENCES)

    # check all preferences contain the default value
    for preference in found_preferences:
        assert preference.value == _get_default_field_value(preference.__class__)


@pytest.fixture
async def enable_all_frontend_preferences(asyncpg_engine: AsyncEngine, product_name: ProductName) -> None:
    # NOTE: upserts the EVERYONE group (gid=1) row instead of relying on one being pre-seeded
    async with asyncpg_engine.begin() as conn:
        await conn.execute(
            pg_insert(groups_extra_properties)
            .values(group_id=1, product_name=product_name, enable_telemetry=True)
            .on_conflict_do_update(
                index_elements=["group_id", "product_name"],
                set_={"enable_telemetry": True},
            )
        )


async def test_get_frontend_user_preferences_aggregation(
    app: web.Application,
    enable_all_frontend_preferences: None,
    user_id: UserID,
    product_name: ProductName,
    drop_all_preferences: None,
):
    # checks that values get properly converted
    frontend_user_preferences_aggregation = await get_frontend_user_preferences_aggregation(
        app, user_id=user_id, product_name=product_name
    )
    assert len(frontend_user_preferences_aggregation) == len(ALL_FRONTEND_PREFERENCES)
    for value in frontend_user_preferences_aggregation.values():
        assert isinstance(value, Preference)


async def test_set_frontend_user_preference(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    drop_all_preferences: None,
):
    # check all preferences contain the default value (since non was saved before)
    found_preferences = await _get_frontend_user_preferences(app, user_id=user_id, product_name=product_name)
    for preference in found_preferences:
        assert preference.value == _get_default_field_value(preference.__class__)

    for preference_class in ALL_FRONTEND_PREFERENCES:
        instance = preference_class()
        await set_frontend_user_preference(
            app,
            user_id=user_id,
            product_name=product_name,
            frontend_preference_identifier=instance.preference_identifier,
            value=_get_non_default_value(preference_class),
        )

    # after a query all preferences should contain a non default value
    found_preferences = await _get_frontend_user_preferences(app, user_id=user_id, product_name=product_name)
    assert len(found_preferences) == len(ALL_FRONTEND_PREFERENCES)
    for preference in found_preferences:
        assert preference.value == _get_non_default_value(preference.__class__)

    # set the original values back again and check
    for preference_class in ALL_FRONTEND_PREFERENCES:
        instance = preference_class()
        await set_frontend_user_preference(
            app,
            user_id=user_id,
            frontend_preference_identifier=instance.preference_identifier,
            product_name=product_name,
            value=_get_default_field_value(preference_class),
        )

    found_preferences = await _get_frontend_user_preferences(app, user_id=user_id, product_name=product_name)
    assert len(found_preferences) == len(ALL_FRONTEND_PREFERENCES)
    for preference in found_preferences:
        assert preference.value == _get_default_field_value(preference.__class__)


def test_expected_fields_in_serialization():
    for preference_class in ALL_FRONTEND_PREFERENCES:
        assert set(preference_class().to_db().keys()) == {"value"}


_INACTIVITY_IDENTIFIER: Final[str] = UserInactivityThresholdFrontendUserPreference.model_fields[
    "preference_identifier"
].default
_MINUTE: Final[int] = 60
_HOUR: Final[int] = 60 * _MINUTE


@pytest.fixture
async def set_inactivity_constraints(
    asyncpg_engine: AsyncEngine, product_name: ProductName
) -> Callable[[Any], Awaitable[None]]:
    # NOTE: upserts the EVERYONE group (gid=1) row instead of relying on one being pre-seeded,
    # so this fixture is unaffected by other tests deleting group extra properties beforehand
    async def _(constraints: Any) -> None:
        frontend_preferences_constraints = {_INACTIVITY_IDENTIFIER: constraints} if constraints else {}
        async with asyncpg_engine.begin() as conn:
            await conn.execute(
                pg_insert(groups_extra_properties)
                .values(
                    group_id=1,
                    product_name=product_name,
                    frontend_preferences_constraints=frontend_preferences_constraints,
                )
                .on_conflict_do_update(
                    index_elements=["group_id", "product_name"],
                    set_={"frontend_preferences_constraints": frontend_preferences_constraints},
                )
            )

    return _


@pytest.fixture
async def drop_all_group_extra_properties(asyncpg_engine: AsyncEngine, product_name: ProductName) -> None:
    async with asyncpg_engine.begin() as conn:
        await conn.execute(
            groups_extra_properties.delete().where(groups_extra_properties.c.product_name == product_name)
        )


async def test_set_frontend_user_preference_without_group_extra_properties(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    drop_all_preferences: None,
    drop_all_group_extra_properties: None,
):
    # NOTE: products do not provision `groups_extra_properties`, writing a preference must not depend on it
    await set_frontend_user_preference(
        app,
        user_id=user_id,
        product_name=product_name,
        frontend_preference_identifier=_INACTIVITY_IDENTIFIER,
        value=2 * _HOUR,
    )

    preference = await get_frontend_user_preference(
        app,
        user_id=user_id,
        product_name=product_name,
        preference_class=UserInactivityThresholdFrontendUserPreference,
    )
    assert preference is not None
    assert preference.value == 2 * _HOUR

    # the class constraints still apply
    with pytest.raises(FrontendUserPreferenceValueIsInvalidError):
        await set_frontend_user_preference(
            app,
            user_id=user_id,
            product_name=product_name,
            frontend_preference_identifier=_INACTIVITY_IDENTIFIER,
            value=4 * _HOUR,
        )


@pytest.mark.parametrize(
    "constraints, value, is_allowed",
    [
        pytest.param(None, 1 * _MINUTE, True, id="at_class_minimum"),
        pytest.param(None, 1 * _MINUTE - 1, False, id="below_class_minimum"),
        pytest.param(None, 3 * _HOUR, True, id="at_class_cap"),
        pytest.param(None, 4 * _HOUR, False, id="above_class_cap"),
        # NOTE: overrides are merged per key, they must use the same key as the class to replace it
        pytest.param({"le": 6 * _HOUR}, 6 * _HOUR, True, id="group_relaxes_class_cap"),
        pytest.param({"le": 6 * _HOUR}, 7 * _HOUR, False, id="above_relaxed_group_cap"),
        pytest.param({"le": 2 * _HOUR}, 3 * _HOUR, False, id="group_tightens_class_cap"),
    ],
)
async def test_set_frontend_user_preference_honours_group_constraints(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    drop_all_preferences: None,
    set_inactivity_constraints: Callable[[dict[str, Any] | None], Awaitable[None]],
    constraints: dict[str, Any] | None,
    value: int,
    is_allowed: bool,
):
    await set_inactivity_constraints(constraints)

    async def _set() -> None:
        await set_frontend_user_preference(
            app,
            user_id=user_id,
            product_name=product_name,
            frontend_preference_identifier=_INACTIVITY_IDENTIFIER,
            value=value,
        )

    if is_allowed:
        await _set()
    else:
        with pytest.raises(FrontendUserPreferenceValueIsInvalidError):
            await _set()


async def test_value_allowed_by_group_stays_readable_after_constraint_removal(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    drop_all_preferences: None,
    set_inactivity_constraints: Callable[[dict[str, Any] | None], Awaitable[None]],
):
    await set_inactivity_constraints({"le": 6 * _HOUR})
    await set_frontend_user_preference(
        app,
        user_id=user_id,
        product_name=product_name,
        frontend_preference_identifier=_INACTIVITY_IDENTIFIER,
        value=6 * _HOUR,
    )

    await set_inactivity_constraints(None)

    preference = await get_frontend_user_preference(
        app,
        user_id=user_id,
        product_name=product_name,
        preference_class=UserInactivityThresholdFrontendUserPreference,
    )
    assert preference is not None
    assert preference.value == 6 * _HOUR


async def test_aggregation_exposes_effective_constraints(
    app: web.Application,
    enable_all_frontend_preferences: None,
    user_id: UserID,
    product_name: ProductName,
    drop_all_preferences: None,
    set_inactivity_constraints: Callable[[dict[str, Any] | None], Awaitable[None]],
):
    await set_inactivity_constraints(None)
    aggregation = await get_frontend_user_preferences_aggregation(app, user_id=user_id, product_name=product_name)
    constraints = aggregation[_INACTIVITY_IDENTIFIER].constraints
    assert constraints is not None
    assert constraints.le == 3 * _HOUR
    # preferences without constraints must not carry an empty object
    assert aggregation["themeName"].constraints is None

    await set_inactivity_constraints({"le": 6 * _HOUR, "ge": 60})
    aggregation = await get_frontend_user_preferences_aggregation(app, user_id=user_id, product_name=product_name)
    constraints = aggregation[_INACTIVITY_IDENTIFIER].constraints
    assert constraints is not None
    assert constraints.le == 6 * _HOUR
    assert constraints.ge == 60


@pytest.mark.parametrize(
    "malformed_constraints",
    [
        pytest.param({"lte": 6 * _HOUR}, id="misspelled_constraint"),
        pytest.param({"le": "not-a-number"}, id="constraint_value_of_wrong_type"),
        pytest.param({"pattern": "["}, id="invalid_regular_expression"),
        pytest.param("not-a-mapping", id="overrides_not_a_mapping"),
        pytest.param(["le", 1], id="overrides_is_a_sequence"),
    ],
)
async def test_misconfigured_constraints_fall_back_to_code_defaults(
    app: web.Application,
    enable_all_frontend_preferences: None,
    user_id: UserID,
    product_name: ProductName,
    drop_all_preferences: None,
    set_inactivity_constraints: Callable[[Any], Awaitable[None]],
    malformed_constraints: Any,
):
    # NOTE: a single bad row must not take down profile loading for everyone in the group
    await set_inactivity_constraints(malformed_constraints)

    aggregation = await get_frontend_user_preferences_aggregation(app, user_id=user_id, product_name=product_name)
    constraints = aggregation[_INACTIVITY_IDENTIFIER].constraints
    assert constraints is not None
    assert constraints.le == 3 * _HOUR

    # the code defaults still apply on the write path
    await set_frontend_user_preference(
        app,
        user_id=user_id,
        product_name=product_name,
        frontend_preference_identifier=_INACTIVITY_IDENTIFIER,
        value=2 * _HOUR,
    )
    with pytest.raises(FrontendUserPreferenceValueIsInvalidError):
        await set_frontend_user_preference(
            app,
            user_id=user_id,
            product_name=product_name,
            frontend_preference_identifier=_INACTIVITY_IDENTIFIER,
            value=4 * _HOUR,
        )
