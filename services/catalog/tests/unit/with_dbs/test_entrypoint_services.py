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

import pytest
import respx
from faker import Faker
from fastapi import FastAPI
from models_library.services import (
    GenericResources,
    Limitations,
    Reservations,
    ServiceDockerData,
    ServiceResources,
)
from pydantic import ByteSize
from respx.models import Route
from respx.router import MockRouter
from simcore_service_catalog.core.settings import (
    _DEFAULT_SERVICE_LIMITATIONS,
    _DEFAULT_SERVICE_RESERVATIONS,
)
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
            ServiceResources(
                limits=_DEFAULT_SERVICE_LIMITATIONS,
                reservations=_DEFAULT_SERVICE_RESERVATIONS,
            ),
            id="nothing_defined_returns_default_resources",
        ),
        pytest.param(
            {
                "simcore.service.settings": '[ {"name": "Resources", "type": "Resources", "value": { "Limits": { "NanoCPUs": 4000000000, "MemoryBytes": 17179869184 } } } ]',
            },
            ServiceResources(
                limits=Limitations(cpu=4.0, ram=ByteSize(17179869184)),
                reservations=_DEFAULT_SERVICE_RESERVATIONS,
            ),
            id="only_limits_defined_returns_default_reservations",
        ),
        pytest.param(
            {
                "simcore.service.settings": '[ {"name": "constraints", "type": "string", "value": [ "node.platform.os == linux" ]}, {"name": "Resources", "type": "Resources", "value": { "Limits": { "NanoCPUs": 4000000000, "MemoryBytes": 17179869184 }, "Reservations": { "NanoCPUs": 100000000, "MemoryBytes": 536870912, "GenericResources": [ { "DiscreteResourceSpec": { "Kind": "VRAM", "Value": 1 } }, { "NamedResourceSpec": { "Kind": "SOME_STUFF", "Value": "some_string" } } ] } } } ]'
            },
            ServiceResources(
                limits=Limitations(cpu=4.0, ram=ByteSize(17179869184)),
                reservations=Reservations(
                    cpu=0.1,
                    ram=ByteSize(536870912),
                    generic=GenericResources.parse_obj(
                        {"VRAM": 1, "SOME_STUFF": "some_string"}
                    ),
                ),
            ),
            id="everything_rightly_defined",
        ),
        pytest.param(
            {
                "simcore.service.settings": '[ {"name": "Resources", "type": "Resources", "value": { "Reservations": { "NanoCPUs": 100000000, "MemoryBytes": 536870912, "GenericResources": [ { "DiscreteResourceSpec": { "Kind": "VRAM", "Value": 1 } } ] } } } ]'
            },
            ServiceResources(
                limits=_DEFAULT_SERVICE_LIMITATIONS,
                reservations=Reservations(
                    cpu=0.1,
                    ram=ByteSize(536870912),
                    generic=GenericResources.parse_obj({"VRAM": 1}),
                ),
            ),
            id="no_limits_defined_returns_default_limits",
        ),
        pytest.param(
            {
                "simcore.service.settings": '[ {"name": "Resources", "type": "Resources", "value": { "Reservations": { "NanoCPUs": 10000000000, "MemoryBytes": 53687091232, "GenericResources": [ { "DiscreteResourceSpec": { "Kind": "VRAM", "Value": 1 } } ] } } } ]'
            },
            ServiceResources(
                limits=Limitations(cpu=10.0, ram=ByteSize(53687091232)),
                reservations=Reservations(
                    cpu=10.0,
                    ram=ByteSize(53687091232),
                    generic=GenericResources.parse_obj({"VRAM": 1}),
                ),
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
    expected_resources: ServiceResources,
    faker: Faker,
):
    service_key = f"simcore/services/{choice(['comp', 'dynamic'])}/jupyter-math"
    service_version = f"{randint(0,100)}.{randint(0,100)}.{randint(0,100)}"
    mock_director_service_labels.respond(json={"data": director_labels})
    url = URL(f"/v0/services/{service_key}/{service_version}/resources")
    response = client.get(f"{url}")
    assert response.status_code == 200, f"{response.text}"
    data = response.json()
    received_resources = ServiceResources.parse_obj(data)
    assert received_resources == expected_resources
