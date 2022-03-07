# pylint: disable=no-value-for-parameter
# pylint: disable=not-an-iterable
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Callable, List

from respx.router import MockRouter
from starlette.testclient import TestClient
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_list_services_without_details(
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
    NUM_SERVICES = 1000
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
    response = client.get(f"{url}", headers={"x-simcore-products-name": target_product})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == NUM_SERVICES


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
