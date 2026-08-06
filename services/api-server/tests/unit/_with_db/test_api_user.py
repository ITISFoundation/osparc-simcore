# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=protected-access


import json
from unittest.mock import MagicMock

import httpx
import pytest
import respx
from fastapi import FastAPI
from models_library.api_schemas_webserver.users import MyProfileRestGet as WebProfileGet
from pytest_mock import MockType
from respx import MockRouter
from servicelib.common_headers import X_SIMCORE_LANGUAGE
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.core.settings import ApplicationSettings
from simcore_service_api_server.models.schemas.profiles import Profile
from simcore_service_api_server.services_http.webserver import AuthSession
from starlette import status


@pytest.fixture
def mocked_webserver_rest_api(app: FastAPI):
    """Mocks some responses of web-server service"""

    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_WEBSERVER.api_base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        # NOTE: webserver-api uses the same schema as api-server!
        # in-memory fake data
        me: dict = WebProfileGet.model_json_schema()["examples"][0]
        me["first_name"] = "James"
        me["last_name"] = "Maxwell"
        me["language"] = "es_ES"

        def _get_me(request):
            return httpx.Response(status.HTTP_200_OK, json={"data": me})

        def _update_me(request: httpx.Request):
            changes = json.loads(request.content.decode(request.headers.encoding))
            me.update(changes)
            return httpx.Response(status.HTTP_200_OK, json={"data": me})

        respx_mock.get("/me", name="get_me").mock(side_effect=_get_me)
        respx_mock.patch("/me", name="update_me").mock(side_effect=_update_me)

        yield respx_mock


async def test_get_profile(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    mocked_webserver_rest_api: MockRouter,
    mocked_webserver_rpc_api: dict[str, MockType],
):
    # needs no auth
    resp = await client.get(f"/{API_VTAG}/meta")
    assert resp.status_code == status.HTTP_200_OK

    # needs auth
    resp = await client.get(f"/{API_VTAG}/me")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert not mocked_webserver_rest_api["get_me"].called

    resp = await client.get(f"/{API_VTAG}/me", auth=auth)
    assert resp.status_code == status.HTTP_200_OK
    assert mocked_webserver_rest_api["get_me"].called

    profile = Profile(**resp.json())
    assert profile.first_name == "James"
    assert profile.last_name == "Maxwell"
    assert profile.language == "es_ES"


async def test_update_profile(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    mocked_webserver_rest_api: MockRouter,
    mocked_webserver_rpc_api: dict[str, MockType],
):
    # needs auth
    resp = await client.put(
        f"/{API_VTAG}/me",
        json={"first_name": "Oliver", "last_name": "Heaviside", "language": "zh_CN"},
        auth=auth,
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text

    profile = Profile.model_validate(resp.json())
    assert profile.first_name == "Oliver"
    assert profile.last_name == "Heaviside"
    assert profile.language == "zh_CN"


def test_auth_session_forwards_locale_as_x_simcore_language_header():
    """AuthSession._get_session_headers() must forward the caller's resolved
    locale to the webserver as the X-Simcore-Language header.
    """
    session = AuthSession(
        _product_name="osparc",
        _user_id=1,
        _api=MagicMock(),
        _long_running_task_client=MagicMock(),
        vtag="v0",
        _locale="es_ES",
    )
    headers = session._get_session_headers()  # noqa: SLF001
    assert headers[X_SIMCORE_LANGUAGE] == "es_ES"


def test_auth_session_omits_locale_header_when_not_resolved():
    """No X-Simcore-Language header is sent when the incoming request had no
    resolved locale (e.g. LocaleMiddleware disabled).
    """
    session = AuthSession(
        _product_name="osparc",
        _user_id=1,
        _api=MagicMock(),
        _long_running_task_client=MagicMock(),
        vtag="v0",
    )
    headers = session._get_session_headers()  # noqa: SLF001
    assert X_SIMCORE_LANGUAGE not in headers
