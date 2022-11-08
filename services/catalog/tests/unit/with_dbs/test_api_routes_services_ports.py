# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import urllib.parse
from typing import Any, Callable

import pytest
from pytest_mock.plugin import MockerFixture
from respx.router import MockRouter
from starlette import status
from starlette.testclient import TestClient
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def disable_service_caching(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AIOCACHE_DISABLE", "1")


@pytest.fixture
def product_name(
    products_names: list[str],
) -> str:
    target_product = products_names[-1]
    assert target_product
    return target_product


@pytest.fixture
def service_key() -> str:
    return "simcore/services/comp/itis/fake_sleeper"


@pytest.fixture
def service_version() -> str:
    return "1.2.3"


@pytest.fixture
def service_metadata(
    service_key: str,
    service_version: str,
    service_metadata_faker: Callable,
) -> dict[str, Any]:
    return service_metadata_faker(key=service_key, version=service_version)


@pytest.fixture
async def mock_check_service_read_access(
    mocker: MockerFixture, user_groups_ids: dict[str, Any]
):
    # MOCKS functionality inside "simcore_service_catalog.api.dependencies.services.check_service_read_access"
    # to provide read access to a service to user_groups_ids
    #
    print(user_groups_ids)

    mocker.patch(
        "simcore_service_catalog.api.dependencies.services.ServicesRepository.get_service",
        autospec=True,
        return_value=True,
    )


@pytest.fixture
async def mock_director_service_api(
    director_mockup: MockRouter,
    service_key: str,
    service_version: str,
    service_metadata: dict[str, Any],
):
    # SEE services/director/src/simcore_service_director/api/v0/openapi.yaml
    director_mockup.get(
        f"/services/{urllib.parse.quote_plus(service_key)}/{service_version}",
        name="services_by_key_version_get",
    ).respond(
        status.HTTP_200_OK,
        json={
            "data": [
                service_metadata,
            ],
        },
    )


async def test_list_service_ports(
    disable_service_caching: None,
    mock_catalog_background_task: None,
    mock_check_service_read_access: None,
    mock_director_service_api: None,
    client: TestClient,
    product_name: str,
    user_id: int,
    service_key: str,
    service_version: str,
    service_metadata: dict[str, Any],  # expected
    benchmark,
):
    url = URL(f"/v0/services/{service_key}/{service_version}/ports").with_query(
        {"user_id": user_id}
    )
    response = benchmark(
        client.get, f"{url}", headers={"x-simcore-products-name": product_name}
    )
    assert response.status_code == 200
    ports = response.json()

    # same order and name identifier
    expected_inputs = service_metadata["inputs"]
    expected_outputs = service_metadata["outputs"]

    assert [p["key"] for p in ports if p["kind"] == "input"] == list(
        expected_inputs.keys()
    )
    assert [p["key"] for p in ports if p["kind"] == "output"] == list(
        expected_outputs.keys()
    )

    assert ports == [
        {
            "key": "input_1",
            "kind": "input",
            "content_media_type": "text/plain",
            "content_schema": {
                "type": "string",
                "title": "File with int number",
                "description": "Pick a file containing only one integer",
            },
        },
        {
            "key": "input_2",
            "kind": "input",
            "content_schema": {
                "title": "Sleep interval",
                "type": "integer",
                "x_unit": "second",
                "minimum": 0,
                "maximum": 5,
            },
        },
        {
            "key": "input_3",
            "kind": "input",
            "content_schema": {
                "title": "Fail after sleep",
                "type": "boolean",
                "description": "If set to true will cause service to fail after it sleeps",
                "default": False,
            },
        },
        {
            "key": "input_4",
            "kind": "input",
            "content_schema": {
                "title": "Distance to bed",
                "type": "integer",
                "x_unit": "meter",
            },
        },
        {
            "key": "output_1",
            "kind": "output",
            "content_media_type": "text/plain",
            "content_schema": {
                "type": "string",
                "title": "File containing one random integer",
                "description": "Integer is generated in range [1-9]",
            },
        },
        {
            "key": "output_2",
            "kind": "output",
            "content_schema": {
                "title": "Random sleep interval",
                "type": "integer",
                "x_unit": "second",
            },
        },
    ]
