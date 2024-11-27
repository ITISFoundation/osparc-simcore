# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import datetime
import random
from collections.abc import Awaitable, Callable
from typing import cast

import arrow
import pytest
from _helpers import PublishedProject
from faker import Faker
from models_library.clusters import DEFAULT_CLUSTER_ID, Cluster
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from models_library.users import UserID
from simcore_service_director_v2.core.errors import (
    ClusterNotFoundError,
    ComputationalRunNotFoundError,
    ProjectNotFoundError,
    UserNotFoundError,
)
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB, RunMetadataDict
from simcore_service_director_v2.modules.comp_scheduler._constants import (
    SCHEDULER_INTERVAL,
)
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
    publish_project: Callable[[], Awaitable[PublishedProject]],
    run_metadata: RunMetadataDict,
    faker: Faker,
):
    assert await CompRunsRepository(aiopg_engine).list() == []

    published_project = await publish_project()
    assert await CompRunsRepository(aiopg_engine).list() == []

    created = await CompRunsRepository(aiopg_engine).create(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
    )
    assert await CompRunsRepository(aiopg_engine).list() == [created]

    created = [created] + await asyncio.gather(
        *(
            CompRunsRepository(aiopg_engine).create(
                user_id=published_project.user["id"],
                project_id=published_project.project.uuid,
                cluster_id=DEFAULT_CLUSTER_ID,
                iteration=created.iteration + n + 1,
                metadata=run_metadata,
                use_on_demand_clusters=faker.pybool(),
            )
            for n in range(50)
        )
    )
    assert sorted(
        await CompRunsRepository(aiopg_engine).list(), key=lambda x: x.iteration
    ) == sorted(created, key=lambda x: x.iteration)

    # test with filter of state
    any_state_but_published = {
        s for s in RunningState if s is not RunningState.PUBLISHED
    }
    assert (
        await CompRunsRepository(aiopg_engine).list(
            filter_by_state=any_state_but_published
        )
        == []
    )
    assert sorted(
        await CompRunsRepository(aiopg_engine).list(
            filter_by_state={RunningState.PUBLISHED}
        ),
        key=lambda x: x.iteration,
    ) == sorted(created, key=lambda x: x.iteration)

    # test with never scheduled filter, let's create a bunch of scheduled entries,
    assert sorted(
        await CompRunsRepository(aiopg_engine).list(never_scheduled=True),
        key=lambda x: x.iteration,
    ) == sorted(created, key=lambda x: x.iteration)
    comp_runs_marked_for_scheduling = random.sample(created, k=25)
    await asyncio.gather(
        *(
            CompRunsRepository(aiopg_engine).mark_for_scheduling(
                user_id=comp_run.user_id,
                project_id=comp_run.project_uuid,
                iteration=comp_run.iteration,
            )
            for comp_run in comp_runs_marked_for_scheduling
        )
    )
    # filter them away
    created = [r for r in created if r not in comp_runs_marked_for_scheduling]
    assert sorted(
        await CompRunsRepository(aiopg_engine).list(never_scheduled=True),
        key=lambda x: x.iteration,
    ) == sorted(created, key=lambda x: x.iteration)

    # now mark a few of them as processed
    comp_runs_marked_as_processed = random.sample(comp_runs_marked_for_scheduling, k=11)
    await asyncio.gather(
        *(
            CompRunsRepository(aiopg_engine).mark_as_processed(
                user_id=comp_run.user_id,
                project_id=comp_run.project_uuid,
                iteration=comp_run.iteration,
            )
            for comp_run in comp_runs_marked_as_processed
        )
    )
    # filter them away
    comp_runs_marked_for_scheduling = [
        r
        for r in comp_runs_marked_for_scheduling
        if r not in comp_runs_marked_as_processed
    ]
    # since they were just marked as processed now, we will get nothing
    assert (
        sorted(
            await CompRunsRepository(aiopg_engine).list(
                never_scheduled=False, processed_since=SCHEDULER_INTERVAL
            ),
            key=lambda x: x.iteration,
        )
        == []
    )
    # now we artificially change the scheduled/processed time and set it 2x the scheduler interval
    # these are correctly processed ones, so we should get them back
    fake_scheduled_time = arrow.utcnow().datetime - 2 * SCHEDULER_INTERVAL
    fake_processed_time = fake_scheduled_time + 0.5 * SCHEDULER_INTERVAL
    comp_runs_marked_as_processed = (
        cast(  # NOTE: the cast here is ok since gather will raise if there is an error
            list[CompRunsAtDB],
            await asyncio.gather(
                *(
                    CompRunsRepository(aiopg_engine).update(
                        user_id=comp_run.user_id,
                        project_id=comp_run.project_uuid,
                        iteration=comp_run.iteration,
                        scheduled=fake_scheduled_time,
                        processed=fake_processed_time,
                    )
                    for comp_run in comp_runs_marked_as_processed
                )
            ),
        )
    )
    # now we should get them
    assert sorted(
        await CompRunsRepository(aiopg_engine).list(
            never_scheduled=False, processed_since=SCHEDULER_INTERVAL
        ),
        key=lambda x: x.iteration,
    ) == sorted(comp_runs_marked_as_processed, key=lambda x: x.iteration)

    # now some of them were never processed (e.g. processed time is either null or before schedule time)
    comp_runs_waiting_for_processing_or_never_processed = random.sample(
        comp_runs_marked_as_processed, k=6
    )
    comp_runs_marked_as_processed = [
        r
        for r in comp_runs_marked_as_processed
        if r not in comp_runs_waiting_for_processing_or_never_processed
    ]
    # now we artificially change the processed time to be before the scheduled time
    comp_runs_waiting_for_processing_or_never_processed = cast(
        list[CompRunsAtDB],
        await asyncio.gather(
            *(
                CompRunsRepository(aiopg_engine).update(
                    user_id=comp_run.user_id,
                    project_id=comp_run.project_uuid,
                    iteration=comp_run.iteration,
                    scheduled=fake_processed_time,  # NOTE: we invert here the timings
                    processed=random.choice([fake_scheduled_time, None]),  # noqa: S311
                )
                for comp_run in comp_runs_waiting_for_processing_or_never_processed
            )
        ),
    )
    # so the processed ones shall remain
    assert sorted(
        await CompRunsRepository(aiopg_engine).list(
            never_scheduled=False, processed_since=SCHEDULER_INTERVAL
        ),
        key=lambda x: x.iteration,
    ) == sorted(comp_runs_marked_as_processed, key=lambda x: x.iteration)
    # the ones waiting for scheduling now
    assert sorted(
        await CompRunsRepository(aiopg_engine).list(
            never_scheduled=False, scheduled_since=SCHEDULER_INTERVAL
        ),
        key=lambda x: x.iteration,
    ) == sorted(
        comp_runs_waiting_for_processing_or_never_processed, key=lambda x: x.iteration
    )


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


async def test_set_run_result(
    aiopg_engine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
):
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
    assert created.result is not RunningState.PENDING
    assert created.ended is None

    updated = await CompRunsRepository(aiopg_engine).set_run_result(
        user_id=created.user_id,
        project_id=created.project_uuid,
        iteration=created.iteration,
        result_state=RunningState.PENDING,
        final_state=False,
    )
    assert updated
    assert updated != created
    assert updated.result is RunningState.PENDING
    assert updated.ended is None

    final_updated = await CompRunsRepository(aiopg_engine).set_run_result(
        user_id=created.user_id,
        project_id=created.project_uuid,
        iteration=created.iteration,
        result_state=RunningState.ABORTED,
        final_state=True,
    )
    assert final_updated
    assert final_updated != updated
    assert final_updated.result is RunningState.ABORTED
    assert final_updated.ended is not None


async def test_mark_for_cancellation(
    aiopg_engine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
):
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
    assert created.cancelled is None

    updated = await CompRunsRepository(aiopg_engine).mark_for_cancellation(
        user_id=created.user_id,
        project_id=created.project_uuid,
        iteration=created.iteration,
    )
    assert updated
    assert updated != created
    assert updated.cancelled is not None


async def test_mark_for_scheduling(
    aiopg_engine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
):
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
    assert created.scheduled is None
    assert created.processed is None

    updated = await CompRunsRepository(aiopg_engine).mark_for_scheduling(
        user_id=created.user_id,
        project_id=created.project_uuid,
        iteration=created.iteration,
    )
    assert updated
    assert updated != created
    assert updated.scheduled is not None
    assert updated.processed is None


async def test_mark_scheduling_done(
    aiopg_engine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
):
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
    assert created.scheduled is None
    assert created.processed is None

    updated = await CompRunsRepository(aiopg_engine).mark_as_processed(
        user_id=created.user_id,
        project_id=created.project_uuid,
        iteration=created.iteration,
    )
    assert updated
    assert updated != created
    assert updated.scheduled is None
    assert updated.processed is not None
