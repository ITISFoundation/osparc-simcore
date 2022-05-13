# pylint: disable=no-value-for-parameter
# pylint: disable=not-an-iterable
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
import urllib.parse
from random import choice, randint
from typing import Any, Callable, Dict, List

import httpx
import pytest
import respx
from faker import Faker
from fastapi import FastAPI
from models_library.services import ServiceDockerData
from models_library.services_resources import (
    ResourcesDict,
    ResourceValue,
    ServiceResources,
)
from pydantic import ByteSize
from respx.models import Route
from respx.router import MockRouter
from simcore_service_catalog.core.settings import _DEFAULT_RESOURCES
from starlette.testclient import TestClient
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_list_services_with_details(
    mock_catalog_background_task,
    director_mockup: MockRouter,
    client: TestClient,
    user_id: int,
    products_names: List[str],
    service_catalog_faker: Callable,
    services_db_tables_injector: Callable,
    benchmark,
):
    target_product = products_names[-1]
    # create some fake services
    NUM_SERVICES = 1000
    fake_services = [
        service_catalog_faker(
            "simcore/services/dynamic/jupyterlab",
            f"1.0.{s}",
            team_access=None,
            everyone_access=None,
            product=target_product,
        )
        for s in range(NUM_SERVICES)
    ]
    # injects fake data in db
    await services_db_tables_injector(fake_services)

    url = URL("/v0/services").with_query({"user_id": user_id, "details": "true"})

    # now fake the director such that it returns half the services
    fake_registry_service_data = ServiceDockerData.Config.schema_extra["examples"][0]

    director_mockup.get("/services", name="list_services").respond(
        200,
        json={
            "data": [
                {
                    **fake_registry_service_data,
                    **{"key": s[0]["key"], "version": s[0]["version"]},
                }
                for s in fake_services[::2]
            ]
        },
    )

    response = benchmark(
        client.get, f"{url}", headers={"x-simcore-products-name": target_product}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == round(NUM_SERVICES / 2)


async def test_list_services_without_details(
    mock_catalog_background_task,
    director_mockup: MockRouter,
    client: TestClient,
    user_id: int,
    products_names: List[str],
    service_catalog_faker: Callable,
    services_db_tables_injector: Callable,
    benchmark,
):
    target_product = products_names[-1]
    # injects fake data in db
    NUM_SERVICES = 1000
    SERVICE_KEY = "simcore/services/dynamic/jupyterlab"
    await services_db_tables_injector(
        [
            service_catalog_faker(
                SERVICE_KEY,
                f"1.0.{s}",
                team_access=None,
                everyone_access=None,
                product=target_product,
            )
            for s in range(NUM_SERVICES)
        ]
    )

    url = URL("/v0/services").with_query({"user_id": user_id, "details": "false"})
    response = benchmark(
        client.get, f"{url}", headers={"x-simcore-products-name": target_product}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == NUM_SERVICES
    for service in data:
        assert service["key"] == SERVICE_KEY
        assert re.match("1.0.[0-9]+", service["version"]) is not None
        assert service["name"] == "nodetails"
        assert service["description"] == "nodetails"
        assert service["contact"] == "nodetails@nodetails.com"


async def test_list_services_without_details_with_wrong_user_id_returns_403(
    mock_catalog_background_task,
    director_mockup: MockRouter,
    client: TestClient,
    user_id: int,
    products_names: List[str],
    service_catalog_faker: Callable,
    services_db_tables_injector: Callable,
):
    target_product = products_names[-1]
    # injects fake data in db
    NUM_SERVICES = 1
    await services_db_tables_injector(
        [
            service_catalog_faker(
                "simcore/services/dynamic/jupyterlab",
                f"1.0.{s}",
                team_access=None,
                everyone_access=None,
                product=target_product,
            )
            for s in range(NUM_SERVICES)
        ]
    )

    url = URL("/v0/services").with_query({"user_id": user_id + 1, "details": "false"})
    response = client.get(f"{url}", headers={"x-simcore-products-name": target_product})
    assert response.status_code == 403


async def test_list_services_without_details_with_another_product_returns_other_services(
    mock_catalog_background_task,
    director_mockup: MockRouter,
    client: TestClient,
    user_id: int,
    products_names: List[str],
    service_catalog_faker: Callable,
    services_db_tables_injector: Callable,
):
    target_product = products_names[-1]
    assert (
        len(products_names) > 1
    ), "please adjust the fixture to have the right number of products"
    # injects fake data in db
    NUM_SERVICES = 15
    await services_db_tables_injector(
        [
            service_catalog_faker(
                "simcore/services/dynamic/jupyterlab",
                f"1.0.{s}",
                team_access=None,
                everyone_access=None,
                product=target_product,
            )
            for s in range(NUM_SERVICES)
        ]
    )

    url = URL("/v0/services").with_query({"user_id": user_id, "details": "false"})
    response = client.get(
        f"{url}", headers={"x-simcore-products-name": products_names[0]}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


async def test_list_services_without_details_with_wrong_product_returns_0_service(
    mock_catalog_background_task,
    director_mockup: MockRouter,
    client: TestClient,
    user_id: int,
    products_names: List[str],
    service_catalog_faker: Callable,
    services_db_tables_injector: Callable,
):
    target_product = products_names[-1]
    assert (
        len(products_names) > 1
    ), "please adjust the fixture to have the right number of products"
    # injects fake data in db
    NUM_SERVICES = 1
    await services_db_tables_injector(
        [
            service_catalog_faker(
                "simcore/services/dynamic/jupyterlab",
                f"1.0.{s}",
                team_access=None,
                everyone_access=None,
                product=target_product,
            )
            for s in range(NUM_SERVICES)
        ]
    )

    url = URL("/v0/services").with_query({"user_id": user_id, "details": "false"})
    response = client.get(
        f"{url}", headers={"x-simcore-products-name": "no valid product"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


# RESOURCES


@pytest.fixture
def service_labels(faker: Faker) -> Callable[..., dict[str, Any]]:
    def creator():
        return {faker.get_label(): faker.text()}

    return creator


@pytest.fixture
def service_key(faker: Faker) -> str:
    return f"simcore/services/{choice(['comp', 'dynamic','frontend'])}/jupyter-math"


@pytest.fixture
def service_version() -> str:
    return f"{randint(0,100)}.{randint(0,100)}.{randint(0,100)}"


@pytest.fixture
def mock_service_labels(faker: Faker) -> Dict[str, Any]:
    return {
        "simcore.service.settings": '[ {"name": "ports", "type": "int", "value": 8888}, {"name": "constraints", "type": "string", "value": ["node.platform.os == linux"]}, {"name": "Resources", "type": "Resources", "value": { "Limits": { "NanoCPUs": 4000000000, "MemoryBytes": 17179869184 } } } ]',
    }


@pytest.fixture
def mock_director_service_labels(
    director_mockup: respx.MockRouter, app: FastAPI
) -> Route:
    slash = urllib.parse.quote_plus("/")
    mock_route = director_mockup.get(
        url__regex=rf"v0/services/simcore{slash}services{slash}(comp|dynamic|frontend)({slash}[\w{slash}-]+)+/[0-9]+.[0-9]+.[0-9]+/labels",
        name="get_service_labels",
    ).respond(200, json={"data": {}})

    return mock_route


@pytest.mark.parametrize(
    "director_labels, expected_resources",
    [
        pytest.param(
            {},
            _DEFAULT_RESOURCES,
            id="nothing_defined_returns_default_resources",
        ),
        pytest.param(
            {
                "simcore.service.settings": '[ {"name": "Resources", "type": "Resources", "value": { "Limits": { "NanoCPUs": 4000000000, "MemoryBytes": 17179869184 } } } ]',
            },
            _DEFAULT_RESOURCES.copy(
                update={
                    "__root__": {
                        "CPU": ResourceValue(
                            limit=4.0,
                            reservation=_DEFAULT_RESOURCES["CPU"].reservation,
                        ),
                        "RAM": ResourceValue(
                            limit=ByteSize(17179869184),
                            reservation=_DEFAULT_RESOURCES["RAM"].reservation,
                        ),
                    },
                }
            ),
            id="only_limits_defined_returns_default_reservations",
        ),
        pytest.param(
            {
                "simcore.service.settings": '[ {"name": "constraints", "type": "string", "value": [ "node.platform.os == linux" ]}, {"name": "Resources", "type": "Resources", "value": { "Limits": { "NanoCPUs": 4000000000, "MemoryBytes": 17179869184 }, "Reservations": { "NanoCPUs": 100000000, "MemoryBytes": 536870912, "GenericResources": [ { "DiscreteResourceSpec": { "Kind": "VRAM", "Value": 1 } }, { "NamedResourceSpec": { "Kind": "AIRAM", "Value": "some_string" } } ] } } } ]'
            },
            _DEFAULT_RESOURCES.copy(
                update={
                    "__root__": {
                        "CPU": ResourceValue(limit=4.0, reservation=0.1),
                        "RAM": ResourceValue(
                            limit=ByteSize(17179869184), reservation=ByteSize(536870912)
                        ),
                        "VRAM": ResourceValue(limit=0, reservation=1),
                        "AIRAM": ResourceValue(limit=0, reservation="some_string"),
                    }
                }
            ),
            id="everything_rightly_defined",
        ),
        pytest.param(
            {
                "simcore.service.settings": '[ {"name": "Resources", "type": "Resources", "value": { "Reservations": { "NanoCPUs": 100000000, "MemoryBytes": 536870912, "GenericResources": [  ] } } } ]'
            },
            _DEFAULT_RESOURCES.copy(
                update={
                    "__root__": {
                        "CPU": ResourceValue(
                            limit=_DEFAULT_RESOURCES["CPU"].limit,
                            reservation=0.1,
                        ),
                        "RAM": ResourceValue(
                            limit=_DEFAULT_RESOURCES["RAM"].limit,
                            reservation=ByteSize(536870912),
                        ),
                    }
                }
            ),
            id="no_limits_defined_returns_default_limits",
        ),
        pytest.param(
            {
                "simcore.service.settings": '[ {"name": "Resources", "type": "Resources", "value": { "Reservations": { "NanoCPUs": 10000000000, "MemoryBytes": 53687091232, "GenericResources": [ { "DiscreteResourceSpec": { "Kind": "VRAM", "Value": 1 } } ] } } } ]'
            },
            _DEFAULT_RESOURCES.copy(
                update={
                    "__root__": {
                        "CPU": ResourceValue(
                            limit=10.0,
                            reservation=10.0,
                        ),
                        "RAM": ResourceValue(
                            limit=ByteSize(53687091232),
                            reservation=ByteSize(53687091232),
                        ),
                        "VRAM": ResourceValue(limit=0, reservation=1),
                    }
                }
            ),
            id="no_limits_with_reservations_above_default_returns_same_as_reservation",
        ),
    ],
)
async def test_get_service_resources(
    mock_catalog_background_task,
    mock_director_service_labels: Route,
    client: TestClient,
    director_labels: Dict[str, Any],
    expected_resources: ResourcesDict,
) -> None:
    service_key = f"simcore/services/{choice(['comp', 'dynamic'])}/jupyter-math"
    service_version = f"{randint(0,100)}.{randint(0,100)}.{randint(0,100)}"
    mock_director_service_labels.respond(json={"data": director_labels})
    url = URL(f"/v0/services/{service_key}/{service_version}/resources")
    response = client.get(f"{url}")
    assert response.status_code == 200, f"{response.text}"
    data = response.json()
    received_resources = ServiceResources.parse_obj(data)

    expected_service_resources = ServiceResources.from_resources(
        expected_resources, f"{service_key}:{service_version}"
    )
    assert received_resources.dict() == expected_service_resources.dict()
    assert received_resources.json() == expected_service_resources.json()
    assert received_resources == expected_service_resources


@pytest.fixture
def create_mock_director_service_labels(
    director_mockup: respx.MockRouter, app: FastAPI
) -> Callable:
    def factory(services_labels: Dict[str, Dict[str, Any]]) -> None:
        for service_name, data in services_labels.items():
            encoded_key = urllib.parse.quote_plus(
                f"simcore/services/dynamic/{service_name}"
            )
            director_mockup.get(
                url__regex=rf"v0/services/{encoded_key}/[0-9]+.[0-9]+.[0-9]+/labels",
                name=f"get_service_labels_for_{service_name}",
            ).respond(200, json={"data": data})

    return factory


@pytest.mark.parametrize(
    "mapped_services_labels, expected_service_resources",
    [
        pytest.param(
            {
                "sim4life-dy": {
                    "simcore.service.settings": '[ {"name": "Resources", "type": "Resources", "value": { "Reservations": { "NanoCPUs": 300000000, "MemoryBytes": 53687091232 } } } ]',
                    "simcore.service.compose-spec": '{"version": "2.3", "services": {"rt-web-dy":{"image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/sim4life-dy:${SERVICE_VERSION}","init": true, "depends_on": ["s4l-core"]}, "s4l-core": {"image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/s4l-core-dy:${SERVICE_VERSION}","runtime": "nvidia", "init": true, "environment": ["DISPLAY=${DISPLAY}"],"volumes": ["/tmp/.X11-unix:/tmp/.X11-unix"]}, "sym-server": {"image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/sym-server:${SERVICE_VERSION}","init": true}}}',
                },
                "s4l-core-dy": {
                    "simcore.service.settings": '[{"name": "env", "type": "string", "value": ["DISPLAY=:0"]},{"name": "env", "type": "string", "value": ["SYM_SERVER_HOSTNAME=%%container_name.sym-server%%"]},{"name": "mount", "type": "object", "value": [{"ReadOnly": true, "Source":"/tmp/.X11-unix", "Target": "/tmp/.X11-unix", "Type": "bind"}]}, {"name":"constraints", "type": "string", "value": ["node.platform.os == linux"]},{"name": "Resources", "type": "Resources", "value": {"Limits": {"NanoCPUs":4000000000, "MemoryBytes": 17179869184}, "Reservations": {"NanoCPUs": 100000000,"MemoryBytes": 536870912, "GenericResources": [{"DiscreteResourceSpec":{"Kind": "VRAM", "Value": 1}}]}}}]'
                },
                "sym-server": {"simcore.service.settings": "[]"},
            },
            ServiceResources.parse_obj(
                ServiceResources.Config.schema_extra["examples"][1]
            ),
            id="s4l_case",
        ),
    ],
)
async def test_get_service_resources_sim4life_case(
    mock_catalog_background_task,
    create_mock_director_service_labels: Callable,
    client: TestClient,
    mapped_services_labels: Dict[str, Dict[str, Any]],
    expected_service_resources: ServiceResources,
) -> None:
    service_key = "simcore/services/dynamic/sim4life-dy"
    service_version = "3.0.0"

    create_mock_director_service_labels(mapped_services_labels)

    url = URL(f"/v0/services/{service_key}/{service_version}/resources")
    response = client.get(f"{url}")
    assert response.status_code == 200, f"{response.text}"
    data = response.json()
    received_service_resources = ServiceResources.parse_obj(data)

    # assemble expected!

    assert received_service_resources.dict() == expected_service_resources.dict()
    assert received_service_resources.json() == expected_service_resources.json()
    assert received_service_resources == expected_service_resources


async def test_get_service_resources_raises_errors(
    mock_catalog_background_task,
    mock_director_service_labels: Route,
    client: TestClient,
) -> None:

    service_key = f"simcore/services/{choice(['comp', 'dynamic'])}/jupyter-math"
    service_version = f"{randint(0,100)}.{randint(0,100)}.{randint(0,100)}"
    url = URL(f"/v0/services/{service_key}/{service_version}/resources")
    # simulate a communication error
    mock_director_service_labels.side_effect = httpx.HTTPError
    response = client.get(f"{url}")
    assert response.status_code == httpx.codes.SERVICE_UNAVAILABLE, f"{response.text}"
    # simulate a missing service
    mock_director_service_labels.respond(
        httpx.codes.NOT_FOUND, json={"error": "service not found"}
    )
    response = client.get(f"{url}")
    assert response.status_code == httpx.codes.NOT_FOUND, f"{response.text}"
