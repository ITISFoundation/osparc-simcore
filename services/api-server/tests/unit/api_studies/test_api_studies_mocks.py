# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any

import httpx
from fastapi import FastAPI, status
from respx import MockRouter
from simcore_service_api_server.core.settings import ApplicationSettings
from simcore_service_api_server.models.schemas.studies import StudyID


def test_mocked_webserver_service_api(
    app: FastAPI,
    mocked_webserver_service_api: MockRouter,
    study_id: StudyID,
    fake_study_ports: list[dict[str, Any]],
):
    #
    # This test intends to help building the urls in mocked_webserver_service_api
    # At some point, it can be skipped and reenabled only for development
    #
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER
    webserver_api_baseurl = settings.API_SERVER_WEBSERVER.api_base_url

    resp = httpx.get(f"{webserver_api_baseurl}/health")
    assert resp.status_code == status.HTTP_200_OK

    # Sometimes is difficult to adjust respx.Mock
    resp = httpx.get(f"{webserver_api_baseurl}/projects/{study_id}/metadata/ports")
    assert resp.status_code == status.HTTP_200_OK

    payload = resp.json()
    assert payload.get("error") is None
    assert payload.get("data") == fake_study_ports

    mocked_webserver_service_api.assert_all_called()
