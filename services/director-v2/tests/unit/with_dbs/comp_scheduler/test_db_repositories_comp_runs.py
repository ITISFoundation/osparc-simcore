import pytest
from models_library.projects import ProjectID
from models_library.users import UserID
from simcore_service_director_v2.core.errors import ComputationalRunNotFoundError
from simcore_service_director_v2.modules.db.repositories.comp_runs import (
    CompRunsRepository,
)

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_get(aiopg_engine, user_id: UserID, project_id: ProjectID):
    with pytest.raises(ComputationalRunNotFoundError):
        await CompRunsRepository(aiopg_engine).get(user_id, project_id)


async def test_list():
    ...


async def test_create():
    ...


async def test_update():
    ...


async def test_delete():
    ...


async def test_set_run_result():
    ...


async def test_mark_for_cancellation():
    ...


async def test_mark_for_scheduling():
    ...


async def test_mark_scheduling_done():
    ...
