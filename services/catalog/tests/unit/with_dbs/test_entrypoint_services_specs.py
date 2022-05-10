# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from random import choice, randint
from typing import Any

import respx
from models_library.users import UserID
from simcore_service_catalog.models.schemas.services_specifications import (
    ServiceSpecificationsGet,
)
from starlette import status
from starlette.testclient import TestClient
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_get_service_specifications_returns_403_if_user_does_not_exist(
    mock_catalog_background_task,
    director_mockup: respx.MockRouter,
    client: TestClient,
    user_id: UserID,
):
    service_key = f"simcore/services/{choice(['comp', 'dynamic'])}/jupyter-math"
    service_version = f"{randint(0,100)}.{randint(0,100)}.{randint(0,100)}"
    url = URL(
        f"/v0/services/{service_key}/{service_version}/specifications"
    ).with_query(user_id=user_id)
    response = client.get(f"{url}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_get_service_specifications(
    mock_catalog_background_task,
    director_mockup: respx.MockRouter,
    client: TestClient,
    user_id: UserID,
    user_db: dict[str, Any],
):
    service_key = f"simcore/services/{choice(['comp', 'dynamic'])}/jupyter-math"
    service_version = f"{randint(0,100)}.{randint(0,100)}.{randint(0,100)}"
    url = URL(
        f"/v0/services/{service_key}/{service_version}/specifications"
    ).with_query(user_id=user_id)
    response = client.get(f"{url}")
    assert response.status_code == status.HTTP_200_OK
    service_specs = ServiceSpecificationsGet.parse_obj(response.json())
    assert service_specs
    assert service_specs.schedule_specs == {}
