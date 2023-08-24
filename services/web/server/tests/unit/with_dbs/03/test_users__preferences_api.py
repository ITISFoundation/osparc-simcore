# pylint: disable=inconsistent-return-statements
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import AsyncIterator
from typing import Any

import aiopg.sa
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.users import UserID
from pydantic import BaseModel
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_login import NewUser
from simcore_postgres_database.models.user_preferences import user_preferences
from simcore_postgres_database.models.users import UserStatus
from simcore_service_webserver.users._preferences_api import (
    ALL_FRONTEND_PREFERENCES,
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


@pytest.fixture
async def drop_all_preferences(
    aiopg_engine: aiopg.sa.engine.Engine,
) -> AsyncIterator[None]:
    yield
    async with aiopg_engine.acquire() as conn:
        await conn.execute(user_preferences.delete())


def _get_default_field_value(model_class: type[BaseModel]) -> Any:
    return model_class.__dict__["__fields__"]["value"].default


def _get_non_default_value(obj: Any) -> Any:
    """given a default value transforms into something that is different"""
    if isinstance(obj, bool):
        return not obj

    pytest.fail(f"case type={type(obj)}, {obj=} not implemented. Please add it.")


async def test_get_frontend_user_preferences_defaults(
    app: web.Application, user_id: UserID, drop_all_preferences: None
):
    # get preferences which were not saved, return default values
    found_preferences = await get_frontend_user_preferences(app, user_id=user_id)
    assert len(found_preferences) == len(ALL_FRONTEND_PREFERENCES)

    # check all preferences contain the default value
    for preference in found_preferences:
        assert preference.value == _get_default_field_value(preference.__class__)


async def test_set_frontend_user_preference(
    app: web.Application, user_id: UserID, drop_all_preferences: None
):
    # check all preferences contain the default value (since non was saved before)
    found_preferences = await get_frontend_user_preferences(app, user_id=user_id)
    for preference in found_preferences:
        assert preference.value == _get_default_field_value(preference.__class__)

    for preference_class in ALL_FRONTEND_PREFERENCES:
        await set_frontend_user_preference(
            app,
            user_id=user_id,
            preference_name=preference_class.get_preference_name(),
            value=_get_non_default_value(_get_default_field_value(preference_class)),
        )

    # after a query all preferences should contain a non default value
    found_preferences = await get_frontend_user_preferences(app, user_id=user_id)
    assert len(found_preferences) == len(ALL_FRONTEND_PREFERENCES)
    for preference in found_preferences:
        assert preference.value == _get_non_default_value(
            _get_default_field_value(preference.__class__)
        )

    # set the original values back again and check
    for preference_class in ALL_FRONTEND_PREFERENCES:
        await set_frontend_user_preference(
            app,
            user_id=user_id,
            preference_name=preference_class.get_preference_name(),
            value=_get_default_field_value(preference_class),
        )

    found_preferences = await get_frontend_user_preferences(app, user_id=user_id)
    assert len(found_preferences) == len(ALL_FRONTEND_PREFERENCES)
    for preference in found_preferences:
        assert preference.value == _get_default_field_value(preference.__class__)
