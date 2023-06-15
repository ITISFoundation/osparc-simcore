# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

import aiohttp.test_utils
import httpx
import pytest
import respx
import yaml
from asgi_lifespan import LifespanManager
from cryptography.fernet import Fernet
from faker import Faker
from fastapi import FastAPI, status
from httpx._transports.asgi import ASGITransport
from moto.server import ThreadedMotoServer
from pydantic import HttpUrl, parse_obj_as
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_docker import get_localhost_ip
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from requests.auth import HTTPBasicAuth
from respx import MockRouter
from simcore_service_api_server.core.application import init_app
from simcore_service_api_server.core.settings import ApplicationSettings

## APP + SYNC/ASYNC CLIENTS --------------------------------------------------


@pytest.fixture
def app_environment(
    monkeypatch: MonkeyPatch, default_app_env_vars: EnvVarsDict
) -> EnvVarsDict:
    """Config that disables many plugins e.g. database or tracing"""

    env_vars = setenvs_from_dict(
        monkeypatch,
        {
            **default_app_env_vars,
            "WEBSERVER_HOST": "webserver",
            "WEBSERVER_SESSION_SECRET_KEY": Fernet.generate_key().decode("utf-8"),
            "API_SERVER_POSTGRES": "null",
            "LOG_LEVEL": "debug",
            "SC_BOOT_MODE": "production",
        },
    )

    # should be sufficient to create settings
    print(ApplicationSettings.create_from_envs().json(indent=1))

    return env_vars


@pytest.fixture
def app(app_environment: EnvVarsDict) -> FastAPI:
    """Inits app on a light environment"""
    the_app = init_app()
    return the_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    #
    # Prefer this client instead of fastapi.testclient.TestClient
    #
    async with LifespanManager(app):
        # needed for app to trigger start/stop event handlers
        async with httpx.AsyncClient(
            app=app,
            base_url="http://api.testserver.io",
            headers={"Content-Type": "application/json"},
        ) as client:
            assert isinstance(client._transport, ASGITransport)
            # rewires location test's app to client.app
            setattr(client, "app", client._transport.app)

            yield client


## MOCKED Repositories --------------------------------------------------


@pytest.fixture
def auth(mocker, app: FastAPI, faker: Faker) -> HTTPBasicAuth:
    """
    Auth mocking repositories and db engine (i.e. does not require db up)

    """
    # mock engine if db was not init
    if app.state.settings.API_SERVER_POSTGRES is None:
        engine = mocker.MagicMock()
        engine.minsize = 1
        engine.size = 10
        engine.freesize = 3
        engine.maxsize = 10
        app.state.engine = engine

    # patch authentication entry in repo
    faker_user_id = faker.pyint()

    # NOTE: here, instead of using the database, we patch repositories interface
    mocker.patch(
        "simcore_service_api_server.db.repositories.api_keys.ApiKeysRepository.get_user_id",
        autospec=True,
        return_value=faker_user_id,
    )
    mocker.patch(
        "simcore_service_api_server.db.repositories.users.UsersRepository.get_user_id",
        autospec=True,
        return_value=faker_user_id,
    )
    mocker.patch(
        "simcore_service_api_server.db.repositories.users.UsersRepository.get_email_from_user_id",
        autospec=True,
        return_value=faker.email(),
    )

    # patches simcore_postgres_database.utils_products.get_default_product_name
    mocker.patch(
        "simcore_service_api_server.api.dependencies.application.get_default_product_name",
        autospec=True,
        return_value="osparc",
    )

    return HTTPBasicAuth(faker.word(), faker.password())


## MOCKED S3 service --------------------------------------------------


@pytest.fixture
def mocked_s3_server_url() -> Iterator[HttpUrl]:
    """
    For download links, the in-memory moto.mock_s3() does not suffice since
    we need an http entrypoint
    """
    # http://docs.getmoto.org/en/latest/docs/server_mode.html#start-within-python
    server = ThreadedMotoServer(
        ip_address=get_localhost_ip(), port=aiohttp.test_utils.unused_port()
    )

    # pylint: disable=protected-access
    endpoint_url = parse_obj_as(HttpUrl, f"http://{server._ip_address}:{server._port}")

    print(f"--> started mock S3 server on {endpoint_url}")
    server.start()

    yield endpoint_url

    server.stop()
    print(f"<-- stopped mock S3 server on {endpoint_url}")


## MOCKED stack services --------------------------------------------------


@pytest.fixture
def directorv2_service_openapi_specs(
    osparc_simcore_services_dir: Path,
) -> dict[str, Any]:
    return json.loads(
        (osparc_simcore_services_dir / "director-v2" / "openapi.json").read_text()
    )


@pytest.fixture
def webserver_service_openapi_specs(
    osparc_simcore_services_dir: Path,
) -> dict[str, Any]:
    return yaml.safe_load(
        (
            osparc_simcore_services_dir
            / "web/server/src/simcore_service_webserver/api/v0/openapi.yaml"
        ).read_text()
    )


@pytest.fixture
def mocked_webserver_service_api_base(
    app: FastAPI, webserver_service_openapi_specs: dict[str, Any], faker: Faker
) -> Iterator[MockRouter]:
    """
    Creates a respx.mock to capture calls to webserver API
    Includes only basic routes to check that the configuration is correct
    IMPORTANT: This fixture shall be extended on a test bases
    """
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER

    openapi = deepcopy(webserver_service_openapi_specs)

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_WEBSERVER.api_base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        # include /v0
        assert settings.API_SERVER_WEBSERVER.api_base_url.endswith("/v0")

        # healthcheck_readiness_probe, healthcheck_liveness_probe
        response_body = {
            "data": openapi["paths"]["/"]["get"]["responses"]["200"]["content"][
                "application/json"
            ]["schema"]["properties"]["data"]["example"]
        }

        respx_mock.get(path="/v0/", name="healthcheck_readiness_probe").respond(
            status.HTTP_200_OK, json=response_body
        )
        respx_mock.get(path="/v0/health", name="healthcheck_liveness_probe").respond(
            status.HTTP_200_OK, json=response_body
        )

        yield respx_mock


@pytest.fixture
def catalog_service_openapi_specs(osparc_simcore_services_dir: Path) -> dict[str, Any]:
    openapi_path = osparc_simcore_services_dir / "catalog" / "openapi.json"
    openapi_specs = json.loads(openapi_path.read_text())
    return openapi_specs


@pytest.fixture
def mocked_catalog_service_api_base(
    app: FastAPI, catalog_service_openapi_specs: dict[str, Any]
) -> Iterator[MockRouter]:
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_CATALOG

    openapi = deepcopy(catalog_service_openapi_specs)
    schemas = openapi["components"]["schemas"]

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_CATALOG.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.get("/v0/meta").respond(200, json=schemas["Meta"]["example"])

        yield respx_mock
