# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import httpx
from fastapi import status
from fastapi.testclient import TestClient
from simcore_service_invitations._meta import API_VTAG
from simcore_service_invitations.api._invitations import (
    INVALID_INVITATION_URL_MSG,
    _InvitationContentAndLink,
)
from simcore_service_invitations.invitations import (
    InvitationContent,
    InvitationInputs,
    create_invitation_link,
)


def test_create_invitation(
    client: TestClient,
    basic_auth: httpx.BasicAuth,
    invitation_data: InvitationInputs,
):
    response = client.post(
        f"/{API_VTAG}/invitations",
        json={
            "issuer": invitation_data.issuer,
            "guest": invitation_data.guest,
            "trial_account_days": invitation_data.trial_account_days,
        },
        auth=basic_auth,
    )
    assert response.status_code == status.HTTP_200_OK, f"{response.json()=}"

    invitation = _InvitationContentAndLink(**response.json())
    assert invitation.issuer == invitation_data.issuer
    assert invitation.guest == invitation_data.guest
    assert invitation.trial_account_days == invitation_data.trial_account_days


def test_check_invitation(
    client: TestClient,
    basic_auth: httpx.BasicAuth,
    invitation_data: InvitationInputs,
):
    response = client.post(
        f"/{API_VTAG}/invitations",
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
    invitation_url = _InvitationContentAndLink.parse_obj(response.json()).invitation_url

    # check invitation_url
    response = client.post(
        f"/{API_VTAG}/invitations:extract",
        json={"invitation_url": invitation_url},
        auth=basic_auth,
    )
    assert response.status_code == 200, f"{response.json()=}"

    # decrypted invitation should be identical to request above
    invitation = InvitationContent.parse_obj(response.json())
    assert invitation.issuer == invitation_data.issuer
    assert invitation.guest == invitation_data.guest
    assert invitation.trial_account_days == invitation_data.trial_account_days


def test_check_valid_invitation(
    client: TestClient,
    basic_auth: httpx.BasicAuth,
    invitation_data: InvitationInputs,
    secret_key: str,
):
    invitation_url = create_invitation_link(
        invitation_data=invitation_data,
        secret_key=secret_key.encode(),
        base_url=f"{client.base_url}",
    )

    # check invitation_url
    response = client.post(
        f"/{API_VTAG}/invitations:extract",
        json={"invitation_url": invitation_url},
        auth=basic_auth,
    )
    assert response.status_code == 200, f"{response.json()=}"

    # decrypted invitation should be identical to request above
    invitation = InvitationContent.parse_obj(response.json())

    assert invitation.issuer == invitation_data.issuer
    assert invitation.guest == invitation_data.guest
    assert invitation.trial_account_days == invitation_data.trial_account_days


def test_check_invalid_invitation_with_different_secret(
    client: TestClient,
    basic_auth: httpx.BasicAuth,
    invitation_data: InvitationInputs,
    another_secret_key: str,
):
    invitation_url = create_invitation_link(
        invitation_data=invitation_data,
        secret_key=another_secret_key,  # <-- NOTE: DIFFERENT secret
        base_url=f"{client.base_url}",
    )

    # check invitation_url
    response = client.post(
        f"/{API_VTAG}/invitations:extract",
        json={"invitation_url": invitation_url},
        auth=basic_auth,
    )
    assert (
        response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    ), f"{response.json()=}"

    assert response.json()["detail"] == INVALID_INVITATION_URL_MSG


def test_check_invalid_invitation_with_wrong_fragment(
    client: TestClient,
    basic_auth: httpx.BasicAuth,
):
    # check invitation_url
    response = client.post(
        f"/{API_VTAG}/invitations:extract",
        json={
            "invitation_url": "https://foo.com#/page?some_value=True"
        },  # <-- NOTE: DIFFERENT fragment
        auth=basic_auth,
    )
    assert (
        response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    ), f"{response.json()=}"

    assert response.json()["detail"] == INVALID_INVITATION_URL_MSG


def test_check_invalid_invitation_with_wrong_code(
    client: TestClient,
    basic_auth: httpx.BasicAuth,
    invitation_data: InvitationInputs,
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
        f"/{API_VTAG}/invitations:extract",
        json={"invitation_url": invitation_url_with_invalid_code},
        auth=basic_auth,
    )
    assert (
        response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    ), f"{response.json()=}"

    assert response.json()["detail"] == INVALID_INVITATION_URL_MSG
