# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonref
import pytest
import respx
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI, status
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from respx import MockRouter
from simcore_service_payments.core.application import create_app
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.services.resource_usage_tracker import (
    ResourceUsageTrackerApi,
    setup_resource_usage_tracker,
)
from toolz.dicttoolz import get_in


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
    disable_rabbitmq_and_rpc_setup: Callable,
    app_environment: EnvVarsDict,
):
    disable_rabbitmq_and_rpc_setup()
    return create_app()


@pytest.fixture
def rut_service_openapi_specs(
    osparc_simcore_services_dir: Path,
) -> dict[str, Any]:
    openapi_path = (
        osparc_simcore_services_dir / "resource-usage-tracker" / "openapi.json"
    )
    return jsonref.loads(openapi_path.read_text())


@pytest.fixture
def mock_resource_usage_tracker_service_api_base(
    app: FastAPI, rut_service_openapi_specs: dict[str, Any]
) -> Iterator[MockRouter]:
    settings: ApplicationSettings = app.state.settings
    with respx.mock(
        base_url=settings.PAYMENTS_RESOURCE_USAGE_TRACKER.base_url,
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as respx_mock:
        #
        # /
        #
        assert "healthcheck" in get_in(
            ["paths", "/", "get", "operationId"],
            rut_service_openapi_specs,
            no_default=True,
        )  # type: ignore
        respx_mock.get(
            path="/",
            name="healthcheck",
        ).respond(status.HTTP_200_OK)

        yield respx_mock


@pytest.fixture
def mock_rut_service_api(
    faker: Faker,
    mock_resource_usage_tracker_service_api_base: MockRouter,
    rut_service_openapi_specs: dict[str, Any],
):
    # check it exists
    get_in(
        ["paths", "/v1/credit-transactions", "post", "operationId"],
        rut_service_openapi_specs,
        no_default=True,
    )

    # fake successful response
    mock_resource_usage_tracker_service_api_base.post(
        "/v1/credit-transactions"
    ).respond(json={"credit_transaction_id": faker.pyint()})

    return mock_resource_usage_tracker_service_api_base


async def test_add_credits_to_wallet(
    app: FastAPI, faker: Faker, mock_rut_service_api: MockRouter
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
