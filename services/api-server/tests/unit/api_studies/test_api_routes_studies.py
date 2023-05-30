# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any

import httpx
import pytest
from fastapi import status
from pydantic import parse_obj_as
from respx import MockRouter
from simcore_service_api_server.models.schemas.studies import Study, StudyID


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


@pytest.mark.xfail(reason="Still not implemented")
@pytest.mark.acceptance_test(
    "Implements https://github.com/ITISFoundation/osparc-simcore/issues/4177"
)
async def test_studies_workflow(
    client: httpx.AsyncClient,
    auth: httpx.BasicAuth,
    mocked_webserver_service_api: MockRouter,
    study_id: StudyID,
):

    # list_studies
    resp = await client.get("/v0/studies", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    studies = parse_obj_as(list[Study], resp.json())
    assert len(studies) == 1
    assert studies[0].uid == study_id

    # create_study doest NOT exist -> needs to be done via GUI
    resp = await client.post("/v0/studies", auth=auth)
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    # get_study
    resp = await client.get(f"/v0/studies/{study_id}", auth=auth)
    assert resp.status_code == status.HTTP_200_OK

    study = parse_obj_as(Study, resp.json())
    assert study.uid == study_id
