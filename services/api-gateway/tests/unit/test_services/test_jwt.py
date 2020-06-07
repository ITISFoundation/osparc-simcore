# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import importlib

import pytest

from simcore_service_api_gateway.models.schemas.tokens import TokenData
from simcore_service_api_gateway.services.jwt import (
    create_access_token,
    get_access_token_data,
)


@pytest.fixture()
def mock_secret_key(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "your-256-bit-secret")

    import simcore_service_api_gateway.services.jwt

    importlib.reload(simcore_service_api_gateway.services.jwt)


def test_access_token_data(mock_secret_key):

    data = TokenData(user_id=33, scopes=[])
    jwt = create_access_token(data, expires_in_mins=None)

    # checks jwt against https://jwt.io/#debugger-io
    # assert jwt == b"ey ...

    received_data = get_access_token_data(jwt)

    assert data == received_data
