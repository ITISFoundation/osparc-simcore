# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_invitations.core.application import create_app


@pytest.fixture
def client(app_environment: EnvVarsDict) -> Iterator[TestClient]:
    print(f"app_environment={json.dumps(app_environment)}")

    app = create_app()
    print("settings:\n", app.state.settings.model_dump_json(indent=1))
    with TestClient(app, base_url="http://testserver.test") as client:
        yield client


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
