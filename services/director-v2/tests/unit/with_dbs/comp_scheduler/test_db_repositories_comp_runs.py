# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import datetime
from collections.abc import Awaitable, Callable

import pytest
from _helpers import PublishedProject
from faker import Faker
from models_library.clusters import DEFAULT_CLUSTER_ID, Cluster
from models_library.projects import ProjectID
from models_library.users import UserID
from simcore_service_director_v2.core.errors import (
    ClusterNotFoundError,
    ComputationalRunNotFoundError,
    ProjectNotFoundError,
    UserNotFoundError,
)
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB, RunMetadataDict
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

    await create_comp_run(published_project.user, published_project.project)
    await CompRunsRepository(aiopg_engine).get(
        published_project.project.prj_owner, published_project.project.uuid
    )


async def test_list(
    aiopg_engine,
):
    assert await CompRunsRepository(aiopg_engine).list() == []


async def test_create(
    aiopg_engine,
    fake_user_id: UserID,
    fake_project_id: ProjectID,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    create_cluster: Callable[..., Awaitable[Cluster]],
):
    with pytest.raises(ProjectNotFoundError):
        await CompRunsRepository(aiopg_engine).create(
            user_id=fake_user_id,
            project_id=fake_project_id,
            cluster_id=DEFAULT_CLUSTER_ID,
            iteration=None,
            metadata=run_metadata,
            use_on_demand_clusters=faker.pybool(),
        )
    published_project = await publish_project()
    with pytest.raises(UserNotFoundError):
        await CompRunsRepository(aiopg_engine).create(
            user_id=fake_user_id,
            project_id=published_project.project.uuid,
            cluster_id=DEFAULT_CLUSTER_ID,
            iteration=None,
            metadata=run_metadata,
            use_on_demand_clusters=faker.pybool(),
        )

    created = await CompRunsRepository(aiopg_engine).create(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
    )
    got = await CompRunsRepository(aiopg_engine).get(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
    )
    assert created == got

    # creating a second one auto increment the iteration
    created = await CompRunsRepository(aiopg_engine).create(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
    )
    assert created != got
    assert created.iteration == got.iteration + 1

    # getting without specifying the iteration returns the latest
    got = await CompRunsRepository(aiopg_engine).get(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
    )
    assert created == got

    with pytest.raises(ClusterNotFoundError):
        await CompRunsRepository(aiopg_engine).create(
            user_id=published_project.user["id"],
            project_id=published_project.project.uuid,
            cluster_id=faker.pyint(min_value=1),
            iteration=None,
            metadata=run_metadata,
            use_on_demand_clusters=faker.pybool(),
        )
    cluster = await create_cluster(published_project.user)
    await CompRunsRepository(aiopg_engine).create(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
        cluster_id=cluster.id,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
    )


async def test_update(
    aiopg_engine,
    fake_user_id: UserID,
    fake_project_id: ProjectID,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
):
    # this updates nothing but also does not complain
    updated = await CompRunsRepository(aiopg_engine).update(
        fake_user_id, fake_project_id, faker.pyint(min_value=1)
    )
    assert updated is None
    # now let's create a valid one
    published_project = await publish_project()
    created = await CompRunsRepository(aiopg_engine).create(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
    )

    got = await CompRunsRepository(aiopg_engine).get(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
    )
    assert created == got

    updated = await CompRunsRepository(aiopg_engine).update(
        created.user_id,
        created.project_uuid,
        created.iteration,
        scheduled=datetime.datetime.now(datetime.UTC),
    )
    assert updated is not None
    assert created != updated
    assert created.scheduled is None
    assert updated.scheduled is not None


async def test_delete(aiopg_engine):
    ...


async def test_set_run_result(aiopg_engine):
    ...


async def test_mark_for_cancellation(aiopg_engine):
    ...


async def test_mark_for_scheduling(aiopg_engine):
    ...


async def test_mark_scheduling_done(aiopg_engine):
    ...
