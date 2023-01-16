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
from pytest import MonkeyPatch
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_webserver.invitations import (
    InvitationServiceUnavailable,
    validate_invitation_url,
)
from simcore_service_webserver.invitations_client import (
    InvitationsServiceApi,
    get_invitations_service_api,
)
from simcore_service_webserver.invitations_settings import (
    InvitationsSettings,
    get_plugin_settings,
)
from yarl import URL


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: MonkeyPatch):
    plugin_settings = InvitationsSettings.create_from_envs()
    print("InvitationsSettings=", plugin_settings.json(indent=1))
    return app_environment


@pytest.fixture
def app_invitation_plugin_settings(client: TestClient) -> InvitationsSettings:
    settings = get_plugin_settings(app=client.app)
    assert settings
    return settings


@pytest.fixture(scope="module")
def invitations_service_openapi_specs(
    osparc_simcore_services_dir: Path,
) -> dict[str, Any]:
    oas_path = osparc_simcore_services_dir / "invitations" / "openapi.json"
    openapi_specs = json.loads(oas_path.read_text())
    return openapi_specs


@pytest.fixture
def mock_invitations_service_http_api(
    aioresponses_mocker: AioResponsesMock,
    invitations_service_openapi_specs: dict[str, Any],
    app_invitation_plugin_settings: InvitationsSettings,
) -> AioResponsesMock:
    oas = deepcopy(invitations_service_openapi_specs)
    base_url = URL(app_invitation_plugin_settings.base_url)

    # healthcheck
    assert "/" in oas["paths"]
    aioresponses_mocker.get(
        f"{base_url}/",
        status=web.HTTPOk.status_code,
    )

    # meta
    assert "/v1/meta" in oas["paths"]
    aioresponses_mocker.get(
        f"{base_url}/v1/meta",
        status=web.HTTPOk.status_code,
        payload={"name": "string", "version": "string", "docs_url": "string"},
        repeat=True,
    )

    # extract
    assert "/v1/invitations:extract" in oas["paths"]
    aioresponses_mocker.post(
        f"{base_url}/v1/invitations:extract",
        status=web.HTTPOk.status_code,
        payload=oas["components"]["schemas"]["_ApiInvitationContent"]["example"],
        repeat=True,
    )

    return aioresponses_mocker


async def test_invitation_service_unavailable(client: TestClient):

    invitations_api: InvitationsServiceApi = get_invitations_service_api(app=client.app)

    assert not await invitations_api.ping()

    with pytest.raises(InvitationServiceUnavailable):
        await validate_invitation_url(
            app=client.app, invitation_url="https://osparc.io#register?invitation=1234"
        )


async def test_invitation_service_api_ping(
    client: TestClient, mock_invitations_service_http_api: AioResponsesMock
):
    invitations_api: InvitationsServiceApi = get_invitations_service_api(app=client.app)

    print(mock_invitations_service_http_api)

    assert await invitations_api.ping()

    invitation = await validate_invitation_url(
        app=client.app, invitation_url="https://osparc.io#register?invitation=1234"
    )
    assert invitation


# create fake invitation service

# valid invitation

# invalid invitation

# confirmation-type of invitations
