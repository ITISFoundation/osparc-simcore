# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from unittest import mock

from fastapi import FastAPI
from pytest_simcore.helpers.postgres_users import (
    insert_and_get_user_and_secrets_lifespan,
)
from simcore_service_resource_usage_tracker.services.modules.db import users_db

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_get_user_language_returns_persisted_value(
    mocked_redis_server: None,
    mocked_setup_rabbitmq: mock.Mock,
    initialized_app: FastAPI,
):
    engine = initialized_app.state.engine

    async with insert_and_get_user_and_secrets_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
        engine, language="es_ES"
    ) as user:
        language = await users_db.get_user_language(engine, user_id=user["id"])
        assert language == "es_ES"


async def test_get_user_language_returns_none_when_not_set(
    mocked_redis_server: None,
    mocked_setup_rabbitmq: mock.Mock,
    initialized_app: FastAPI,
):
    engine = initialized_app.state.engine

    async with insert_and_get_user_and_secrets_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
        engine
    ) as user:
        language = await users_db.get_user_language(engine, user_id=user["id"])
        assert language is None


async def test_get_user_language_returns_none_for_unknown_user(
    mocked_redis_server: None,
    mocked_setup_rabbitmq: mock.Mock,
    initialized_app: FastAPI,
):
    engine = initialized_app.state.engine

    language = await users_db.get_user_language(engine, user_id=999_999_999)
    assert language is None
