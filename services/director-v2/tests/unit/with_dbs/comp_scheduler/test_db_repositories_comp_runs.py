# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Awaitable, Callable

import pytest
from _helpers import PublishedProject
from faker import Faker
from models_library.projects import ProjectID
from models_library.users import UserID
from simcore_service_director_v2.core.errors import ComputationalRunNotFoundError
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB
from simcore_service_director_v2.modules.db.repositories.comp_runs import (
    CompRunsRepository,
)

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def fake_user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture
def fake_project_id(faker: Faker) -> ProjectID:
    return ProjectID(f"{faker.uuid4(cast_to=None)}")


async def test_get(
    aiopg_engine,
    fake_user_id: UserID,
    fake_project_id: ProjectID,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
):
    with pytest.raises(ComputationalRunNotFoundError):
        await CompRunsRepository(aiopg_engine).get(fake_user_id, fake_project_id)

    published_project = await publish_project()
    assert published_project.project.prj_owner
    # there is still no comp run created
    with pytest.raises(ComputationalRunNotFoundError):
        await CompRunsRepository(aiopg_engine).get(
            published_project.project.prj_owner, published_project.project.uuid
        )

    comp_run = await create_comp_run(published_project.user, published_project.project)
    await CompRunsRepository(aiopg_engine).get(
        published_project.project.prj_owner, published_project.project.uuid
    )


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
