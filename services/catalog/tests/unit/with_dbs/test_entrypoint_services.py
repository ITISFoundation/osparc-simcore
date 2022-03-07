# pylint: disable=no-value-for-parameter
# pylint: disable=not-an-iterable
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any, Callable, Dict, List

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
    service_catalog_faker: Callable,
    services_db_tables_injector: Callable,
):
    target_product = products_names[-1]
    # injects fake data in db
    await services_db_tables_injector(
        [
            service_catalog_faker(
                "simcore/services/dynamic/jupyterlab",
                "1.0.0",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
            service_catalog_faker(
                "simcore/services/dynamic/jupyterlab",
                "1.0.2",
                team_access="x",
                everyone_access=None,
                product=target_product,
            ),
        ]
    )

    url = URL("/v0/services").with_query(user_id=user_id)
    response = client.get(f"{url}", headers={"x-simcore-products-name": target_product})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    import pdb

    pdb.set_trace()
