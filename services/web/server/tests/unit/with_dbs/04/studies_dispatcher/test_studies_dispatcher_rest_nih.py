# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aiohttp.test_utils import TestClient, TestServer
from common_library.json_serialization import json_dumps
from common_library.serialization import model_dump_with_secrets
from pydantic import TypeAdapter
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp import status
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_service_webserver.studies_dispatcher._controller.rest.nih_schemas import (
    ServiceGet,
)
from yarl import URL

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    rabbit_service: RabbitSettings,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_RABBITMQ": json_dumps(
                model_dump_with_secrets(rabbit_service, show_secrets=True)
            )
        },
    )


@pytest.fixture
def web_server(
    redis_service: RedisSettings,
    rabbit_service: RabbitSettings,
    web_server: TestServer,
    # Add dependencies to ensure database is populated before app starts
    services_metadata_in_db: list[dict],
    services_consume_filetypes_in_db: list[dict],
    services_access_rights_in_db: list[dict],
) -> TestServer:
    #
    # Extends web_server to start redis_service and ensure DB is populated
    #
    print(
        "Redis service started with settings: ", redis_service.model_dump_json(indent=1)
    )
    return web_server


def _get_base_url(client: TestClient) -> str:
    s = client.server
    assert isinstance(s.scheme, str)
    url = URL.build(scheme=s.scheme, host=s.host, port=s.port)
    return f"{url}"


async def test_api_get_viewer_for_file(client: TestClient):
    resp = await client.get("/v0/viewers/default?file_type=JPEG")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    base_url = _get_base_url(client)
    assert data == [
        {
            "file_type": "JPEG",
            "title": "Bio-formats v1.0.1",
            "view_url": f"{base_url}/view?file_type=JPEG&viewer_key=simcore/services/dynamic/bio-formats-web&viewer_version=1.0.1",
        },
    ]


async def test_api_get_viewer_for_unsupported_type(client: TestClient):
    resp = await client.get("/v0/viewers/default?file_type=UNSUPPORTED_TYPE")
    data, error = await assert_status(resp, status.HTTP_200_OK)
    assert data == []
    assert error is None


async def test_api_list_supported_filetypes(client: TestClient):
    resp = await client.get("/v0/viewers/default")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    base_url = _get_base_url(client)
    assert data == [
        {
            "title": "Rawgraphs v2.11.1",
            "file_type": "CSV",
            "view_url": f"{base_url}/view?file_type=CSV&viewer_key=simcore/services/dynamic/raw-graphs&viewer_version=2.11.1",
        },
        {
            "file_type": "HORNET_REPO",
            "title": "Hornet flow v3.2.300",
            "view_url": f"{base_url}/view?file_type=HORNET_REPO&viewer_key=simcore/services/dynamic/s4l-ui-modeling&viewer_version=3.2.300",
        },
        {
            "title": "Jupyterlab math v1.6.9",
            "file_type": "IPYNB",
            "view_url": f"{base_url}/view?file_type=IPYNB&viewer_key=simcore/services/dynamic/jupyter-octave-python-math&viewer_version=1.6.9",
        },
        {
            "title": "Bio-formats v1.0.1",
            "file_type": "JPEG",
            "view_url": f"{base_url}/view?file_type=JPEG&viewer_key=simcore/services/dynamic/bio-formats-web&viewer_version=1.0.1",
        },
        {
            "title": "Rawgraphs v2.11.1",
            "file_type": "JSON",
            "view_url": f"{base_url}/view?file_type=JSON&viewer_key=simcore/services/dynamic/raw-graphs&viewer_version=2.11.1",
        },
        {
            "title": "Bio-formats v1.0.1",
            "file_type": "PNG",
            "view_url": f"{base_url}/view?file_type=PNG&viewer_key=simcore/services/dynamic/bio-formats-web&viewer_version=1.0.1",
        },
        {
            "title": "Jupyterlab math v1.6.9",
            "file_type": "PY",
            "view_url": f"{base_url}/view?file_type=PY&viewer_key=simcore/services/dynamic/jupyter-octave-python-math&viewer_version=1.6.9",
        },
        {
            "title": "Rawgraphs v2.11.1",
            "file_type": "TSV",
            "view_url": f"{base_url}/view?file_type=TSV&viewer_key=simcore/services/dynamic/raw-graphs&viewer_version=2.11.1",
        },
        {
            "title": "Rawgraphs v2.11.1",
            "file_type": "XLSX",
            "view_url": f"{base_url}/view?file_type=XLSX&viewer_key=simcore/services/dynamic/raw-graphs&viewer_version=2.11.1",
        },
    ]


async def test_api_list_services(client: TestClient):
    assert client.app

    url = client.app.router["list_latest_services"].url_for()
    response = await client.get(f"{url}")

    data, error = await assert_status(response, status.HTTP_200_OK)

    services = TypeAdapter(list[ServiceGet]).validate_python(data)
    assert services

    # latest versions of services with everyone + ospar-product (see services_access_rights_in_db)
    assert services[0].key == "simcore/services/dynamic/raw-graphs"
    assert services[0].file_extensions == ["CSV", "JSON", "TSV", "XLSX"]

    assert services[0].view_url.query
    assert "2.11.1" in services[0].view_url.query

    assert services[2].key == "simcore/services/dynamic/jupyter-octave-python-math"
    assert services[2].file_extensions == ["IPYNB", "PY"]
    assert services[2].view_url.query
    assert "1.6.9" in services[2].view_url.query

    assert error is None
