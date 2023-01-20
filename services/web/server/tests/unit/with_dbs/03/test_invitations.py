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
from pytest import MonkeyPatch
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_login import NewUser
from simcore_service_webserver.application_settings import ApplicationSettings
from simcore_service_webserver.invitations import (
    InvalidInvitation,
    InvitationsServiceUnavailable,
    validate_invitation_url,
)
from simcore_service_webserver.invitations_client import (
    InvitationContent,
    InvitationsServiceApi,
    get_invitations_service_api,
)
from simcore_service_webserver.invitations_settings import (
    InvitationsSettings,
    get_plugin_settings,
)
from yarl import URL


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, env_devel_dict: EnvVarsDict, monkeypatch: MonkeyPatch
):

    envs_plugins = setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_ACTIVITY": "null",
            "WEBSERVER_CLUSTERS": "null",
            "WEBSERVER_COMPUTATION": "null",
            "WEBSERVER_DIAGNOSTICS": "null",
            "WEBSERVER_DIRECTOR": "null",
            "WEBSERVER_EXPORTER": "null",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_META_MODELING": "null",
            "WEBSERVER_PUBLICATIONS": "0",
            "WEBSERVER_REMOTE_DEBUG": "0",
            "WEBSERVER_SOCKETIO": "0",
            "WEBSERVER_STUDIES_ACCESS_ENABLED": "0",
            "WEBSERVER_TAGS": "0",
            "WEBSERVER_TRACING": "null",
            "WEBSERVER_VERSION_CONTROL": "0",
        },
    )

    # undefine WEBSERVER_INVITATIONS
    app_environment.pop("WEBSERVER_INVITATIONS", None)
    monkeypatch.delenv("WEBSERVER_INVITATIONS", raising=False)

    # set INVITATIONS_* variables using those in .devel-env
    envs_invitations = setenvs_from_dict(
        monkeypatch,
        envs={
            name: value
            for name, value in env_devel_dict.items()
            if name.startswith("INVITATIONS_")
        },
    )

    print(ApplicationSettings.create_from_envs().json(indent=2))
    return app_environment | envs_plugins | envs_invitations


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
def expected_invitation(
    invitations_service_openapi_specs: dict[str, Any]
) -> InvitationContent:
    oas = deepcopy(invitations_service_openapi_specs)
    return InvitationContent.parse_obj(
        oas["components"]["schemas"]["_ApiInvitationContent"]["example"]
    )


@pytest.fixture
def mock_invitations_service_http_api(
    aioresponses_mocker: AioResponsesMock,
    invitations_service_openapi_specs: dict[str, Any],
    app_invitation_plugin_settings: InvitationsSettings,
    expected_invitation: InvitationContent,
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
        payload=jsonable_encoder(expected_invitation.dict()),
        repeat=True,
    )

    return aioresponses_mocker


async def test_invitation_service_unavailable(client: TestClient):

    invitations_api: InvitationsServiceApi = get_invitations_service_api(app=client.app)

    assert not await invitations_api.ping()

    with pytest.raises(InvitationsServiceUnavailable):
        await validate_invitation_url(
            app=client.app,
            invitation_url="https://server.com#/registration?invitation=1234",
        )


async def test_invitation_service_api_ping(
    client: TestClient, mock_invitations_service_http_api: AioResponsesMock
):
    invitations_api: InvitationsServiceApi = get_invitations_service_api(app=client.app)

    print(mock_invitations_service_http_api)

    assert await invitations_api.ping()
    assert await invitations_api.is_responsive()


async def test_valid_invitation(
    client: TestClient,
    mock_invitations_service_http_api: AioResponsesMock,
    expected_invitation: InvitationContent,
):
    invitation = await validate_invitation_url(
        app=client.app, invitation_url="https://server.com#register?invitation=1234"
    )
    assert invitation
    assert invitation == expected_invitation


async def test_invalid_invitation_if_already_registered(
    client: TestClient,
    mock_invitations_service_http_api: AioResponsesMock,
    expected_invitation: InvitationContent,
):

    async with NewUser(
        params={
            "name": "test-user",
            "email": expected_invitation.guest,
        },
        app=client.app,
    ) as registered_user:

        with pytest.raises(InvalidInvitation):
            await validate_invitation_url(
                app=client.app,
                invitation_url="https://server.com#register?invitation=1234",
            )


# create fake invitation service

# valid invitation

# invalid invitation

# confirmation-type of invitations
