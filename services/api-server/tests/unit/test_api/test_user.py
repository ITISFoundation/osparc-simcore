# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

# from typing import Dict

# import pytest
from starlette import status
from starlette.testclient import TestClient

from simcore_service_api_server.__version__ import api_vtag
from simcore_service_api_server.models.domain.api_keys import ApiKeyInDB
from simcore_service_api_server.models.schemas.profiles import Profile, ProfileUpdate


def test_authentication(client: TestClient, test_api_key: ApiKeyInDB):
    ## https://requests.readthedocs.io/en/master/user/authentication/
    # TODO: https://requests-oauthlib.readthedocs.io/en/latest/oauth2_workflow.html#backend-application-flow

    auth = (test_api_key.api_key, test_api_key.api_secret.get_secret_value())

    resp = client.get(f"/{api_vtag}/meta", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    resp = client.get(f"/{api_vtag}/me", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    # validates response
    profile = Profile.parse_obj(resp.json())
    assert profile.first_name == "James"

    resp = client.patch(
        f"/{api_vtag}/me",
        data=ProfileUpdate(first_name="Oliver", last_name="Heaviside").dict(),
        auth=auth,
    )
    assert resp.status_code == status.HTTP_200_OK
