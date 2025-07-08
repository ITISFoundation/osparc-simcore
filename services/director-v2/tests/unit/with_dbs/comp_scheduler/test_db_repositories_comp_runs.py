# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import datetime
import random
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, cast

import arrow
import pytest
from _helpers import PublishedProject
from faker import Faker
from models_library.computations import CollectionRunID
from models_library.projects import ProjectID
from models_library.projects_state import RunningState
from models_library.users import UserID
from simcore_service_director_v2.core.errors import (
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
from sqlalchemy.ext.asyncio.engine import AsyncEngine

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
    sqlalchemy_async_engine: AsyncEngine,
    fake_user_id: UserID,
    fake_project_id: ProjectID,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    with_product: dict[str, Any],
):
    with pytest.raises(ComputationalRunNotFoundError):
        await CompRunsRepository(sqlalchemy_async_engine).get(
            fake_user_id, fake_project_id
        )

    published_project = await publish_project()
    assert published_project.project.prj_owner
    # there is still no comp run created
    with pytest.raises(ComputationalRunNotFoundError):
        await CompRunsRepository(sqlalchemy_async_engine).get(
            published_project.project.prj_owner, published_project.project.uuid
        )

    await create_comp_run(
        published_project.user,
        published_project.project,
        dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
    )
    comp_run_db = await CompRunsRepository(sqlalchemy_async_engine).get(
        published_project.project.prj_owner, published_project.project.uuid
    )
    assert (
        comp_run_db.dag_adjacency_list == published_project.pipeline.dag_adjacency_list
    )


async def test_list(
    sqlalchemy_async_engine: AsyncEngine,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    run_metadata: RunMetadataDict,
    faker: Faker,
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    assert await CompRunsRepository(sqlalchemy_async_engine).list_() == []

    published_project = await publish_project()
    assert await CompRunsRepository(sqlalchemy_async_engine).list_() == []

    created = await CompRunsRepository(sqlalchemy_async_engine).create(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
        collection_run_id=fake_collection_run_id,
    )
    assert await CompRunsRepository(sqlalchemy_async_engine).list_() == [created]

    created = [created] + await asyncio.gather(
        *(
            CompRunsRepository(sqlalchemy_async_engine).create(
                user_id=published_project.user["id"],
                project_id=published_project.project.uuid,
                iteration=created.iteration + n + 1,
                metadata=run_metadata,
                use_on_demand_clusters=faker.pybool(),
                dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
                collection_run_id=faker.uuid4(),
            )
            for n in range(50)
        )
    )
    assert sorted(
        await CompRunsRepository(sqlalchemy_async_engine).list_(),
        key=lambda x: x.iteration,
    ) == sorted(created, key=lambda x: x.iteration)

    # test with filter of state
    any_state_but_published = {
        s for s in RunningState if s is not RunningState.PUBLISHED
    }
    assert (
        await CompRunsRepository(sqlalchemy_async_engine).list_(
            filter_by_state=any_state_but_published
        )
        == []
    )
    assert sorted(
        await CompRunsRepository(sqlalchemy_async_engine).list_(
            filter_by_state={RunningState.PUBLISHED}
        ),
        key=lambda x: x.iteration,
    ) == sorted(created, key=lambda x: x.iteration)

    # test with never scheduled filter, let's create a bunch of scheduled entries,
    assert sorted(
        await CompRunsRepository(sqlalchemy_async_engine).list_(never_scheduled=True),
        key=lambda x: x.iteration,
    ) == sorted(created, key=lambda x: x.iteration)
    comp_runs_marked_for_scheduling = random.sample(created, k=25)
    await asyncio.gather(
        *(
            CompRunsRepository(sqlalchemy_async_engine).mark_for_scheduling(
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
        await CompRunsRepository(sqlalchemy_async_engine).list_(never_scheduled=True),
        key=lambda x: x.iteration,
    ) == sorted(created, key=lambda x: x.iteration)

    # now mark a few of them as processed
    comp_runs_marked_as_processed = random.sample(comp_runs_marked_for_scheduling, k=11)
    await asyncio.gather(
        *(
            CompRunsRepository(sqlalchemy_async_engine).mark_as_processed(
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
            await CompRunsRepository(sqlalchemy_async_engine).list_(
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
                    CompRunsRepository(sqlalchemy_async_engine).update(
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
        await CompRunsRepository(sqlalchemy_async_engine).list_(
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
                CompRunsRepository(sqlalchemy_async_engine).update(
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
        await CompRunsRepository(sqlalchemy_async_engine).list_(
            never_scheduled=False, processed_since=SCHEDULER_INTERVAL
        ),
        key=lambda x: x.iteration,
    ) == sorted(comp_runs_marked_as_processed, key=lambda x: x.iteration)
    # the ones waiting for scheduling now
    assert sorted(
        await CompRunsRepository(sqlalchemy_async_engine).list_(
            never_scheduled=False, scheduled_since=SCHEDULER_INTERVAL
        ),
        key=lambda x: x.iteration,
    ) == sorted(
        comp_runs_waiting_for_processing_or_never_processed, key=lambda x: x.iteration
    )


async def test_create(
    sqlalchemy_async_engine: AsyncEngine,
    fake_user_id: UserID,
    fake_project_id: ProjectID,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    with_product: dict[str, Any],
):
    with pytest.raises(ProjectNotFoundError):
        await CompRunsRepository(sqlalchemy_async_engine).create(
            user_id=fake_user_id,
            project_id=fake_project_id,
            iteration=None,
            metadata=run_metadata,
            use_on_demand_clusters=faker.pybool(),
            dag_adjacency_list={},
            collection_run_id=faker.uuid4(),
        )
    published_project = await publish_project()
    with pytest.raises(UserNotFoundError):
        await CompRunsRepository(sqlalchemy_async_engine).create(
            user_id=fake_user_id,
            project_id=published_project.project.uuid,
            iteration=None,
            metadata=run_metadata,
            use_on_demand_clusters=faker.pybool(),
            dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
            collection_run_id=faker.uuid4(),
        )

    created = await CompRunsRepository(sqlalchemy_async_engine).create(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
        collection_run_id=faker.uuid4(),
    )
    got = await CompRunsRepository(sqlalchemy_async_engine).get(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
    )
    assert created == got

    # creating a second one auto increment the iteration
    created = await CompRunsRepository(sqlalchemy_async_engine).create(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
        collection_run_id=faker.uuid4(),
    )
    assert created != got
    assert created.iteration == got.iteration + 1

    # getting without specifying the iteration returns the latest
    got = await CompRunsRepository(sqlalchemy_async_engine).get(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
    )
    assert created == got


async def test_update(
    sqlalchemy_async_engine: AsyncEngine,
    fake_user_id: UserID,
    fake_project_id: ProjectID,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    # this updates nothing but also does not complain
    updated = await CompRunsRepository(sqlalchemy_async_engine).update(
        fake_user_id, fake_project_id, faker.pyint(min_value=1)
    )
    assert updated is None
    # now let's create a valid one
    published_project = await publish_project()
    created = await CompRunsRepository(sqlalchemy_async_engine).create(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
        collection_run_id=fake_collection_run_id,
    )

    got = await CompRunsRepository(sqlalchemy_async_engine).get(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
    )
    assert created == got

    updated = await CompRunsRepository(sqlalchemy_async_engine).update(
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
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    published_project = await publish_project()
    created = await CompRunsRepository(sqlalchemy_async_engine).create(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
        collection_run_id=fake_collection_run_id,
    )
    got = await CompRunsRepository(sqlalchemy_async_engine).get(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
    )
    assert created == got
    assert created.result is not RunningState.PENDING
    assert created.ended is None

    updated = await CompRunsRepository(sqlalchemy_async_engine).set_run_result(
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

    final_updated = await CompRunsRepository(sqlalchemy_async_engine).set_run_result(
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
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    published_project = await publish_project()
    created = await CompRunsRepository(sqlalchemy_async_engine).create(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
        collection_run_id=fake_collection_run_id,
    )
    got = await CompRunsRepository(sqlalchemy_async_engine).get(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
    )
    assert created == got
    assert created.cancelled is None

    updated = await CompRunsRepository(sqlalchemy_async_engine).mark_for_cancellation(
        user_id=created.user_id,
        project_id=created.project_uuid,
        iteration=created.iteration,
    )
    assert updated
    assert updated != created
    assert updated.cancelled is not None


async def test_mark_for_scheduling(
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    published_project = await publish_project()
    created = await CompRunsRepository(sqlalchemy_async_engine).create(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
        collection_run_id=fake_collection_run_id,
    )
    got = await CompRunsRepository(sqlalchemy_async_engine).get(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
    )
    assert created == got
    assert created.scheduled is None
    assert created.processed is None

    updated = await CompRunsRepository(sqlalchemy_async_engine).mark_for_scheduling(
        user_id=created.user_id,
        project_id=created.project_uuid,
        iteration=created.iteration,
    )
    assert updated
    assert updated != created
    assert updated.scheduled is not None
    assert updated.processed is None


async def test_mark_scheduling_done(
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    published_project = await publish_project()
    created = await CompRunsRepository(sqlalchemy_async_engine).create(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
        collection_run_id=fake_collection_run_id,
    )
    got = await CompRunsRepository(sqlalchemy_async_engine).get(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
    )
    assert created == got
    assert created.scheduled is None
    assert created.processed is None

    updated = await CompRunsRepository(sqlalchemy_async_engine).mark_as_processed(
        user_id=created.user_id,
        project_id=created.project_uuid,
        iteration=created.iteration,
    )
    assert updated
    assert updated != created
    assert updated.scheduled is None
    assert updated.processed is not None


def _normalize_uuids(data):
    """Recursively convert UUID objects to strings in a nested dictionary."""
    if isinstance(data, dict):
        return {k: _normalize_uuids(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_normalize_uuids(i) for i in data]
    if isinstance(data, uuid.UUID):
        return str(data)
    return data


async def test_list_group_by_collection_run_id(
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    """Test list_group_by_collection_run_id function with simple data insertion and retrieval."""
    # Create a few published projects
    published_project_1 = await publish_project()
    published_project_2 = (
        await publish_project()
    )  # Create a shared collection run ID for grouping
    collection_run_id = fake_collection_run_id

    # Create computation runs with the same collection_run_id
    await asyncio.gather(
        CompRunsRepository(sqlalchemy_async_engine).create(
            user_id=published_project_1.user["id"],
            project_id=published_project_1.project.uuid,
            iteration=None,
            metadata=run_metadata,
            use_on_demand_clusters=faker.pybool(),
            dag_adjacency_list=published_project_1.pipeline.dag_adjacency_list,
            collection_run_id=collection_run_id,
        ),
        CompRunsRepository(sqlalchemy_async_engine).create(
            user_id=published_project_1.user["id"],
            project_id=published_project_2.project.uuid,
            iteration=None,
            metadata=run_metadata,
            use_on_demand_clusters=faker.pybool(),
            dag_adjacency_list=published_project_2.pipeline.dag_adjacency_list,
            collection_run_id=collection_run_id,
        ),
    )

    # Test the list_group_by_collection_run_id function
    total_count, items = await CompRunsRepository(
        sqlalchemy_async_engine
    ).list_group_by_collection_run_id(
        product_name=run_metadata.get("product_name"),
        user_id=published_project_1.user["id"],
        offset=0,
        limit=10,
    )

    # Assertions
    assert total_count == 1  # One collection group
    assert len(items) == 1

    collection_item = items[0]
    assert collection_item.collection_run_id == collection_run_id
    assert len(collection_item.project_ids) == 2  # Two projects in the collection
    assert str(published_project_1.project.uuid) in collection_item.project_ids
    assert str(published_project_2.project.uuid) in collection_item.project_ids
    assert (
        collection_item.state
        == RunningState.STARTED  # Initial state returned to activity overview
    )
    assert collection_item.info == _normalize_uuids(run_metadata)
    assert collection_item.submitted_at is not None
    assert collection_item.started_at is None  # Not started yet
    assert collection_item.ended_at is None  # Not ended yet


async def test_list_group_by_collection_run_id_with_mixed_states_returns_started(
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    """Test that if any state is not final, the grouped state returns STARTED."""
    # Create published projects
    published_project_1 = await publish_project()
    published_project_2 = await publish_project()
    published_project_3 = await publish_project()

    collection_run_id = fake_collection_run_id
    repo = CompRunsRepository(sqlalchemy_async_engine)

    # Create computation runs with same collection_run_id
    comp_run_1 = await repo.create(
        user_id=published_project_1.user["id"],
        project_id=published_project_1.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project_1.pipeline.dag_adjacency_list,
        collection_run_id=collection_run_id,
    )
    comp_run_2 = await repo.create(
        user_id=published_project_1.user["id"],
        project_id=published_project_2.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project_2.pipeline.dag_adjacency_list,
        collection_run_id=collection_run_id,
    )
    comp_run_3 = await repo.create(
        user_id=published_project_1.user["id"],
        project_id=published_project_3.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project_3.pipeline.dag_adjacency_list,
        collection_run_id=collection_run_id,
    )

    # Set mixed states: one SUCCESS (final), one FAILED (final), one STARTED (non-final)
    await repo.set_run_result(
        user_id=published_project_1.user["id"],
        project_id=published_project_1.project.uuid,
        iteration=comp_run_1.iteration,
        result_state=RunningState.SUCCESS,
        final_state=True,
    )
    await repo.set_run_result(
        user_id=published_project_1.user["id"],
        project_id=published_project_2.project.uuid,
        iteration=comp_run_2.iteration,
        result_state=RunningState.FAILED,
        final_state=True,
    )
    await repo.set_run_result(
        user_id=published_project_1.user["id"],
        project_id=published_project_3.project.uuid,
        iteration=comp_run_3.iteration,
        result_state=RunningState.STARTED,
        final_state=False,
    )

    # Test the list_group_by_collection_run_id function
    total_count, items = await repo.list_group_by_collection_run_id(
        product_name=run_metadata.get("product_name"),
        user_id=published_project_1.user["id"],
        offset=0,
        limit=10,
    )

    # Assertions
    assert total_count == 1
    assert len(items) == 1
    collection_item = items[0]
    assert collection_item.collection_run_id == collection_run_id
    assert collection_item.state == RunningState.STARTED  # Non-final state wins


async def test_list_group_by_collection_run_id_all_success_returns_success(
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    """Test that if all states are SUCCESS, the grouped state returns SUCCESS."""
    published_project_1 = await publish_project()
    published_project_2 = await publish_project()

    collection_run_id = fake_collection_run_id
    repo = CompRunsRepository(sqlalchemy_async_engine)

    # Create computation runs
    comp_run_1 = await repo.create(
        user_id=published_project_1.user["id"],
        project_id=published_project_1.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project_1.pipeline.dag_adjacency_list,
        collection_run_id=collection_run_id,
    )
    comp_run_2 = await repo.create(
        user_id=published_project_1.user["id"],
        project_id=published_project_2.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project_2.pipeline.dag_adjacency_list,
        collection_run_id=collection_run_id,
    )

    # Set both to SUCCESS
    await repo.set_run_result(
        user_id=published_project_1.user["id"],
        project_id=published_project_1.project.uuid,
        iteration=comp_run_1.iteration,
        result_state=RunningState.SUCCESS,
        final_state=True,
    )
    await repo.set_run_result(
        user_id=published_project_1.user["id"],
        project_id=published_project_2.project.uuid,
        iteration=comp_run_2.iteration,
        result_state=RunningState.SUCCESS,
        final_state=True,
    )

    # Test the function
    total_count, items = await repo.list_group_by_collection_run_id(
        product_name=run_metadata.get("product_name"),
        user_id=published_project_1.user["id"],
        offset=0,
        limit=10,
    )

    # Assertions
    assert total_count == 1
    assert len(items) == 1
    collection_item = items[0]
    assert collection_item.state == RunningState.SUCCESS


async def test_list_group_by_collection_run_id_with_failed_returns_failed(
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    """Test that if any state is FAILED (among final states), the grouped state returns FAILED."""
    published_project_1 = await publish_project()
    published_project_2 = await publish_project()
    published_project_3 = await publish_project()

    collection_run_id = fake_collection_run_id
    repo = CompRunsRepository(sqlalchemy_async_engine)

    # Create computation runs
    comp_runs = []
    for project in [published_project_1, published_project_2, published_project_3]:
        comp_run = await repo.create(
            user_id=published_project_1.user["id"],
            project_id=project.project.uuid,
            iteration=None,
            metadata=run_metadata,
            use_on_demand_clusters=faker.pybool(),
            dag_adjacency_list=project.pipeline.dag_adjacency_list,
            collection_run_id=collection_run_id,
        )
        comp_runs.append((project, comp_run))

    # Set states: SUCCESS, FAILED, ABORTED (all final states, but FAILED is present)
    await repo.set_run_result(
        user_id=published_project_1.user["id"],
        project_id=comp_runs[0][0].project.uuid,
        iteration=comp_runs[0][1].iteration,
        result_state=RunningState.SUCCESS,
        final_state=True,
    )
    await repo.set_run_result(
        user_id=published_project_1.user["id"],
        project_id=comp_runs[1][0].project.uuid,
        iteration=comp_runs[1][1].iteration,
        result_state=RunningState.FAILED,
        final_state=True,
    )
    await repo.set_run_result(
        user_id=published_project_1.user["id"],
        project_id=comp_runs[2][0].project.uuid,
        iteration=comp_runs[2][1].iteration,
        result_state=RunningState.ABORTED,
        final_state=True,
    )

    # Test the function
    total_count, items = await repo.list_group_by_collection_run_id(
        product_name=run_metadata.get("product_name"),
        user_id=published_project_1.user["id"],
        offset=0,
        limit=10,
    )

    # Assertions
    assert total_count == 1
    assert len(items) == 1
    collection_item = items[0]
    assert collection_item.state == RunningState.FAILED  # FAILED takes precedence


async def test_list_group_by_collection_run_id_with_aborted_returns_aborted(
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    """Test that if any state is ABORTED (but no FAILED), the grouped state returns ABORTED."""
    published_project_1 = await publish_project()
    published_project_2 = await publish_project()

    collection_run_id = fake_collection_run_id
    repo = CompRunsRepository(sqlalchemy_async_engine)

    # Create computation runs
    comp_run_1 = await repo.create(
        user_id=published_project_1.user["id"],
        project_id=published_project_1.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project_1.pipeline.dag_adjacency_list,
        collection_run_id=collection_run_id,
    )
    comp_run_2 = await repo.create(
        user_id=published_project_1.user["id"],
        project_id=published_project_2.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project_2.pipeline.dag_adjacency_list,
        collection_run_id=collection_run_id,
    )

    # Set states: SUCCESS, ABORTED (final states, no FAILED)
    await repo.set_run_result(
        user_id=published_project_1.user["id"],
        project_id=published_project_1.project.uuid,
        iteration=comp_run_1.iteration,
        result_state=RunningState.SUCCESS,
        final_state=True,
    )
    await repo.set_run_result(
        user_id=published_project_1.user["id"],
        project_id=published_project_2.project.uuid,
        iteration=comp_run_2.iteration,
        result_state=RunningState.ABORTED,
        final_state=True,
    )

    # Test the function
    total_count, items = await repo.list_group_by_collection_run_id(
        product_name=run_metadata.get("product_name"),
        user_id=published_project_1.user["id"],
        offset=0,
        limit=10,
    )

    # Assertions
    assert total_count == 1
    assert len(items) == 1
    collection_item = items[0]
    assert collection_item.state == RunningState.ABORTED


async def test_list_group_by_collection_run_id_with_unknown_returns_unknown(
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    """Test that if any state is UNKNOWN (but no FAILED/ABORTED), the grouped state returns UNKNOWN."""
    published_project_1 = await publish_project()
    published_project_2 = await publish_project()

    collection_run_id = fake_collection_run_id
    repo = CompRunsRepository(sqlalchemy_async_engine)

    # Create computation runs
    comp_run_1 = await repo.create(
        user_id=published_project_1.user["id"],
        project_id=published_project_1.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project_1.pipeline.dag_adjacency_list,
        collection_run_id=collection_run_id,
    )
    comp_run_2 = await repo.create(
        user_id=published_project_1.user["id"],
        project_id=published_project_2.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project_2.pipeline.dag_adjacency_list,
        collection_run_id=collection_run_id,
    )

    # Set states: SUCCESS, UNKNOWN (final states, no FAILED/ABORTED)
    await repo.set_run_result(
        user_id=published_project_1.user["id"],
        project_id=published_project_1.project.uuid,
        iteration=comp_run_1.iteration,
        result_state=RunningState.SUCCESS,
        final_state=True,
    )
    await repo.set_run_result(
        user_id=published_project_1.user["id"],
        project_id=published_project_2.project.uuid,
        iteration=comp_run_2.iteration,
        result_state=RunningState.UNKNOWN,  # --> is setup to be FAILED
        final_state=True,
    )

    # Test the function
    total_count, items = await repo.list_group_by_collection_run_id(
        product_name=run_metadata.get("product_name"),
        user_id=published_project_1.user["id"],
        offset=0,
        limit=10,
    )

    # Assertions
    assert total_count == 1
    assert len(items) == 1
    collection_item = items[0]
    assert collection_item.state == RunningState.FAILED


async def test_list_group_by_collection_run_id_with_project_filter(
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    with_product: dict[str, Any],
):
    """Test list_group_by_collection_run_id with project_ids filter."""
    published_project_1 = await publish_project()
    published_project_2 = await publish_project()
    published_project_3 = await publish_project()

    collection_run_id_1 = CollectionRunID(f"{faker.uuid4(cast_to=None)}")
    collection_run_id_2 = CollectionRunID(f"{faker.uuid4(cast_to=None)}")
    repo = CompRunsRepository(sqlalchemy_async_engine)

    # Create computation runs with different collection_run_ids
    await repo.create(
        user_id=published_project_1.user["id"],
        project_id=published_project_1.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project_1.pipeline.dag_adjacency_list,
        collection_run_id=collection_run_id_1,
    )
    await repo.create(
        user_id=published_project_1.user["id"],
        project_id=published_project_2.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project_2.pipeline.dag_adjacency_list,
        collection_run_id=collection_run_id_1,
    )
    await repo.create(
        user_id=published_project_1.user["id"],
        project_id=published_project_3.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project_3.pipeline.dag_adjacency_list,
        collection_run_id=collection_run_id_2,
    )

    # Test with project filter for only first two projects
    total_count, items = await repo.list_group_by_collection_run_id(
        product_name=run_metadata.get("product_name"),
        user_id=published_project_1.user["id"],
        project_ids=[
            published_project_1.project.uuid,
            published_project_2.project.uuid,
        ],
        offset=0,
        limit=10,
    )

    # Should only return collection_run_id_1
    assert total_count == 1
    assert len(items) == 1
    collection_item = items[0]
    assert collection_item.collection_run_id == collection_run_id_1
    assert len(collection_item.project_ids) == 2


async def test_list_group_by_collection_run_id_pagination(
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    with_product: dict[str, Any],
):
    """Test pagination functionality of list_group_by_collection_run_id."""
    published_project = await publish_project()
    repo = CompRunsRepository(sqlalchemy_async_engine)

    # Create multiple collection runs
    collection_run_ids = []
    for _ in range(5):
        collection_run_id = CollectionRunID(f"{faker.uuid4(cast_to=None)}")
        collection_run_ids.append(collection_run_id)

        project = await publish_project()
        await repo.create(
            user_id=published_project.user["id"],
            project_id=project.project.uuid,
            iteration=None,
            metadata=run_metadata,
            use_on_demand_clusters=faker.pybool(),
            dag_adjacency_list=project.pipeline.dag_adjacency_list,
            collection_run_id=collection_run_id,
        )

    # Test first page
    total_count, items = await repo.list_group_by_collection_run_id(
        product_name=run_metadata.get("product_name"),
        user_id=published_project.user["id"],
        offset=0,
        limit=2,
    )

    assert total_count == 5
    assert len(items) == 2

    # Test second page
    total_count, items = await repo.list_group_by_collection_run_id(
        product_name=run_metadata.get("product_name"),
        user_id=published_project.user["id"],
        offset=2,
        limit=2,
    )

    assert total_count == 5
    assert len(items) == 2

    # Test last page
    total_count, items = await repo.list_group_by_collection_run_id(
        product_name=run_metadata.get("product_name"),
        user_id=published_project.user["id"],
        offset=4,
        limit=2,
    )

    assert total_count == 5
    assert len(items) == 1


async def test_list_group_by_collection_run_id_empty_result(
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    fake_user_id: UserID,
    with_product: dict[str, Any],
):
    """Test list_group_by_collection_run_id returns empty when no runs exist."""
    repo = CompRunsRepository(sqlalchemy_async_engine)

    total_count, items = await repo.list_group_by_collection_run_id(
        product_name=run_metadata.get("product_name"),
        user_id=fake_user_id,
        offset=0,
        limit=10,
    )

    assert total_count == 0
    assert len(items) == 0


async def test_list_group_by_collection_run_id_with_different_users(
    sqlalchemy_async_engine: AsyncEngine,
    create_registered_user: Callable[..., dict[str, Any]],
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    with_product: dict[str, Any],
):
    """Test that list_group_by_collection_run_id filters by user_id correctly."""
    published_project_user1 = await publish_project()
    published_project_user2 = await publish_project()

    user1 = create_registered_user()
    user2 = create_registered_user()

    collection_run_id_1 = CollectionRunID(f"{faker.uuid4(cast_to=None)}")
    collection_run_id_2 = CollectionRunID(f"{faker.uuid4(cast_to=None)}")

    repo = CompRunsRepository(sqlalchemy_async_engine)

    # Create runs for different users with same collection_run_id
    await repo.create(
        user_id=user1["id"],
        project_id=published_project_user1.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project_user1.pipeline.dag_adjacency_list,
        collection_run_id=collection_run_id_1,
    )
    await repo.create(
        user_id=user2["id"],
        project_id=published_project_user2.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project_user2.pipeline.dag_adjacency_list,
        collection_run_id=collection_run_id_2,
    )

    # Test for user1 - should only see their own runs
    total_count, items = await repo.list_group_by_collection_run_id(
        product_name=run_metadata.get("product_name"),
        user_id=user1["id"],
        offset=0,
        limit=10,
    )

    assert total_count == 1
    assert len(items) == 1
    collection_item = items[0]
    assert len(collection_item.project_ids) == 1
    assert str(published_project_user1.project.uuid) in collection_item.project_ids
    assert str(published_project_user2.project.uuid) not in collection_item.project_ids

    # Test for user2 - should only see their own runs
    total_count, items = await repo.list_group_by_collection_run_id(
        product_name=run_metadata.get("product_name"),
        user_id=user2["id"],
        offset=0,
        limit=10,
    )

    assert total_count == 1
    assert len(items) == 1
    collection_item = items[0]
    assert len(collection_item.project_ids) == 1
    assert str(published_project_user2.project.uuid) in collection_item.project_ids
    assert str(published_project_user1.project.uuid) not in collection_item.project_ids


async def test_list_group_by_collection_run_id_state_priority_precedence(
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    """Test that state resolution follows correct priority: FAILED > ABORTED > UNKNOWN."""
    published_projects = [await publish_project() for _ in range(4)]

    collection_run_id = fake_collection_run_id
    repo = CompRunsRepository(sqlalchemy_async_engine)

    # Create computation runs
    comp_runs = []
    for project in published_projects:
        comp_run = await repo.create(
            user_id=published_projects[0].user["id"],
            project_id=project.project.uuid,
            iteration=None,
            metadata=run_metadata,
            use_on_demand_clusters=faker.pybool(),
            dag_adjacency_list=project.pipeline.dag_adjacency_list,
            collection_run_id=collection_run_id,
        )
        comp_runs.append((project, comp_run))

    # Set states: SUCCESS, UNKNOWN, ABORTED, FAILED - should return FAILED
    states = [
        RunningState.SUCCESS,
        RunningState.UNKNOWN,
        RunningState.ABORTED,
        RunningState.FAILED,
    ]
    for i, (project, comp_run) in enumerate(comp_runs):
        await repo.set_run_result(
            user_id=published_projects[0].user["id"],
            project_id=project.project.uuid,
            iteration=comp_run.iteration,
            result_state=states[i],
            final_state=True,
        )

    # Test the function
    total_count, items = await repo.list_group_by_collection_run_id(
        product_name=run_metadata.get("product_name"),
        user_id=published_projects[0].user["id"],
        offset=0,
        limit=10,
    )

    # Assertions - FAILED should have highest priority
    assert total_count == 1
    assert len(items) == 1
    collection_item = items[0]
    assert collection_item.state == RunningState.FAILED


async def test_get_latest_run_by_project(
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    faker: Faker,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    create_registered_user: Callable[..., dict[str, Any]],
):
    """Test that get() with user_id=None retrieves the latest run regardless of user"""
    published_project = await publish_project()

    # Create a second user
    second_user = create_registered_user()

    # Create comp runs for the original user
    comp_run_user1_iter1 = await CompRunsRepository(sqlalchemy_async_engine).create(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
        collection_run_id=CollectionRunID(faker.uuid4()),
    )

    # Create comp runs for the second user (this should increment iteration)
    comp_run_user2_iter2 = await CompRunsRepository(sqlalchemy_async_engine).create(
        user_id=second_user["id"],
        project_id=published_project.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
        collection_run_id=CollectionRunID(faker.uuid4()),
    )

    # Create another run for the first user (should be iteration 3)
    comp_run_user1_iter3 = await CompRunsRepository(sqlalchemy_async_engine).create(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
        iteration=None,
        metadata=run_metadata,
        use_on_demand_clusters=faker.pybool(),
        dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
        collection_run_id=CollectionRunID(faker.uuid4()),
    )

    # Verify iterations are correct
    assert comp_run_user1_iter1.iteration == 1
    assert comp_run_user2_iter2.iteration == 1
    assert comp_run_user1_iter3.iteration == 2

    # Test get with user_id=None should return the latest run (highest iteration)
    latest_run = await CompRunsRepository(
        sqlalchemy_async_engine
    ).get_latest_run_by_project(
        project_id=published_project.project.uuid,
    )
    assert latest_run == comp_run_user1_iter3
    assert latest_run.iteration == 2

    # Test get with specific user_id still works
    user1_latest = await CompRunsRepository(sqlalchemy_async_engine).get(
        user_id=published_project.user["id"],
        project_id=published_project.project.uuid,
    )
    assert user1_latest == comp_run_user1_iter3

    user2_latest = await CompRunsRepository(sqlalchemy_async_engine).get(
        user_id=second_user["id"],
        project_id=published_project.project.uuid,
    )
    assert user2_latest == comp_run_user2_iter2
