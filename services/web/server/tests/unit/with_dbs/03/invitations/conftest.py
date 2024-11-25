# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import binascii
import json
from contextlib import suppress
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from aioresponses import CallbackResult
from faker import Faker
from models_library.api_schemas_invitations.invitations import (
    ApiInvitationContent,
    ApiInvitationContentAndLink,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.aiohttp import status
from simcore_service_webserver.application_settings import ApplicationSettings
from simcore_service_webserver.invitations.settings import (
    InvitationsSettings,
    get_plugin_settings,
)
from simcore_service_webserver.products.api import Product, list_products
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
def current_product(client: TestClient) -> Product:
    assert client.app
    products = list_products(client.app)
    assert products
    assert products[0].name == "osparc"
    return products[0]


@pytest.fixture
def fake_osparc_invitation(
    invitations_service_openapi_specs: dict[str, Any]
) -> ApiInvitationContent:
    """
    Emulates an invitation for osparc product
    """
    oas = deepcopy(invitations_service_openapi_specs)
    content = ApiInvitationContent.model_validate(
        oas["components"]["schemas"]["ApiInvitationContent"]["example"]
    )
    content.product = "osparc"
    return content


@pytest.fixture
def guest_email(faker: Faker) -> str:
    return faker.email()


@pytest.fixture
def guest_password() -> str:
    return "secret" * 3


@pytest.fixture()
def base_url(app_invitations_plugin_settings: InvitationsSettings) -> URL:
    return URL(app_invitations_plugin_settings.base_url)


@pytest.fixture
def mock_invitations_service_http_api(
    aioresponses_mocker: AioResponsesMock,
    invitations_service_openapi_specs: dict[str, Any],
    base_url: URL,
    fake_osparc_invitation: ApiInvitationContent,
) -> AioResponsesMock:
    oas = deepcopy(invitations_service_openapi_specs)

    # healthcheck
    assert "/" in oas["paths"]
    aioresponses_mocker.get(
        f"{base_url}/",
        status=status.HTTP_200_OK,
        repeat=False,  # NOTE: this is only usable once!
    )

    # meta
    assert "/v1/meta" in oas["paths"]
    aioresponses_mocker.get(
        f"{base_url}/v1/meta",
        status=status.HTTP_200_OK,
        payload={"name": "string", "version": "string", "docs_url": "string"},
    )

    # extract
    assert "/v1/invitations:extract" in oas["paths"]

    def _extract(url, **kwargs):
        fake_code = URL(URL(f'{kwargs["json"]["invitation_url"]}').fragment).query[
            "invitation"
        ]
        # if nothing is encoded in fake_code, just return fake_osparc_invitation
        body = fake_osparc_invitation.model_dump()
        with suppress(Exception):
            decoded = json.loads(binascii.unhexlify(fake_code).decode())
            body.update(decoded)

        return CallbackResult(
            status=status.HTTP_200_OK,
            payload=jsonable_encoder(body),
        )

    aioresponses_mocker.post(
        f"{base_url}/v1/invitations:extract",
        callback=_extract,
        repeat=True,  # NOTE: this can be used many times
    )

    # generate
    assert "/v1/invitations" in oas["paths"]
    example = oas["components"]["schemas"]["ApiInvitationContentAndLink"]["example"]

    def _generate(url, **kwargs):
        body = kwargs["json"]
        if not body.get("product"):
            body["product"] = example["product"]

        fake_code = binascii.hexlify(json.dumps(body).encode()).decode()
        return CallbackResult(
            status=status.HTTP_200_OK,
            payload=jsonable_encoder(
                ApiInvitationContentAndLink.model_validate(
                    {
                        **example,
                        **body,
                        "invitation_url": f"https://osparc-simcore.test/#/registration?invitation={fake_code}",
                        "created": datetime.now(tz=timezone.utc),
                    }
                )
            ),
        )

    aioresponses_mocker.post(
        f"{base_url}/v1/invitations",
        callback=_generate,
        repeat=True,  # NOTE: this can be used many times
    )

    return aioresponses_mocker


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    env_devel_dict: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
):
    # ensures WEBSERVER_INVITATIONS is undefined
    monkeypatch.delenv("WEBSERVER_INVITATIONS", raising=False)
    app_environment.pop("WEBSERVER_INVITATIONS", None)

    # new envs
    envs = setenvs_from_dict(
        monkeypatch,
        {
            # as before
            **app_environment,
            # disable these plugins
            "WEBSERVER_ACTIVITY": "null",
            "WEBSERVER_DB_LISTENER": "0",
            "WEBSERVER_DIAGNOSTICS": "null",
            "WEBSERVER_EXPORTER": "null",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_META_MODELING": "0",
            "WEBSERVER_NOTIFICATIONS": "0",
            "WEBSERVER_PUBLICATIONS": "0",
            "WEBSERVER_REMOTE_DEBUG": "0",
            "WEBSERVER_SOCKETIO": "0",
            "WEBSERVER_STUDIES_ACCESS_ENABLED": "0",
            "WEBSERVER_TAGS": "0",
            "WEBSERVER_TRACING": "null",
            "WEBSERVER_VERSION_CONTROL": "0",
            "WEBSERVER_WALLETS": "0",
            # set INVITATIONS_* variables using those in .env-devel
            **{
                key: value
                for key, value in env_devel_dict.items()
                if key.startswith("INVITATIONS_")
            },
        },
    )

    # tests envs
    print(ApplicationSettings.create_from_envs().model_dump_json(indent=2))
    return envs
