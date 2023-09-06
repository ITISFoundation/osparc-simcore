# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import httpx
import pytest


@pytest.fixture(params=["username", "password", "both", None])
def invalid_basic_auth(
    request: pytest.FixtureRequest, fake_user_name: str, fake_password: str
) -> httpx.BasicAuth | None:
    invalid_case = request.param

    if invalid_case is None:
        return None

    kwargs = {"username": fake_user_name, "password": fake_password}

    if invalid_case == "both":
        kwargs = {key: "wrong" for key in kwargs}
    else:
        kwargs[invalid_case] = "wronggg"

    return httpx.BasicAuth(**kwargs)


@pytest.fixture
def basic_auth(fake_user_name: str, fake_password: str) -> httpx.BasicAuth:
    return httpx.BasicAuth(username=fake_user_name, password=fake_password)
