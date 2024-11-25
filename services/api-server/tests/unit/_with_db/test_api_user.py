# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import json
from copy import deepcopy

import httpx
import pytest
import respx
from fastapi import FastAPI
from respx import MockRouter
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.core.settings import ApplicationSettings
from simcore_service_api_server.models.schemas.profiles import Profile
from starlette import status


@pytest.fixture
def mocked_webserver_service_api(app: FastAPI):
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
        me = deepcopy(Profile.model_config["json_schema_extra"]["example"])

        def _get_me(request):
            return httpx.Response(status.HTTP_200_OK, json={"data": me})

        def _update_me(request: httpx.Request):
            changes = json.loads(request.content.decode(request.headers.encoding))
            me.update(changes)
            return httpx.Response(status.HTTP_200_OK, json={"data": me})

        respx_mock.get("/me", name="get_me").mock(side_effect=_get_me)
        respx_mock.put("/me", name="update_me").mock(side_effect=_update_me)

        yield respx_mock

        del me


async def test_get_profile(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    mocked_webserver_service_api: MockRouter,
):
    # needs no auth
    resp = await client.get(f"/{API_VTAG}/meta")
    assert resp.status_code == status.HTTP_200_OK

    # needs auth
    resp = await client.get(f"/{API_VTAG}/me")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert not mocked_webserver_service_api["get_me"].called

    resp = await client.get(f"/{API_VTAG}/me", auth=auth)
    assert resp.status_code == status.HTTP_200_OK
    assert mocked_webserver_service_api["get_me"].called

    profile = Profile(**resp.json())
    assert profile.first_name == "James"
    assert profile.last_name == "Maxwell"


async def test_update_profile(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    mocked_webserver_service_api: MockRouter,
):
    # needs auth
    resp = await client.put(
        f"/{API_VTAG}/me",
        json={"first_name": "Oliver", "last_name": "Heaviside"},
        auth=auth,
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text

    profile = Profile.model_validate(resp.json())
    assert profile.first_name == "Oliver"
    assert profile.last_name == "Heaviside"
