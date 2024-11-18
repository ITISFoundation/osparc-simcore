# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import httpx
from fastapi import status
from fastapi.testclient import TestClient
from simcore_service_invitations._meta import API_VTAG
from simcore_service_invitations.services.invitations import InvitationInputs


def test_invalid_http_basic_auth(
    client: TestClient,
    invalid_basic_auth: httpx.BasicAuth | None,
    invitation_data: InvitationInputs,
):
    response = client.post(
        f"/{API_VTAG}/invitations",
        json=invitation_data.model_dump(),
        auth=invalid_basic_auth,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"{response.json()=}"
