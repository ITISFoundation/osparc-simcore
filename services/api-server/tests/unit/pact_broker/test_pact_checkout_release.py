# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import Iterable

import pytest
from fastapi import FastAPI
from models_library.api_schemas_webserver.licensed_items_checkouts import (
    LicensedItemCheckoutRpcGet,
)
from pact.v3 import Verifier
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_mock import HandlerMockFactory
from simcore_service_api_server._meta import API_VERSION
from simcore_service_api_server.api.dependencies.resource_usage_tracker_rpc import (
    get_resource_usage_tracker_client,
)
from simcore_service_api_server.services_rpc.resource_usage_tracker import (
    ResourceUsageTrackerClient,
)

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
async def mock_wb_api_server_rpc(
    app: FastAPI,
    mocked_app_rpc_dependencies: None,
    mock_handler_in_licenses_rpc_interface: HandlerMockFactory,
) -> None:

    mock_handler_in_licenses_rpc_interface(
        "checkout_licensed_item_for_wallet", return_value=EXPECTED_CHECKOUT
    )

    mock_handler_in_licenses_rpc_interface(
        "release_licensed_item_for_wallet", return_value=EXPECTED_RELEASE
    )


@pytest.fixture
def mock_rut_server_rpc(app: FastAPI, mocker: MockerFixture) -> Iterable[None]:
    import simcore_service_api_server.services_rpc.resource_usage_tracker  # noqa: PLC0415
    from servicelib.rabbitmq import RabbitMQRPCClient  # noqa: PLC0415

    app.dependency_overrides[get_resource_usage_tracker_client] = (
        lambda: ResourceUsageTrackerClient(
            _client=mocker.MagicMock(spec=RabbitMQRPCClient)
        )
    )

    mocker.patch.object(
        simcore_service_api_server.services_rpc.resource_usage_tracker,
        "_get_licensed_item_checkout",
        return_value=EXPECTED_CHECKOUT,
    )

    yield None

    app.dependency_overrides.pop(get_resource_usage_tracker_client, None)


def test_osparc_api_server_checkout_release_pact(
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
        "checkout_release"  # NOTE: Here you define which pact to verify
    ).build()

    # Set API version and run verification
    verifier.set_publish_options(version=API_VERSION, tags=None, branch=None)
    verifier.verify()
