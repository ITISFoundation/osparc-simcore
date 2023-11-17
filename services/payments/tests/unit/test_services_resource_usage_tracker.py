# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from datetime import datetime, timezone

import pytest
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from respx import MockRouter
from simcore_service_payments.core.application import create_app
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.services.resource_usage_tracker import (
    ResourceUsageTrackerApi,
    setup_resource_usage_tracker,
)


async def test_setup_rut_api(app_environment: EnvVarsDict):
    new_app = FastAPI()
    new_app.state.settings = ApplicationSettings.create_from_envs()
    with pytest.raises(AttributeError):
        ResourceUsageTrackerApi.get_from_app_state(new_app)

    setup_resource_usage_tracker(new_app)
    rut_api = ResourceUsageTrackerApi.get_from_app_state(new_app)

    assert rut_api is not None
    assert rut_api.client

    async with LifespanManager(
        new_app,
        startup_timeout=None,  # for debugging
        shutdown_timeout=10,
    ):
        # start event called
        assert not rut_api.client.is_closed

    # shutdown event
    assert rut_api.client.is_closed


@pytest.fixture
def app(
    app_environment: EnvVarsDict,
    with_disabled_rabbitmq_and_rpc: None,
    with_disabled_postgres: None,
):
    # NOTE: overrides services/payments/tests/unit/conftest.py:app fixture
    return create_app()


async def test_add_credits_to_wallet(
    app: FastAPI, faker: Faker, mock_resoruce_usage_tracker_service_api: MockRouter
):
    # test
    rut_api = ResourceUsageTrackerApi.get_from_app_state(app)

    assert (
        await rut_api.create_credit_transaction(
            product_name=faker.word(),
            wallet_id=faker.pyint(),
            wallet_name=faker.word(),
            user_id=faker.pyint(),
            user_email=faker.email(),
            osparc_credits=100,
            payment_transaction_id=faker.pyint(),
            created_at=datetime.now(tz=timezone.utc),
        )
        > 0
    )
