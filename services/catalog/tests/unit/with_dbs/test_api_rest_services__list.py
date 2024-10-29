# pylint: disable=no-value-for-parameter
# pylint: disable=not-an-iterable
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
from collections.abc import Callable
from datetime import datetime, timedelta

from models_library.api_schemas_catalog.services import ServiceGet
from models_library.products import ProductName
from models_library.services import ServiceMetaDataPublished
from models_library.users import UserID
from pydantic import TypeAdapter
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


async def test_list_services_with_details(
    background_tasks_setup_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_service_api_base: MockRouter,
    user_id: UserID,
    target_product: ProductName,
    create_fake_service_data: Callable,
    services_db_tables_injector: Callable,
    client: TestClient,
    benchmark,
):
    # create some fake services
    NUM_SERVICES = 1000
    fake_services = [
        create_fake_service_data(
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
    fake_registry_service_data = ServiceMetaDataPublished.model_config[
        "json_schema_extra"
    ]["examples"][0]

    mocked_director_service_api_base.get("/services", name="list_services").respond(
        200,
        json={
            "data": [
                {
                    **fake_registry_service_data,
                    "key": s[0]["key"],
                    "version": s[0]["version"],
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
    background_tasks_setup_disabled: None,
    mocked_director_service_api: MockRouter,
    rabbitmq_and_rpc_setup_disabled: None,
    user_id: int,
    target_product: ProductName,
    create_fake_service_data: Callable,
    services_db_tables_injector: Callable,
    client: TestClient,
    benchmark,
):

    # injects fake data in db
    NUM_SERVICES = 1000
    SERVICE_KEY = "simcore/services/dynamic/jupyterlab"
    await services_db_tables_injector(
        [
            create_fake_service_data(
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
    service_caching_disabled,
    background_tasks_setup_disabled: None,
    mocked_director_service_api: MockRouter,
    rabbitmq_and_rpc_setup_disabled: None,
    user_id: int,
    target_product: ProductName,
    create_fake_service_data: Callable,
    services_db_tables_injector: Callable,
    client: TestClient,
):

    # injects fake data in db
    NUM_SERVICES = 1
    await services_db_tables_injector(
        [
            create_fake_service_data(
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
    service_caching_disabled: None,
    background_tasks_setup_disabled: None,
    mocked_director_service_api: MockRouter,
    rabbitmq_and_rpc_setup_disabled: None,
    user_id: int,
    target_product: ProductName,
    other_product: ProductName,
    create_fake_service_data: Callable,
    services_db_tables_injector: Callable,
    client: TestClient,
):
    NUM_SERVICES = 15
    await services_db_tables_injector(
        [
            create_fake_service_data(
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
    response = client.get(f"{url}", headers={"x-simcore-products-name": other_product})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


async def test_list_services_without_details_with_wrong_product_returns_0_service(
    service_caching_disabled,
    background_tasks_setup_disabled,
    mocked_director_service_api: MockRouter,
    rabbitmq_and_rpc_setup_disabled: None,
    user_id: int,
    target_product: ProductName,
    create_fake_service_data: Callable,
    services_db_tables_injector: Callable,
    client: TestClient,
):

    # injects fake data in db
    NUM_SERVICES = 1
    await services_db_tables_injector(
        [
            create_fake_service_data(
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
    service_caching_disabled,
    background_tasks_setup_disabled,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_service_api_base: MockRouter,
    user_id: int,
    target_product: ProductName,
    create_fake_service_data: Callable,
    services_db_tables_injector: Callable,
    client: TestClient,
):

    # injects fake data in db
    deprecation_date = datetime.utcnow() + timedelta(days=1)
    deprecated_service = create_fake_service_data(
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
    list_of_services = TypeAdapter(list[ServiceGet]).validate_python(resp.json())
    assert list_of_services
    assert len(list_of_services) == 1
    received_service = list_of_services[0]
    assert received_service.deprecated == deprecation_date

    # for details, the director must return the same service
    fake_registry_service_data = ServiceMetaDataPublished.model_config[
        "json_schema_extra"
    ]["examples"][0]
    mocked_director_service_api_base.get("/services", name="list_services").respond(
        200,
        json={
            "data": [
                {
                    **fake_registry_service_data,
                    "key": deprecated_service[0]["key"],
                    "version": deprecated_service[0]["version"],
                }
            ]
        },
    )

    url = URL("/v0/services").with_query({"user_id": user_id, "details": "true"})
    resp = client.get(f"{url}", headers={"x-simcore-products-name": target_product})
    assert resp.status_code == status.HTTP_200_OK
    list_of_services = TypeAdapter(list[ServiceGet]).validate_python(resp.json())
    assert list_of_services
    assert len(list_of_services) == 1
    received_service = list_of_services[0]
    assert received_service.deprecated == deprecation_date
