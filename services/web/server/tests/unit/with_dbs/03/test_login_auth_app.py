# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging
from collections.abc import Callable
from pathlib import Path

import pytest
import pytest_asyncio
import sqlalchemy as sa
import yaml
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.application import create_application_auth
from simcore_service_webserver.application_settings import (
    ApplicationSettings,
    get_application_settings,
)
from simcore_service_webserver.application_settings_utils import AppConfigDict
from simcore_service_webserver.security import security_web


@pytest.fixture
def service_name() -> str:
    return "wb-auth"


@pytest.fixture
def app_environment_for_wb_authz_service_dict(
    docker_compose_service_environment_dict: EnvVarsDict,
    docker_compose_service_hostname: str,
    default_app_cfg: AppConfigDict,
) -> EnvVarsDict:

    postgres_cfg = default_app_cfg["db"]["postgres"]

    # Checks that docker-compose service environment is correct
    assert (
        docker_compose_service_environment_dict["WEBSERVER_APP_FACTORY_NAME"]
        == "WEBSERVER_AUTHZ_APP_FACTORY"
    )
    # expected tracing in the docker-environ BUT we will disable it for tests
    assert "WEBSERVER_TRACING" in docker_compose_service_environment_dict
    assert (
        "TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT"
        in docker_compose_service_environment_dict
    )
    assert "WEBSERVER_DIAGNOSTICS" in docker_compose_service_environment_dict
    assert "WEBSERVER_PROFILING" in docker_compose_service_environment_dict

    return {
        **docker_compose_service_environment_dict,
        # NOTE: TEST-stack uses different env-vars
        # this is temporary here until we get rid of config files
        # SEE https://github.com/ITISFoundation/osparc-simcore/issues/8129
        "POSTGRES_DB": postgres_cfg["database"],
        "POSTGRES_HOST": postgres_cfg["host"],
        "POSTGRES_PORT": postgres_cfg["port"],
        "POSTGRES_USER": postgres_cfg["user"],
        "POSTGRES_PASSWORD": postgres_cfg["password"],
        "HOSTNAME": docker_compose_service_hostname,
        "WEBSERVER_TRACING": "null",  # BUT we will disable it for tests
    }


@pytest.fixture
def app_environment_for_wb_authz_service(
    monkeypatch: pytest.MonkeyPatch,
    app_environment_for_wb_authz_service_dict: EnvVarsDict,
    service_name: str,
) -> EnvVarsDict:
    """Mocks the environment variables for the auth app service (considering docker-compose's environment)."""

    mocked_envs = setenvs_from_dict(
        monkeypatch, {**app_environment_for_wb_authz_service_dict}
    )

    # test how service will load
    settings = ApplicationSettings.create_from_envs()

    logging.info(
        "Application settings:\n%s",
        settings.model_dump_json(indent=2),
    )

    assert service_name == settings.WEBSERVER_HOST
    assert settings.WEBSERVER_DB is not None
    assert settings.WEBSERVER_SESSION is not None
    assert settings.WEBSERVER_SECURITY is not None
    assert settings.WEBSERVER_TRACING is None, "No tracing for tests"

    return mocked_envs


@pytest.fixture
async def wb_auth_app(
    app_environment_for_wb_authz_service: EnvVarsDict,
) -> web.Application:
    assert app_environment_for_wb_authz_service

    # creates auth application instead
    app = create_application_auth()

    settings = get_application_settings(app)
    assert settings.WEBSERVER_APP_FACTORY_NAME == "WEBSERVER_AUTHZ_APP_FACTORY"
    assert (
        settings.APP_NAME == "simcore_service_wb_auth"
    ), "APP_NAME in docker-compose for wb-auth is not set correctly"

    # checks endpoint exposed
    url = app.router["check_auth"].url_for()
    assert url.path == "/v0/auth:check"

    return app


@pytest_asyncio.fixture(loop_scope="function", scope="function")
async def web_server(
    postgres_db: sa.engine.Engine,  # sets up postgres database
    wb_auth_app: web.Application,
    webserver_test_server_port: int,
    # tools
    aiohttp_server: Callable,
) -> TestServer:
    # Overrides tests/unit/with_dbs/context.py:web_server fixture

    # Add test routes for login/logout
    async def test_login(request: web.Request) -> web.Response:
        data = await request.json()
        response = web.Response(status=200)
        return await security_web.remember_identity(
            request, response, user_email=data["email"]
        )

    async def test_logout(request: web.Request) -> web.Response:
        response = web.Response(status=200)
        await security_web.forget_identity(request, response)
        return response

    wb_auth_app.router.add_post("/v0/test/login", test_login)
    wb_auth_app.router.add_post("/v0/test/logout", test_logout)

    return await aiohttp_server(wb_auth_app, port=webserver_test_server_port)


# @pytest.mark.parametrize(
#     "user_role", [role for role in UserRole if role > UserRole.ANONYMOUS]
# )
async def test_check_endpoint_in_auth_app(client: TestClient, user: UserInfoDict):
    assert client.app

    # user is not signed it (ANONYMOUS)
    response = await client.get("/v0/auth:check")
    await assert_status(response, status.HTTP_401_UNAUTHORIZED)

    # Sign in using test login route
    await client.post("/v0/test/login", json={"email": user["email"]})

    # Now user should be authorized
    response = await client.get("/v0/auth:check")
    await assert_status(response, status.HTTP_204_NO_CONTENT)

    await client.post("/v0/test/logout")

    response = await client.get("/v0/auth:check")
    await assert_status(response, status.HTTP_401_UNAUTHORIZED)


def test_docker_compose_dev_vendors_forwardauth_configuration(
    services_docker_compose_dev_vendors_file: Path,
    env_devel_dict: EnvVarsDict,
):
    """Test that manual service forwardauth.address points to correct WB_AUTH_WEBSERVER_HOST and port.

    NOTE: traefik's `forwardauth` labels are also used in
        `services/director-v2/src/simcore_service_director_v2/modules/dynamic_sidecar/docker_service_specs/proxy.py`
    """

    # Load docker-compose file
    compose_config = yaml.safe_load(
        services_docker_compose_dev_vendors_file.read_text()
    )

    # Get the manual service configuration
    manual_service = compose_config.get("services", {}).get("manual")
    assert (
        manual_service is not None
    ), "Manual service not found in docker-compose-dev-vendors.yml"

    # Extract forwardauth.address from deploy labels
    deploy_labels = manual_service.get("deploy", {}).get("labels", [])
    forwardauth_address_label = None

    for label in deploy_labels:
        if "forwardauth.address=" in label:
            forwardauth_address_label = label
            break

    assert (
        forwardauth_address_label is not None
    ), "forwardauth.address label not found in manual service"

    # Parse the forwardauth address
    # Expected format: traefik.http.middlewares.${SWARM_STACK_NAME}_manual-auth.forwardauth.address=http://${WB_AUTH_WEBSERVER_HOST}:${WB_AUTH_WEBSERVER_PORT}/v0/auth:check
    address_part = forwardauth_address_label.split("forwardauth.address=")[1]

    # Verify it contains the expected pattern
    assert (
        "${WB_AUTH_WEBSERVER_HOST}" in address_part
    ), "forwardauth.address should reference WB_AUTH_WEBSERVER_HOST"
    assert (
        "${WB_AUTH_WEBSERVER_PORT}" in address_part
    ), "forwardauth.address should reference WB_AUTH_WEBSERVER_PORT"
    assert (
        "/v0/auth:check" in address_part
    ), "forwardauth.address should point to /v0/auth:check endpoint"

    # Verify the full expected pattern
    expected_pattern = (
        "http://${WB_AUTH_WEBSERVER_HOST}:${WB_AUTH_WEBSERVER_PORT}/v0/auth:check"
    )
    assert (
        address_part == expected_pattern
    ), f"forwardauth.address should be '{expected_pattern}', got '{address_part}'"

    # Verify that WB_AUTH_WEBSERVER_HOST and WB_AUTH_WEBSERVER_PORT are configured in the .env-devel file!
    wb_auth_host = env_devel_dict.get("WB_AUTH_WEBSERVER_HOST")
    wb_auth_port = env_devel_dict.get("WB_AUTH_WEBSERVER_PORT")

    assert (
        wb_auth_host is not None
    ), "WB_AUTH_WEBSERVER_HOST should be configured in test environment"
    assert (
        wb_auth_port is not None
    ), "WB_AUTH_WEBSERVER_PORT should be configured in test environment"
