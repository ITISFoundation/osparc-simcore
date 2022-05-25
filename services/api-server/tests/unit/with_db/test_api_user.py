# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

# from starlette.testclient import TestClient

import pytest
import respx
from fastapi import FastAPI
from httpx import AsyncClient, BasicAuth
from respx import MockRouter
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server.core.settings import ApplicationSettings
from simcore_service_api_server.models.domain.api_keys import ApiKeyInDB
from simcore_service_api_server.models.schemas.profiles import Profile
from starlette import status

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mocked_webserver_service_api(app: FastAPI):
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_WEBSERVER.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:

        respx_mock.get("/me", name="get_me").respond(
            status.HTTP_200_OK,
            # NOTE: webserver-api uses the same schema as api-server!
            json={"data": Profile.Config.schema_extra["example"]},
        )
        yield respx_mock


@pytest.fixture
def auth(fake_api_key: ApiKeyInDB) -> BasicAuth:
    return BasicAuth(fake_api_key.api_key, fake_api_key.api_secret.get_secret_value())


async def test_get_profile(
    client: AsyncClient, auth: BasicAuth, mocked_webserver_service_api: MockRouter
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


async def test_patch_profile(
    client: AsyncClient, auth: BasicAuth, mocked_webserver_service_api: MockRouter
):

    resp = await client.patch(
        f"/{API_VTAG}/me",
        data={"first_name": "Oliver", "last_name": "Heaviside"},
        auth=auth,
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text

    profile = Profile(**resp.json())
    assert profile.first_name == "Oliver"
    assert profile.last_name == "Heaviside"
