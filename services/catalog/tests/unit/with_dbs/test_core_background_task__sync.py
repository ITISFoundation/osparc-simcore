# pylint: disable=no-value-for-parameter
# pylint: disable=not-an-iterable
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any

import pytest
from fastapi import FastAPI
from models_library.products import ProductName
from models_library.users import UserID
from respx.router import MockRouter
from simcore_service_catalog.core.background_tasks import _run_sync_services
from simcore_service_catalog.db.repositories.services import ServicesRepository

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def services_repo(app: FastAPI) -> ServicesRepository:
    # depends on client so the app has a state ready
    assert len(app.state._state) > 0  # noqa: SLF001
    return ServicesRepository(app.state.engine)


async def test_registry_sync_task(
    background_tasks_setup_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_service_api: MockRouter,
    expected_director_list_services: list[dict[str, Any]],
    user_id: UserID,
    target_product: ProductName,
    app: FastAPI,
    services_repo: ServicesRepository,
):

    assert app.state

    service_key = expected_director_list_services[0]["key"]
    service_version = expected_director_list_services[0]["version"]

    # in registry but NOT in db
    got_from_db = await services_repo.get_service_with_history(
        product_name=target_product,
        user_id=user_id,
        key=service_key,
        version=service_version,
    )
    assert not got_from_db

    await _run_sync_services(app)

    # afer sync, it should be in db as well
    got_from_db = await services_repo.get_service_with_history(
        product_name=target_product,
        user_id=user_id,
        key=service_key,
        version=service_version,
    )
    assert got_from_db
