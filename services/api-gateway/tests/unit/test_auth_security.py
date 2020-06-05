# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import importlib

import pytest

from simcore_service_api_gateway.auth_security import (
    create_access_token,
    get_access_token_data,
    get_password_hash,
    verify_password,
)
from simcore_service_api_gateway.schemas import TokenData


def test_has_password():
    hashed_pass = get_password_hash("secret")
    assert hashed_pass != "secret"
    assert verify_password("secret", hashed_pass)


@pytest.fixture()
def mock_secret_key(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "your-256-bit-secret")

    import simcore_service_api_gateway.auth_security

    importlib.reload(simcore_service_api_gateway.auth_security)


def test_access_token_data(mock_secret_key):

    data = TokenData(user_id=33, scopes=[])
    jwt = create_access_token(data, expires_in_mins=None)

    # checks jwt against https://jwt.io/#debugger-io
    # assert jwt == b"ey ...

    received_data = get_access_token_data(jwt)

    assert data == received_data
