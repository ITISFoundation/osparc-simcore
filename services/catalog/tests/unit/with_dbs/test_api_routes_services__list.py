# pylint: disable=no-value-for-parameter
# pylint: disable=not-an-iterable
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
from collections.abc import Callable
from datetime import datetime, timedelta

import pytest
from models_library.api_schemas_catalog.services import ServiceGet
from models_library.services import ServiceDockerData
from pydantic import parse_obj_as
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
def disable_service_caching(monkeypatch):
    monkeypatch.setenv("AIOCACHE_DISABLE", "1")


async def test_list_services_with_details(
    mock_catalog_background_task: None,
    director_mockup: MockRouter,
    client: TestClient,
    user_id: int,
    products_names: list[str],
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
    mock_catalog_background_task: None,
    director_mockup: MockRouter,
    client: TestClient,
    user_id: int,
    products_names: list[str],
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
    disable_service_caching,
    mock_catalog_background_task: None,
    director_mockup: MockRouter,
    client: TestClient,
    user_id: int,
    products_names: list[str],
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
    disable_service_caching: None,
    mock_catalog_background_task: None,
    director_mockup: MockRouter,
    client: TestClient,
    user_id: int,
    products_names: list[str],
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
    disable_service_caching,
    mock_catalog_background_task,
    director_mockup: MockRouter,
    client: TestClient,
    user_id: int,
    products_names: list[str],
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


async def test_list_services_that_are_deprecated(
    disable_service_caching,
    mock_catalog_background_task,
    director_mockup: MockRouter,
    client: TestClient,
    user_id: int,
    products_names: list[str],
    service_catalog_faker: Callable,
    services_db_tables_injector: Callable,
):
    target_product = products_names[-1]
    assert (
        len(products_names) > 1
    ), "please adjust the fixture to have the right number of products"
    # injects fake data in db
    deprecation_date = datetime.utcnow() + timedelta(days=1)
    deprecated_service = service_catalog_faker(
        "simcore/services/dynamic/jupyterlab",
        "1.0.1",
        team_access=None,
        everyone_access=None,
        product=target_product,
        deprecated=deprecation_date,
    )
    await services_db_tables_injector([deprecated_service])

    # check without details
    url = URL("/v0/services").with_query({"user_id": user_id, "details": "false"})
    resp = client.get(f"{url}", headers={"x-simcore-products-name": target_product})
    assert resp.status_code == status.HTTP_200_OK
    list_of_services = parse_obj_as(list[ServiceGet], resp.json())
    assert list_of_services
    assert len(list_of_services) == 1
    received_service = list_of_services[0]
    assert received_service.deprecated == deprecation_date

    # for details, the director must return the same service
    fake_registry_service_data = ServiceDockerData.Config.schema_extra["examples"][0]
    director_mockup.get("/services", name="list_services").respond(
        200,
        json={
            "data": [
                {
                    **fake_registry_service_data,
                    **{
                        "key": deprecated_service[0]["key"],
                        "version": deprecated_service[0]["version"],
                    },
                }
            ]
        },
    )

    url = URL("/v0/services").with_query({"user_id": user_id, "details": "true"})
    resp = client.get(f"{url}", headers={"x-simcore-products-name": target_product})
    assert resp.status_code == status.HTTP_200_OK
    list_of_services = parse_obj_as(list[ServiceGet], resp.json())
    assert list_of_services
    assert len(list_of_services) == 1
    received_service = list_of_services[0]
    assert received_service.deprecated == deprecation_date
