# pylint: disable=no-value-for-parameter
# pylint: disable=not-an-iterable
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import urllib.parse
from collections.abc import Callable
from typing import Any

import pytest
import respx
from fastapi.testclient import TestClient
from models_library.api_schemas_catalog.services import ServiceGet
from models_library.products import ProductName
from models_library.users import UserID
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
async def expected_service(
    expected_director_list_services: list[dict[str, Any]],
    user: dict[str, Any],
    services_db_tables_injector: Callable,
    target_product: ProductName,
) -> dict[str, Any]:
    # Just selected one of the list provided by the director (i.e. emulated from registry)
    service = expected_director_list_services[-1]

    # Emulates sync of registry with db and injects the expected response model
    # of the director (i.e. coming from the registry) in the database
    await services_db_tables_injector(
        [
            (  # service
                {
                    "key": service["key"],
                    "version": service["version"],
                    "owner": user["primary_gid"],
                    "name": service["name"],
                    "description": service["description"],
                    "thumbnail": service["thumbnail"],
                },
                # owner_access,
                {
                    "key": service["key"],
                    "version": service["version"],
                    "gid": user["primary_gid"],
                    "execute_access": True,
                    "write_access": True,
                    "product_name": target_product,
                }
                # team_access, everyone_access [optional]
            )
        ]
    )
    return service


def test_get_service_with_details(
    service_caching_disabled: None,
    background_tasks_setup_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_service_api: respx.MockRouter,
    user_id: UserID,
    expected_service: dict[str, Any],
    target_product: ProductName,
    client: TestClient,
):
    service_key = expected_service["key"]
    service_version = expected_service["version"]

    url = URL(
        f"/v0/services/{urllib.parse.quote_plus(service_key)}/{service_version}"
    ).with_query({"user_id": user_id})

    response = client.get(
        f"{url}",
        headers={
            "x-simcore-products-name": target_product,
        },
    )

    assert response.status_code == 200

    got = ServiceGet.model_validate(response.json())
    assert got.key == service_key
    assert got.version == service_version

    assert mocked_director_service_api["get_service"].called
