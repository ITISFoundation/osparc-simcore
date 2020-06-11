# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

from typing import Dict

import pytest
from aiopg.sa.engine import Engine, create_engine
from starlette import status
from starlette.testclient import TestClient

from simcore_service_api_server.__version__ import api_version, api_vtag


@pytest.fixture(scope="module")
async def user_in_db(postgres_service):
    user = {}
    return user


@pytest.fixture(scope="module")
async def api_keys_in_db(postgres_service):
    api_keys = {"key": "key", "secret": "secret"}
    # TODO: inject api-keys in db
    return api_keys


def test_get_user(client: TestClient, api_keys_in_db: Dict, user_in_db: Dict):
    response = client.get(f"/{api_vtag}/meta")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["version"] == api_version

    # TODO: https://requests-oauthlib.readthedocs.io/en/latest/oauth2_workflow.html#backend-application-flow

    # TODO: authenciate with API
    auth_data = {
        "grant_type": "password",
        # "scope": "me projects you".split(),
        "username": api_keys_in_db["key"],
        "password": api_keys_in_db["secret"],
    }

    # form-encoded data
    response = client.post(f"/{api_vtag}/token", data=auth_data)

    # json response
    assert response.json() == {"access_token": "string", "token_type": "string"}

    # TODO: add access token in header??
    response = client.get(f"/{api_vtag}/user")
    assert response.status_code == status.HTTP_200_OK

    assert response.json() == {"name": user_in_db["name"], "email": user_in_db["email"]}

    ## response = client.get(f"/{api_vtag}/studies")
