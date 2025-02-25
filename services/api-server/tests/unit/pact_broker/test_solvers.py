from copy import deepcopy
from threading import Thread
from time import sleep
from typing import Any

import pytest
import uvicorn
from fastapi import FastAPI
from pact.v3 import Verifier
from pytest_simcore.helpers import faker_catalog
from respx import MockRouter
from simcore_service_api_server.api.dependencies.authentication import (
    Identity,
    get_current_identity,
)


@pytest.fixture
def mocked_catalog_service_api(
    mocked_catalog_service_api_base: MockRouter,
    catalog_service_openapi_specs: dict[str, Any],
) -> tuple:
    """
    Mocks the API response, allowing dynamic modifications
    based on provider states.
    """
    respx_mock = mocked_catalog_service_api_base
    openapi = deepcopy(catalog_service_openapi_specs)

    def apply_mock_for_state(provider_state):
        """Clear existing mocks and apply new ones based on provider state."""
        respx_mock.reset()  # Clear all previous mocks

        if provider_state == "Solver exists":
            respx_mock.get(
                path__startswith="/v0/services/simcore/services/comp/isolve-gpu/2.2.129",
                name="get_service",
            ).respond(
                200,
                json=faker_catalog.create_service_out(
                    key="simcore/services/comp/isolve-gpu",
                    version="2.2.129",
                    name="isolve gpu",
                    description="GPU solvers for sim4life",
                    owner="guidon@itis.swiss",
                ),
            )
        elif provider_state == "Solver does not exist":
            respx_mock.get(
                path__startswith="/v0/services/simcore/services/comp/isolve-gpu/2.2.129",
                name="get_service",
            ).respond(404)

    return respx_mock, apply_mock_for_state


def mock_get_current_identity() -> Identity:
    return Identity(user_id=1, product_name="osparc", email="test@itis.swiss")


@pytest.fixture()
def run_test_server(
    mocked_catalog_service_api,
    get_free_port: int,
    app: FastAPI,
):
    """
    Spins up a FastAPI server in a background thread and yields a base URL.
    The 'mocked_catalog_service' fixture ensures the function is already
    patched by the time we start the server.
    """
    # Get the mock and apply function
    _, apply_mock_for_state = mocked_catalog_service_api

    def before_server_start(state):
        """This function applies the correct mock before server start"""
        apply_mock_for_state(state)

    # Override
    app.dependency_overrides[get_current_identity] = mock_get_current_identity

    port = get_free_port
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

    yield base_url, before_server_start

    server.should_exit = True
    thread.join()


# @pytest.mark.skipif(not os.getenv("CI"), reason="Skipping test: Only runs in CI")
def test_provider_against_pact(pact_broker_credentials, run_test_server):
    """
    Use the Pact Verifier to check the real provider
    against the generated contract.
    """
    server_url, before_server_start = run_test_server
    broker_url, broker_username, broker_password = pact_broker_credentials

    def solver_exists(params: dict | None):
        """Activate mock before running tests"""
        before_server_start("Solver exists")

    broker_builder = (
        Verifier("OsparcApiProvider")
        .add_transport(url=server_url)
        .broker_source(
            broker_url,
            username=broker_username,
            password=broker_password,
            selector=True,
        )
    )

    # NOTE: If you want to filter/test agains specific contract
    # `verifier = broker_builder.consumer_tags("test").build()`

    verifier = broker_builder.build()

    # Register provider states BEFORE verification
    verifier.state_handler({"Solver exists": solver_exists})

    # Set API version and run verification
    verifier.set_publish_options(
        version="1.0.1", tags=None, branch=None  # API SPECS VERSION
    )
    verifier.verify()
