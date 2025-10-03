# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import os

import pytest
from fastapi import FastAPI
from models_library.api_schemas_webserver.licensed_items_checkouts import (
    LicensedItemCheckoutRpcGet,
)
from pact.v3 import Verifier
from pytest_mock import MockerFixture
from simcore_service_api_server._meta import API_VERSION
from simcore_service_api_server.api.dependencies.resource_usage_tracker_rpc import (
    get_resource_usage_tracker_client,
)
from simcore_service_api_server.api.dependencies.webserver_rpc import (
    get_wb_api_rpc_client,
)
from simcore_service_api_server.services_rpc.resource_usage_tracker import (
    ResourceUsageTrackerClient,
)
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient

# Fake response based on values from 01_checkout_release.json
EXPECTED_CHECKOUT = LicensedItemCheckoutRpcGet.model_validate(
    {
        "key": "MODEL_IX_HEAD",
        "licensed_item_checkout_id": "25262183-392c-4268-9311-3c4256c46012",
        "licensed_item_id": "99580844-77fa-41bb-ad70-02dfaf1e3965",
        "num_of_seats": 1,
        "product_name": "s4l",
        "started_at": "2025-02-21T15:04:47.673828Z",
        "stopped_at": None,
        "user_id": 425,
        "version": "1.0.0",
        "wallet_id": 35,
    }
)
assert EXPECTED_CHECKOUT.stopped_at is None


EXPECTED_RELEASE = LicensedItemCheckoutRpcGet.model_validate(
    {
        "key": "MODEL_IX_HEAD",
        "licensed_item_checkout_id": "25262183-392c-4268-9311-3c4256c46012",
        "licensed_item_id": "99580844-77fa-41bb-ad70-02dfaf1e3965",
        "num_of_seats": 1,
        "product_name": "s4l",
        "started_at": "2025-02-21T15:04:47.673828Z",
        "stopped_at": "2025-02-21T15:04:47.901169Z",
        "user_id": 425,
        "version": "1.0.0",
        "wallet_id": 35,
    }
)
assert EXPECTED_RELEASE.stopped_at is not None


@pytest.fixture
async def mock_wb_api_server_rpc(app: FastAPI, mocker: MockerFixture) -> None:
    from servicelib.rabbitmq.rpc_interfaces.webserver.v1 import WebServerRpcClient

    app.dependency_overrides[get_wb_api_rpc_client] = lambda: WbApiRpcClient(
        _rpc_client=mocker.MagicMock(spec=WebServerRpcClient),
    )

    mocker.patch(
        "simcore_service_api_server.services_rpc.wb_api_server._checkout_licensed_item_for_wallet",
        return_value=EXPECTED_CHECKOUT,
    )

    mocker.patch(
        "simcore_service_api_server.services_rpc.wb_api_server._release_licensed_item_for_wallet",
        return_value=EXPECTED_RELEASE,
    )


@pytest.fixture
async def mock_rut_server_rpc(app: FastAPI, mocker: MockerFixture) -> None:
    from servicelib.rabbitmq import RabbitMQRPCClient

    app.dependency_overrides[get_resource_usage_tracker_client] = (
        lambda: ResourceUsageTrackerClient(
            _client=mocker.MagicMock(spec=RabbitMQRPCClient)
        )
    )

    mocker.patch(
        "simcore_service_api_server.services_rpc.resource_usage_tracker._get_licensed_item_checkout",
        return_value=EXPECTED_CHECKOUT,
    )


@pytest.mark.skipif(
    not os.getenv("PACT_BROKER_URL"),
    reason="This test runs only if PACT_BROKER_URL is provided",
)
def test_provider_against_pact(
    pact_broker_credentials: tuple[str, str, str],
    mock_wb_api_server_rpc: None,
    mock_rut_server_rpc: None,
    running_test_server_url: str,
) -> None:
    """
    Use the Pact Verifier to check the real provider
    against the generated contract.
    """
    broker_url, broker_username, broker_password = pact_broker_credentials

    broker_builder = (
        Verifier("OsparcApiServerCheckoutRelease")
        .add_transport(url=running_test_server_url)
        .broker_source(
            broker_url,
            username=broker_username,
            password=broker_password,
            selector=True,
        )
    )

    # NOTE: If you want to filter/test against specific contract use tags
    verifier = broker_builder.consumer_tags(
        "checkout_release"  # <-- Here you define which pact to verify
    ).build()

    # Set API version and run verification
    verifier.set_publish_options(version=API_VERSION, tags=None, branch=None)
    verifier.verify()
