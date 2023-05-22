# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any

import httpx
from fastapi import status
from respx import MockRouter
from simcore_service_api_server.models.schemas.studies import StudyID


async def test_list_study_ports(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    mocked_webserver_service_api: MockRouter,
    fake_study_ports: list[dict[str, Any]],
    study_id: StudyID,
):
    # list_study_ports
    resp = await client.get(f"/v0/studies/{study_id}/ports", auth=auth)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == fake_study_ports
