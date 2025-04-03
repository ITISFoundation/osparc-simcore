# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import httpx
import pytest
from fastapi import FastAPI, status
from respx import MockRouter
from simcore_service_api_server.core.settings import ApplicationSettings


def test_mocked_webserver_service_api(
    app: FastAPI,
    mocked_webserver_rest_api_base: MockRouter,
    services_mocks_enabled: bool,
):
    if not services_mocks_enabled:
        pytest.skip(f"{services_mocks_enabled=}")

    #
    # This test intends to help building the urls in mocked_webserver_service_api
    # At some point, it can be skipped and reenabled only for development
    #
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER
    webserver_api_baseurl = settings.API_SERVER_WEBSERVER.api_base_url

    resp = httpx.get(f"{webserver_api_baseurl}/")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()

    resp = httpx.get(f"{webserver_api_baseurl}/health")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()

    mocked_webserver_rest_api_base.assert_all_called()
