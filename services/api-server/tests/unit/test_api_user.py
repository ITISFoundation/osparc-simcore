# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

# from starlette.testclient import TestClient

import pytest
from httpx import AsyncClient
from starlette import status

from simcore_service_api_server.__version__ import api_vtag
from simcore_service_api_server.models.domain.api_keys import ApiKeyInDB
from simcore_service_api_server.models.schemas.profiles import Profile


@pytest.fixture
def auth(test_api_key: ApiKeyInDB):
    ## https://requests.readthedocs.io/en/master/user/authentication/
    # TODO: https://requests-oauthlib.readthedocs.io/en/latest/oauth2_workflow.html#backend-application-flow

    auth = (test_api_key.api_key, test_api_key.api_secret.get_secret_value())
    return auth

@pytest.mark.skip(reason="fixture under dev")
async def test_get_profile(client: AsyncClient, auth):

    resp = await client.get(f"/{api_vtag}/meta", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    resp = await client.get(f"/{api_vtag}/me", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    # validates response
    profile = Profile(**resp.json())
    assert profile.first_name == "James"

@pytest.mark.skip(reason="fixture under dev")
async def test_patch_profile(client: AsyncClient, auth):

    resp = await client.patch(
        f"/{api_vtag}/me",
        data={"first_name": "Oliver", "last_name": "Heaviside"},
        auth=auth,
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text

    profile = Profile(**resp.json())
    assert profile.first_name == "Oliver"
    assert profile.last_name == "Heaviside"
