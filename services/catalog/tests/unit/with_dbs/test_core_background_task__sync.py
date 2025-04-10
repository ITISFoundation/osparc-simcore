# pylint: disable=no-value-for-parameter
# pylint: disable=not-an-iterable
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any

import pytest
import simcore_service_catalog.service.access_rights
from fastapi import FastAPI, HTTPException, status
from pytest_mock import MockerFixture
from respx.router import MockRouter
from simcore_postgres_database.models.services import services_meta_data
from simcore_service_catalog.core.background_tasks import _run_sync_services
from simcore_service_catalog.repository.services import ServicesRepository
from sqlalchemy.ext.asyncio.engine import AsyncEngine

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


@pytest.fixture
async def cleanup_service_meta_data_db_content(sqlalchemy_async_engine: AsyncEngine):
    # NOTE: necessary because _run_sync_services fills tables
    yield

    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(services_meta_data.delete())


@pytest.mark.parametrize("director_fails", [False, True])
async def test_registry_sync_task(
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_service_api: MockRouter,
    expected_director_list_services: list[dict[str, Any]],
    user: dict[str, Any],
    app: FastAPI,
    services_repo: ServicesRepository,
    cleanup_service_meta_data_db_content: None,
    mocker: MockerFixture,
    director_fails: bool,
):
    assert app.state

    if director_fails:
        # Emulates issue https://github.com/ITISFoundation/osparc-simcore/issues/6318
        mocker.patch.object(
            simcore_service_catalog.service.access_rights,
            "_is_old_service",
            side_effect=HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="fake director error"
            ),
        )

    service_key = expected_director_list_services[0]["key"]
    service_version = expected_director_list_services[0]["version"]

    # in registry but NOT in db
    got_from_db = await services_repo.get_service_with_history(
        product_name="osparc",
        user_id=user["id"],
        key=service_key,
        version=service_version,
    )
    assert not got_from_db

    # let's sync
    await _run_sync_services(app)

    # after sync, it should be in db as well
    got_from_db = await services_repo.get_service_with_history(
        product_name="osparc",
        user_id=user["id"],
        key=service_key,
        version=service_version,
    )

    if director_fails:
        assert not got_from_db
    else:
        assert got_from_db
        assert got_from_db.key == service_key
        assert got_from_db.version == service_version
