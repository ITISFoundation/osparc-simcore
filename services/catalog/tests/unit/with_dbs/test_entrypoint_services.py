# pylint: disable=no-value-for-parameter
# pylint: disable=not-an-iterable
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any, Dict, List

from fastapi import FastAPI
from respx.router import MockRouter
from starlette.testclient import TestClient
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_list_services(
    director_mockup: MockRouter,
    app: FastAPI,
    client: TestClient,
    user_id: int,
    user_db: Dict[str, Any],
    products_names: List[str],
):
    url = URL("/v0/services").with_query(user_id=user_id)
    response = client.get(
        f"{url}", headers={"x-simcore-products-name": products_names[0]}
    )
    assert response.status_code == 200
    data = response.json()
