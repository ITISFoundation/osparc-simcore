# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
from typing import Iterator, Optional

import httpx
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pytest import FixtureRequest
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_invitations._meta import API_VTAG
from simcore_service_invitations.api._invitations import (
    INVALID_INVITATION_URL_MSG,
    InvitationGet,
)
from simcore_service_invitations.api._meta import Meta
from simcore_service_invitations.core.application import create_app
from simcore_service_invitations.invitations import (
    InvitationData,
    create_invitation_link,
)


@pytest.fixture
def client(app_environment: EnvVarsDict) -> Iterator[TestClient]:
    print(f"app_environment={json.dumps(app_environment)}")

    app = create_app()
    print("settings:\n", app.state.settings.json(indent=1))
    with TestClient(app, base_url="http://testserver.test") as client:
        yield client


def test_root(client: TestClient):
    response = client.get(f"/{API_VTAG}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text.startswith("simcore_service_invitations.api._meta@")


def test_meta(client: TestClient):
    response = client.get(f"/{API_VTAG}/meta")
    assert response.status_code == status.HTTP_200_OK
    meta = Meta.parse_obj(response.json())

    response = client.get(meta.docs_url)
    assert response.status_code == status.HTTP_200_OK


@pytest.fixture(params=["username", "password", "both", None])
def invalid_basic_auth(
    request: FixtureRequest, fake_user_name: str, fake_password: str
) -> Optional[httpx.BasicAuth]:
    invalid_case = request.param

    if invalid_case is None:
        return None

    kwargs = {"username": fake_user_name, "password": fake_password}

    if invalid_case == "both":
        kwargs = {key: "wrong" for key in kwargs}
    else:
        kwargs[invalid_case] = "wronggg"

    return httpx.BasicAuth(**kwargs)


def test_invalid_http_basic_auth(
    client: TestClient,
    invalid_basic_auth: Optional[httpx.BasicAuth],
    invitation_data: InvitationData,
):
    response = client.post(
        f"/{API_VTAG}/invitation",
        json=invitation_data.dict(),
        auth=invalid_basic_auth,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"{response.json()=}"


@pytest.fixture
def basic_auth(fake_user_name: str, fake_password: str) -> httpx.BasicAuth:
    return httpx.BasicAuth(username=fake_user_name, password=fake_password)


def test_create_invitation(
    client: TestClient,
    basic_auth: httpx.BasicAuth,
    invitation_data: InvitationData,
):
    response = client.post(
        f"/{API_VTAG}/invitation",
        json={
            "issuer": invitation_data.issuer,
            "guest": invitation_data.guest,
            "trial_account_days": invitation_data.trial_account_days,
        },
        auth=basic_auth,
    )
    assert response.status_code == status.HTTP_200_OK, f"{response.json()=}"

    invitation = InvitationGet(**response.json())
    assert invitation.issuer == invitation_data.issuer
    assert invitation.guest == invitation_data.guest
    assert invitation.trial_account_days == invitation_data.trial_account_days


def test_check_invitation(
    client: TestClient,
    basic_auth: httpx.BasicAuth,
    invitation_data: InvitationData,
):
    response = client.post(
        f"/{API_VTAG}/invitation",
        json={
            "issuer": invitation_data.issuer,
            "guest": invitation_data.guest,
            "trial_account_days": invitation_data.trial_account_days,
        },
        auth=basic_auth,
    )
    assert response.status_code == status.HTTP_200_OK, f"{response.json()=}"

    # up ot here, identifcal to above.
    # Let's use invitation link
    invitation_url = InvitationGet.parse_obj(response.json()).invitation_url

    # check invitation_url
    response = client.post(
        f"/{API_VTAG}/invitation:check",
        json={"invitation_url": invitation_url},
        auth=basic_auth,
    )
    assert response.status_code == 200, f"{response.json()=}"

    # decrypted invitation should be identical to request above
    invitation = InvitationGet.parse_obj(response.json())
    assert invitation.issuer == invitation_data.issuer
    assert invitation.guest == invitation_data.guest
    assert invitation.trial_account_days == invitation_data.trial_account_days


def test_check_valid_invitation(
    client: TestClient,
    basic_auth: httpx.BasicAuth,
    invitation_data: InvitationData,
    secret_key: str,
):
    invitation_url = create_invitation_link(
        invitation_data=invitation_data,
        secret_key=secret_key.encode(),
        base_url=f"{client.base_url}",
    )

    # check invitation_url
    response = client.post(
        f"/{API_VTAG}/invitation:check",
        json={"invitation_url": invitation_url},
        auth=basic_auth,
    )
    assert response.status_code == 200, f"{response.json()=}"

    # decrypted invitation should be identical to request above
    invitation = InvitationGet.parse_obj(response.json())

    assert invitation.issuer == invitation_data.issuer
    assert invitation.guest == invitation_data.guest
    assert invitation.trial_account_days == invitation_data.trial_account_days


def test_check_invalid_invitation_with_different_secret(
    client: TestClient,
    basic_auth: httpx.BasicAuth,
    invitation_data: InvitationData,
    another_secret_key: str,
):
    invitation_url = create_invitation_link(
        invitation_data=invitation_data,
        secret_key=another_secret_key,  # <-- NOTE: DIFFERENT secret
        base_url=f"{client.base_url}",
    )

    # check invitation_url
    response = client.post(
        f"/{API_VTAG}/invitation:check",
        json={"invitation_url": invitation_url},
        auth=basic_auth,
    )
    assert (
        response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    ), f"{response.json()=}"

    assert INVALID_INVITATION_URL_MSG == response.json()["detail"]


def test_check_invalid_invitation_with_wrong_fragment(
    client: TestClient,
    basic_auth: httpx.BasicAuth,
):
    # check invitation_url
    response = client.post(
        f"/{API_VTAG}/invitation:check",
        json={
            "invitation_url": "https://foo.com#/page?some_value=True"
        },  # <-- NOTE: DIFFERENT fragment
        auth=basic_auth,
    )
    assert (
        response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    ), f"{response.json()=}"

    assert INVALID_INVITATION_URL_MSG == response.json()["detail"]


def test_check_invalid_invitation_with_wrong_code(
    client: TestClient,
    basic_auth: httpx.BasicAuth,
    invitation_data: InvitationData,
    another_secret_key: str,
):
    invitation_url = create_invitation_link(
        invitation_data=invitation_data,
        secret_key=another_secret_key,  # <-- NOTE: DIFFERENT secret
        base_url=f"{client.base_url}",
    )

    invitation_url_with_invalid_code = invitation_url[:-3]

    # check invitation_url
    response = client.post(
        f"/{API_VTAG}/invitation:check",
        json={"invitation_url": invitation_url_with_invalid_code},
        auth=basic_auth,
    )
    assert (
        response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    ), f"{response.json()=}"

    assert INVALID_INVITATION_URL_MSG == response.json()["detail"]
