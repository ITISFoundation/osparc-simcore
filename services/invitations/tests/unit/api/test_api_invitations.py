# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import httpx
from fastapi import status
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from models_library.api_schemas_invitations.invitations import (
    ApiInvitationContentAndLink,
)
from models_library.products import ProductName
from simcore_service_invitations._meta import API_VTAG
from simcore_service_invitations.api._invitations import INVALID_INVITATION_URL_MSG
from simcore_service_invitations.services.invitations import (
    InvitationContent,
    InvitationInputs,
    create_invitation_link_and_content,
)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(invitation_input=st.builds(InvitationInputs, guest=st.emails()))
def test_create_invitation(
    invitation_input: InvitationInputs,
    client: TestClient,
    basic_auth: httpx.BasicAuth,
):
    response = client.post(
        f"/{API_VTAG}/invitations",
        json=invitation_input.model_dump(exclude_none=True),
        auth=basic_auth,
    )
    assert response.status_code == status.HTTP_200_OK, f"{response.json()=}"

    invitation = ApiInvitationContentAndLink(**response.json())
    assert invitation.issuer == invitation_input.issuer
    assert invitation.guest == invitation_input.guest
    assert invitation.trial_account_days == invitation_input.trial_account_days

    assert invitation.product
    if invitation_input.product:
        assert invitation.product == invitation_input.product


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
    invitation_url = ApiInvitationContentAndLink.model_validate(
        response.json()
    ).invitation_url

    # check invitation_url
    response = client.post(
        f"/{API_VTAG}/invitations:extract",
        json={"invitation_url": f"{invitation_url}"},
        auth=basic_auth,
    )
    assert response.status_code == 200, f"{response.json()=}"

    # decrypted invitation should be identical to request above
    invitation = InvitationContent.model_validate(response.json())
    assert invitation.issuer == invitation_data.issuer
    assert invitation.guest == invitation_data.guest
    assert invitation.trial_account_days == invitation_data.trial_account_days


def test_check_valid_invitation(
    client: TestClient,
    basic_auth: httpx.BasicAuth,
    invitation_data: InvitationInputs,
    secret_key: str,
    default_product: ProductName,
):
    invitation_url, _ = create_invitation_link_and_content(
        invitation_data=invitation_data,
        secret_key=secret_key.encode(),
        base_url=f"{client.base_url}",
        default_product=default_product,
    )

    # check invitation_url
    response = client.post(
        f"/{API_VTAG}/invitations:extract",
        json={"invitation_url": f"{invitation_url}"},
        auth=basic_auth,
    )
    assert response.status_code == 200, f"{response.json()=}"

    # decrypted invitation should be identical to request above
    invitation = InvitationContent.model_validate(response.json())

    assert invitation.issuer == invitation_data.issuer
    assert invitation.guest == invitation_data.guest
    assert invitation.trial_account_days == invitation_data.trial_account_days


def test_check_invalid_invitation_with_different_secret(
    client: TestClient,
    basic_auth: httpx.BasicAuth,
    invitation_data: InvitationInputs,
    another_secret_key: str,
    default_product: ProductName,
):
    invitation_url, _ = create_invitation_link_and_content(
        invitation_data=invitation_data,
        secret_key=another_secret_key,  # <-- NOTE: DIFFERENT secret
        base_url=f"{client.base_url}",
        default_product=default_product,
    )

    # check invitation_url
    response = client.post(
        f"/{API_VTAG}/invitations:extract",
        json={"invitation_url": f"{invitation_url}"},
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
    default_product: ProductName,
):
    invitation_url, _ = create_invitation_link_and_content(
        invitation_data=invitation_data,
        secret_key=another_secret_key,  # <-- NOTE: DIFFERENT secret
        base_url=f"{client.base_url}",
        default_product=default_product,
    )

    invitation_url_with_invalid_code = f"{invitation_url}"[:-3]

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
