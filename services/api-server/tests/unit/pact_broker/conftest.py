import os
from threading import Thread
from time import sleep

import pytest
import uvicorn
from fastapi import FastAPI
from servicelib.utils import unused_port
from simcore_service_api_server.api.dependencies.authentication import (
    Identity,
    get_current_identity,
)


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup(
        "Pact broker contract test",
        description="Pact broker contract test specific parameters",
    )
    group.addoption(
        "--pact-broker-url",
        action="store",
        default=None,
        help="URL pointing to the deployment to be tested",
    )
    group.addoption(
        "--pact-broker-username",
        action="store",
        default=None,
        help="User name for logging into the deployment",
    )
    group.addoption(
        "--pact-broker-password",
        action="store",
        default=None,
        help="User name for logging into the deployment",
    )


@pytest.fixture()
def pact_broker_credentials(
    request: pytest.FixtureRequest,
):
    # Get credentials from either CLI arguments or environment variables
    broker_url = request.config.getoption("--broker-url", None) or os.getenv(
        "PACT_BROKER_URL"
    )
    broker_username = request.config.getoption("--broker-username", None) or os.getenv(
        "PACT_BROKER_USERNAME"
    )
    broker_password = request.config.getoption("--broker-password", None) or os.getenv(
        "PACT_BROKER_PASSWORD"
    )

    # Identify missing credentials
    missing = [
        name
        for name, value in {
            "PACT_BROKER_URL": broker_url,
            "PACT_BROKER_USERNAME": broker_username,
            "PACT_BROKER_PASSWORD": broker_password,
        }.items()
        if not value
    ]

    if missing:
        pytest.fail(
            f"Missing Pact Broker credentials: {', '.join(missing)}. Set them as environment variables or pass them as CLI arguments."
        )

    return broker_url, broker_username, broker_password


def mock_get_current_identity() -> Identity:
    return Identity(user_id=1, product_name="osparc", email="test@itis.swiss")


@pytest.fixture()
def run_test_server(
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
