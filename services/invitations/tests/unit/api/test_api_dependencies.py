# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Optional

import httpx
from fastapi import status
from fastapi.testclient import TestClient
from simcore_service_invitations._meta import API_VTAG
from simcore_service_invitations.invitations import InvitationInputs


def test_invalid_http_basic_auth(
    client: TestClient,
    invalid_basic_auth: Optional[httpx.BasicAuth],
    invitation_data: InvitationInputs,
):
    response = client.post(
        f"/{API_VTAG}/invitations",
        json=invitation_data.dict(),
        auth=invalid_basic_auth,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"{response.json()=}"
