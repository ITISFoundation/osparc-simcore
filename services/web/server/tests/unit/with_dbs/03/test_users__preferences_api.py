# pylint: disable=inconsistent-return-statements
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=too-many-return-statements

from collections.abc import AsyncIterator
from typing import Any

import aiopg.sa
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from common_library.pydantic_fields_extension import get_type
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
from simcore_service_webserver.users._preferences_api import (
    _get_frontend_user_preferences,
    get_frontend_user_preferences_aggregation,
    set_frontend_user_preference,
)
from simcore_service_webserver.users._preferences_models import (
    ALL_FRONTEND_PREFERENCES,
    BillingCenterUsageColumnOrderFrontendUserPreference,
)


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    # disables GC
    return app_environment | setenvs_from_dict(
        monkeypatch, {"WEBSERVER_GARBAGE_COLLECTOR": "null"}
    )


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
    return (
        model_field.default_factory()
        if model_field.default_factory
        else model_field.default
    )


def _get_non_default_value(
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
        if value_type == int:
            return 0
        if value_type == str:
            return ""

    pytest.fail(
        f"case type={type(value)}, {value=} {value_type=} not implemented. Please add it."
    )


async def test__get_frontend_user_preferences_list_defaults(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    drop_all_preferences: None,
):
    # get preferences which were not saved, return default values
    found_preferences = await _get_frontend_user_preferences(
        app, user_id=user_id, product_name=product_name
    )
    assert len(found_preferences) == len(ALL_FRONTEND_PREFERENCES)

    # check all preferences contain the default value
    for preference in found_preferences:
        assert preference.value == _get_default_field_value(preference.__class__)


@pytest.fixture
async def enable_all_frontend_preferences(
    aiopg_engine: aiopg.sa.engine.Engine, product_name: ProductName
) -> None:
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            groups_extra_properties.update()
            .where(groups_extra_properties.c.product_name == product_name)
            .values(enable_telemetry=True)
        )


async def test_get_frontend_user_preferences_aggregation(
    app: web.Application,
    enable_all_frontend_preferences: None,
    user_id: UserID,
    product_name: ProductName,
    drop_all_preferences: None,
):
    # checks that values get properly converted
    frontend_user_preferences_aggregation = (
        await get_frontend_user_preferences_aggregation(
            app, user_id=user_id, product_name=product_name
        )
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
    found_preferences = await _get_frontend_user_preferences(
        app, user_id=user_id, product_name=product_name
    )
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
    found_preferences = await _get_frontend_user_preferences(
        app, user_id=user_id, product_name=product_name
    )
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

    found_preferences = await _get_frontend_user_preferences(
        app, user_id=user_id, product_name=product_name
    )
    assert len(found_preferences) == len(ALL_FRONTEND_PREFERENCES)
    for preference in found_preferences:
        assert preference.value == _get_default_field_value(preference.__class__)


def test_expected_fields_in_serialization():
    for preference_class in ALL_FRONTEND_PREFERENCES:
        assert set(preference_class().to_db().keys()) == {"value"}
