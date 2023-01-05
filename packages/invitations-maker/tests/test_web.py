# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
from typing import Iterator

import httpx
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from invitations_maker.web_api import Meta
from invitations_maker.web_application import create_app
from pytest_simcore.helpers.typing_env import EnvVarsDict


@pytest.fixture
def client(app_environment: EnvVarsDict) -> Iterator[TestClient]:
    print(f"app_environment={json.dumps(app_environment)}")

    app = create_app()
    with TestClient(app) as client:
        yield client


def test_root(client: TestClient):
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text.startswith("invitations_maker.web_api@")


def test_meta(client: TestClient):
    response = client.get("/meta")
    assert response.status_code == status.HTTP_200_OK
    meta = Meta.parse_obj(response.json())

    response = client.get(meta.docs_url)
    assert response.status_code == status.HTTP_200_OK


def test_make_invitation(
    client: TestClient,
    fake_user_name: str,
    fake_password: str,
):
    response = client.post(
        "/invitation",
        json={
            "i": "issuerid",
            "g": "invitedguest@company.com",
            "t": None,
            # "LicenseRequestID": 123,
        },
        auth=httpx.BasicAuth(fake_user_name, fake_password),
    )
    assert response.status_code == 200, f"{response.json()=}"
