# pylint: disable=inconsistent-return-statements
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import AsyncIterator
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.users_preferences import UserPreference
from models_library.user_preferences import ValueType
from models_library.users import UserID
from pydantic import BaseModel
from pydantic.fields import ModelField
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_login import NewUser
from simcore_postgres_database.models.users import UserStatus
from simcore_service_webserver.users._preferences_api import (
    ALL_FRONTEND_PREFERENCES,
    _get_frontend_user_preferences_list,
    get_frontend_user_preferences,
    set_frontend_user_preference,
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


def _get_model_field(model_class: type[BaseModel], field_name: str) -> ModelField:
    return model_class.__dict__["__fields__"][field_name]


def _get_default_field_value(model_class: type[BaseModel]) -> Any:
    model_field = _get_model_field(model_class, "value")
    return (
        model_field.default_factory()
        if model_field.default_factory
        else model_field.default
    )


def _get_non_default_value(value: Any, value_type: ValueType) -> Any:
    """given a default value transforms into something that is different"""
    if isinstance(value, bool):
        return not value
    if isinstance(value, dict):
        return {**value, "non_default_key": "non_default_value"}
    if value is None and value_type == ValueType.STR:
        return ""

    pytest.fail(
        f"case type={type(value)}, {value=} {value_type=} not implemented. Please add it."
    )


async def test__get_frontend_user_preferences_list_defaults(
    app: web.Application, user_id: UserID, drop_all_preferences: None
):
    # get preferences which were not saved, return default values
    found_preferences = await _get_frontend_user_preferences_list(app, user_id=user_id)
    assert len(found_preferences) == len(ALL_FRONTEND_PREFERENCES)

    # check all preferences contain the default value
    for preference in found_preferences:
        assert preference.value == _get_default_field_value(preference.__class__)


async def test_get_frontend_user_preferences(
    app: web.Application, user_id: UserID, drop_all_preferences: None
):
    # checks that values get properly converted
    frontend_user_preferences = await get_frontend_user_preferences(
        app, user_id=user_id
    )
    assert len(frontend_user_preferences) == len(ALL_FRONTEND_PREFERENCES)
    for value in frontend_user_preferences.values():
        assert isinstance(value, UserPreference)


async def test_set_frontend_user_preference(
    app: web.Application, user_id: UserID, drop_all_preferences: None
):
    # check all preferences contain the default value (since non was saved before)
    found_preferences = await _get_frontend_user_preferences_list(app, user_id=user_id)
    for preference in found_preferences:
        assert preference.value == _get_default_field_value(preference.__class__)

    for preference_class in ALL_FRONTEND_PREFERENCES:
        await set_frontend_user_preference(
            app,
            user_id=user_id,
            frontend_preference_name=preference_class.get_preference_name(),
            value=_get_non_default_value(
                _get_default_field_value(preference_class),
                _get_model_field(preference_class, "value_type").default,
            ),
        )

    # after a query all preferences should contain a non default value
    found_preferences = await _get_frontend_user_preferences_list(app, user_id=user_id)
    assert len(found_preferences) == len(ALL_FRONTEND_PREFERENCES)
    for preference in found_preferences:
        assert preference.value == _get_non_default_value(
            _get_default_field_value(preference.__class__), preference.value_type
        )

    # set the original values back again and check
    for preference_class in ALL_FRONTEND_PREFERENCES:
        await set_frontend_user_preference(
            app,
            user_id=user_id,
            frontend_preference_name=preference_class.get_preference_name(),
            value=_get_default_field_value(preference_class),
        )

    found_preferences = await _get_frontend_user_preferences_list(app, user_id=user_id)
    assert len(found_preferences) == len(ALL_FRONTEND_PREFERENCES)
    for preference in found_preferences:
        assert preference.value == _get_default_field_value(preference.__class__)


def test_expected_fields_in_serialization():
    for preference_class in ALL_FRONTEND_PREFERENCES:
        assert set(preference_class().dict().keys()) == {"value"}
