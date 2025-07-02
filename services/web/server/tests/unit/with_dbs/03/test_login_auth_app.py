# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable

import pytest
import pytest_asyncio
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.application import create_application_auth
from simcore_service_webserver.security import security_web


@pytest.fixture
async def auth_app(
    app_environment: EnvVarsDict,
    disable_static_webserver: Callable,
) -> web.Application:
    assert app_environment

    # creates auth application instead
    app = create_application_auth()

    # checks endpoint exposed
    url = app.router["check_auth"].url_for()
    assert url.path == "/v0/auth:check"

    disable_static_webserver(app)
    return app


@pytest_asyncio.fixture(loop_scope="function", scope="function")
async def web_server(
    postgres_db: sa.engine.Engine,
    auth_app: web.Application,
    webserver_test_server_port: int,
    # tools
    aiohttp_server: Callable,
    mocked_send_email: None,
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
