# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.utils.fastapi_encoders import jsonable_encoder
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from simcore_service_webserver.invitations._client import InvitationContent
from simcore_service_webserver.invitations.settings import (
    InvitationsSettings,
    get_plugin_settings,
)
from yarl import URL


@pytest.fixture
def app_invitations_plugin_settings(client: TestClient) -> InvitationsSettings:
    assert client.app
    settings = get_plugin_settings(app=client.app)
    assert settings
    return settings


@pytest.fixture(scope="module")
def invitations_service_openapi_specs(
    osparc_simcore_services_dir: Path,
) -> dict[str, Any]:
    oas_path = osparc_simcore_services_dir / "invitations" / "openapi.json"
    return json.loads(oas_path.read_text())


@pytest.fixture
def expected_invitation(
    invitations_service_openapi_specs: dict[str, Any]
) -> InvitationContent:
    oas = deepcopy(invitations_service_openapi_specs)
    return InvitationContent.parse_obj(
        oas["components"]["schemas"]["_ApiInvitationContent"]["example"]
    )


@pytest.fixture()
def base_url(app_invitations_plugin_settings: InvitationsSettings) -> URL:
    return URL(app_invitations_plugin_settings.base_url)


@pytest.fixture
def mock_invitations_service_http_api(
    aioresponses_mocker: AioResponsesMock,
    invitations_service_openapi_specs: dict[str, Any],
    base_url: URL,
    expected_invitation: InvitationContent,
) -> AioResponsesMock:
    oas = deepcopy(invitations_service_openapi_specs)

    # healthcheck
    assert "/" in oas["paths"]
    aioresponses_mocker.get(
        f"{base_url}/",
        status=web.HTTPOk.status_code,
        repeat=False,  # NOTE: this is only usable once!
    )

    # meta
    assert "/v1/meta" in oas["paths"]
    aioresponses_mocker.get(
        f"{base_url}/v1/meta",
        status=web.HTTPOk.status_code,
        payload={"name": "string", "version": "string", "docs_url": "string"},
    )

    # extract
    assert "/v1/invitations:extract" in oas["paths"]
    aioresponses_mocker.post(
        f"{base_url}/v1/invitations:extract",
        status=web.HTTPOk.status_code,
        payload=jsonable_encoder(expected_invitation.dict()),
    )

    return aioresponses_mocker
