# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from random import choice, randint

import respx
from starlette import status
from starlette.testclient import TestClient
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_get_service_specifications(
    mock_catalog_background_task,
    director_mockup: respx.MockRouter,
    client: TestClient,
):
    service_key = f"simcore/services/{choice(['comp', 'dynamic'])}/jupyter-math"
    service_version = f"{randint(0,100)}.{randint(0,100)}.{randint(0,100)}"
    url = URL(f"/v0/services/{service_key}/{service_version}/specifications")
    response = client.get(f"{url}")
    assert response.status_code == status.HTTP_200_OK
