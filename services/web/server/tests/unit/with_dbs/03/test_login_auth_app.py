# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging
from collections.abc import Callable

import pytest
import pytest_asyncio
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from faker import Faker
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.application import create_application_auth
from simcore_service_webserver.application_settings import ApplicationSettings
from simcore_service_webserver.security import security_web


@pytest.fixture
def service_name() -> str:
    return "wb-authz"


@pytest.fixture
def app_environment_for_wb_authz_service_dict(
    docker_compose_service_environment_dict: EnvVarsDict,
    service_name: str,
    faker: Faker,
) -> EnvVarsDict:
    hostname, task_slot = faker.hostname(levels=0), faker.random_int(min=0, max=10)

    assert (
        docker_compose_service_environment_dict["WEBSERVER_APP_FACTORY_NAME"]
        == "WEBSERVER_AUTHZ_APP_FACTORY"
    )

    return {
        **docker_compose_service_environment_dict,
        "HOSTNAME": f"auth-{hostname}-{task_slot}",  # TODO: load from docker-compose
        # TODO: add everything coming from Dockerfile?
    }


@pytest.fixture
def app_environment_for_wb_authz_service(
    monkeypatch: pytest.MonkeyPatch,
    app_environment_for_wb_authz_service_dict: EnvVarsDict,
    faker: Faker,
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

    return mocked_envs


@pytest.fixture
async def auth_app(
    app_environment_for_wb_authz_service: EnvVarsDict,
) -> web.Application:
    assert app_environment_for_wb_authz_service

    # creates auth application instead
    app = create_application_auth()

    # checks endpoint exposed
    url = app.router["check_auth"].url_for()
    assert url.path == "/v0/auth:check"

    return app


@pytest_asyncio.fixture(loop_scope="function", scope="function")
async def web_server(
    postgres_db: sa.engine.Engine,  # sets up postgres database
    auth_app: web.Application,
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

    auth_app.router.add_post("/v0/test/login", test_login)
    auth_app.router.add_post("/v0/test/logout", test_logout)

    return await aiohttp_server(auth_app, port=webserver_test_server_port)


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
