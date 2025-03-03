# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import os
from threading import Thread
from time import sleep

import pytest
import uvicorn
from fastapi import FastAPI
from models_library.api_schemas_webserver.licensed_items import (
    LicensedItemRpcGet,
    LicensedItemRpcGetPage,
)
from pact.v3 import Verifier
from pytest_mock import MockerFixture
from servicelib.utils import unused_port
from simcore_service_api_server._meta import API_VERSION
from simcore_service_api_server.api.dependencies.authentication import (
    Identity,
    get_current_identity,
)
from simcore_service_api_server.api.dependencies.webserver_rpc import (
    get_wb_api_rpc_client,
)
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient


def mock_get_current_identity() -> Identity:
    return Identity(user_id=1, product_name="osparc", email="test@itis.swiss")


# Fake response based on values from 05_licensed_items.json
EXPECTED_LICENSED_ITEMS = [
    {
        "created_at": "2025-02-19T13:46:30.258102Z",
        "display_name": "3 Week Male Mouse V1.0",
        "is_hidden_on_market": False,
        "key": "MODEL_MOUSE_3W_M_POSABLE",
        "licensed_item_id": "f26587de-abad-49cb-9b4f-e6e1fad7f5c1",
        "licensed_resource_type": "VIP_MODEL",
        "licensed_resources": [
            {
                "category_display": "Animal",
                "category_id": "AnimalWholeBody",
                "source": {
                    "available_from_url": None,
                    "description": "Animal Models - 3 Week Male Mouse (B6C3F1) V1.0",
                    "doi": "10.13099/VIP91206-01-0",
                    "features": {
                        "age": "3 weeks",
                        "date": "2021-03-16",
                        "functionality": "Posable",
                        "height": "70 mm",
                        "name": "B6C3F1N Male 3W",
                        "sex": "male",
                        "species": "Mouse",
                        "version": "1.0",
                        "weight": "12.3 g",
                    },
                    "id": 138,
                    "license_key": "MODEL_MOUSE_3W_M_POSABLE",
                    "license_version": "V1.0",
                    "protection": "Code",
                    "thumbnail": "https://itis.swiss/assets/images/Virtual-Population/Animals-Cropped/3WeekMouse.png",
                },
                "terms_of_use_url": "https://raw.githubusercontent.com/ITISFoundation/licenses/refs/heads/main/models/User%20License%20Animal%20Models%20v1.x.md",
            }
        ],
        "modified_at": "2025-02-19T13:46:30.258102Z",
        "pricing_plan_id": 21,
        "version": "1.0.0",
    },
    {
        "created_at": "2025-02-19T13:46:30.302673Z",
        "display_name": "Big Male Rat V1.0",
        "is_hidden_on_market": False,
        "key": "MODEL_RAT567_M",
        "licensed_item_id": "0713928d-9e36-444e-b720-26e97ad7d861",
        "licensed_resource_type": "VIP_MODEL",
        "licensed_resources": [
            {
                "category_display": "Animal",
                "category_id": "AnimalWholeBody",
                "source": {
                    "available_from_url": None,
                    "description": "Animal Models - Big Male Rat V1-x",
                    "doi": "10.13099/VIP91101-01-0",
                    "features": {
                        "date": "2012-01-01",
                        "functionality": "Static",
                        "height": "260 mm",
                        "name": "Big Male Rat",
                        "sex": "male",
                        "species": "Rat",
                        "version": "1.0",
                        "weight": "567 g",
                    },
                    "id": 21,
                    "license_key": "MODEL_RAT567_M",
                    "license_version": "V1.0",
                    "protection": "Code",
                    "thumbnail": "https://itis.swiss/assets/images/Virtual-Population/Animals-Cropped/BigMaleRat567g.png",
                },
                "terms_of_use_url": "https://raw.githubusercontent.com/ITISFoundation/licenses/refs/heads/main/models/User%20License%20Animal%20Models%20v1.x.md",
            },
            {
                "category_display": "Animal",
                "category_id": "AnimalWholeBody",
                "source": {
                    "available_from_url": None,
                    "description": "Animal Models - Posable Big Male Rat V1-x",
                    "doi": "10.13099/VIP91101-01-1",
                    "features": {
                        "date": "2018-01-22",
                        "functionality": "Posable",
                        "height": "260 mm",
                        "name": "Big Male Rat",
                        "sex": "male",
                        "species": "Rat",
                        "version": "1.0",
                        "weight": "567 g",
                    },
                    "id": 111,
                    "license_key": "MODEL_RAT567_M",
                    "license_version": "V1.0",
                    "protection": "Code",
                    "thumbnail": "https://itis.swiss/assets/images/Virtual-Population/Animals-Cropped/BigMaleRat567g.png",
                },
                "terms_of_use_url": "https://raw.githubusercontent.com/ITISFoundation/licenses/refs/heads/main/models/User%20License%20Animal%20Models%20v1.x.md",
            },
        ],
        "modified_at": "2025-02-19T13:46:30.302673Z",
        "pricing_plan_id": 21,
        "version": "1.0.0",
    },
]


EXPECTED_LICENSED_ITEMS_PAGE = LicensedItemRpcGetPage(
    items=[LicensedItemRpcGet.model_validate(item) for item in EXPECTED_LICENSED_ITEMS],
    total=len(EXPECTED_LICENSED_ITEMS),
)


class DummyRpcClient:
    pass


@pytest.fixture
async def mock_wb_api_server_rpc(app: FastAPI, mocker: MockerFixture) -> MockerFixture:

    app.dependency_overrides[get_wb_api_rpc_client] = lambda: WbApiRpcClient(
        _client=DummyRpcClient()
    )

    mocker.patch(
        "simcore_service_api_server.services_rpc.wb_api_server._get_licensed_items",
        return_value=EXPECTED_LICENSED_ITEMS_PAGE,
    )

    return mocker


@pytest.fixture()
def run_test_server(
    # get_free_port: int,
    # get_unused_port: int,
    app: FastAPI,
):
    """
    Spins up a FastAPI server in a background thread and yields a base URL.
    The 'mocked_catalog_service' fixture ensures the function is already
    patched by the time we start the server.
    """
    # Override
    app.dependency_overrides[get_current_identity] = mock_get_current_identity

    port = unused_port()
    base_url = f"http://localhost:{port}"

    config = uvicorn.Config(
        app,
        host="localhost",
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    thread = Thread(target=server.run, daemon=True)
    thread.start()

    # Wait a bit for the server to be ready
    sleep(1)

    yield base_url  # , before_server_start

    server.should_exit = True
    thread.join()


@pytest.mark.skipif(
    not os.getenv("PACT_BROKER_URL"),
    reason="This test runs only if PACT_BROKER_URL is provided",
)
def test_provider_against_pact(
    pact_broker_credentials: tuple[str, str, str],
    mock_wb_api_server_rpc: MockerFixture,
    run_test_server: str,
) -> None:
    """
    Use the Pact Verifier to check the real provider
    against the generated contract.
    """
    broker_url, broker_username, broker_password = pact_broker_credentials

    broker_builder = (
        Verifier("OsparcApiProvider")
        .add_transport(url=run_test_server)
        .broker_source(
            broker_url,
            username=broker_username,
            password=broker_password,
            selector=True,
        )
    )

    # NOTE: If you want to filter/test against specific contract use tags
    verifier = broker_builder.consumer_tags(
        "licensed_items"  # <-- Here you define which pact to verify
    ).build()

    # Set API version and run verification
    verifier.set_publish_options(version=API_VERSION, tags=None, branch=None)
    verifier.verify()
