# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import Awaitable, Callable
from typing import Any

from _helpers import PublishedProject
from models_library.computations import CollectionRunID
from models_library.products import ProductName
from simcore_service_director_v2.models.comp_run_snapshot_tasks import (
    CompRunSnapshotTaskDBGet,
)
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB
from simcore_service_director_v2.modules.db.repositories.comp_runs_snapshot_tasks import (
    CompRunsSnapshotTasksRepository,
)
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_list_computation_collection_run_tasks(
    sqlalchemy_async_engine: AsyncEngine,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    create_comp_run_snapshot_tasks: Callable[
        ..., Awaitable[list[CompRunSnapshotTaskDBGet]]
    ],
    osparc_product_name: ProductName,
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    repo = CompRunsSnapshotTasksRepository(db_engine=sqlalchemy_async_engine)

    # 1. create a project
    published_project = await publish_project()
    user_id = published_project.user["id"]

    # 2. create a comp_run
    run = await create_comp_run(
        published_project.user,
        published_project.project,
        dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
        collection_run_id=f"{fake_collection_run_id}",
    )

    # 3. create snapshot tasks for that run
    snapshot_tasks = await create_comp_run_snapshot_tasks(
        user=published_project.user,
        project=published_project.project,
        run_id=run.run_id,
    )

    # 4. list them
    total_count, tasks = await repo.list_computation_collection_run_tasks(
        product_name=osparc_product_name,
        user_id=user_id,
        collection_run_id=fake_collection_run_id,
    )

    assert total_count == len(snapshot_tasks)
    assert tasks
    assert len(tasks) == len(snapshot_tasks)
    assert {t.snapshot_task_id for t in tasks} == {
        t.snapshot_task_id for t in snapshot_tasks
    }


async def test_list_computation_collection_run_tasks_empty(
    sqlalchemy_async_engine: AsyncEngine,
    osparc_product_name: ProductName,
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    repo = CompRunsSnapshotTasksRepository(db_engine=sqlalchemy_async_engine)
    # Use a random user_id unlikely to have tasks
    user_id = 999999
    total_count, tasks = await repo.list_computation_collection_run_tasks(
        product_name=osparc_product_name,
        user_id=user_id,
        collection_run_id=fake_collection_run_id,
    )
    assert total_count == 0
    assert tasks == []


async def test_list_computation_collection_run_tasks_pagination(
    sqlalchemy_async_engine: AsyncEngine,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    create_comp_run_snapshot_tasks: Callable[
        ..., Awaitable[list[CompRunSnapshotTaskDBGet]]
    ],
    osparc_product_name: ProductName,
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    repo = CompRunsSnapshotTasksRepository(db_engine=sqlalchemy_async_engine)
    published_project = await publish_project()
    user_id = published_project.user["id"]
    run = await create_comp_run(
        published_project.user,
        published_project.project,
        dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
        collection_run_id=f"{fake_collection_run_id}",
    )
    snapshot_tasks = await create_comp_run_snapshot_tasks(
        user=published_project.user,
        project=published_project.project,
        run_id=run.run_id,
    )
    # Test pagination: limit=1
    total_count, tasks = await repo.list_computation_collection_run_tasks(
        product_name=osparc_product_name,
        user_id=user_id,
        collection_run_id=fake_collection_run_id,
        limit=1,
        offset=0,
    )
    assert total_count == len(snapshot_tasks)
    assert len(tasks) == 1
    # Test pagination: offset=1
    _, tasks_offset = await repo.list_computation_collection_run_tasks(
        product_name=osparc_product_name,
        user_id=user_id,
        collection_run_id=fake_collection_run_id,
        limit=1,
        offset=1,
    )
    assert len(tasks_offset) == 1 or (
        len(snapshot_tasks) == 1 and len(tasks_offset) == 0
    )


async def test_list_computation_collection_run_tasks_wrong_user(
    sqlalchemy_async_engine: AsyncEngine,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    create_comp_run_snapshot_tasks: Callable[
        ..., Awaitable[list[CompRunSnapshotTaskDBGet]]
    ],
    osparc_product_name: ProductName,
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    repo = CompRunsSnapshotTasksRepository(db_engine=sqlalchemy_async_engine)
    published_project = await publish_project()
    run = await create_comp_run(
        published_project.user,
        published_project.project,
        dag_adjacency_list=published_project.pipeline.dag_adjacency_list,
        collection_run_id=f"{fake_collection_run_id}",
    )
    await create_comp_run_snapshot_tasks(
        user=published_project.user,
        project=published_project.project,
        run_id=run.run_id,
    )
    # Use a different user_id
    wrong_user_id = 123456789
    total_count, tasks = await repo.list_computation_collection_run_tasks(
        product_name=osparc_product_name,
        user_id=wrong_user_id,
        collection_run_id=fake_collection_run_id,
    )
    assert total_count == 0
    assert tasks == []


async def test_list_computation_collection_run_tasks_multiple_comp_runs_same_collection(
    sqlalchemy_async_engine: AsyncEngine,
    publish_project: Callable[[], Awaitable[PublishedProject]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    create_comp_run_snapshot_tasks: Callable[
        ..., Awaitable[list[CompRunSnapshotTaskDBGet]]
    ],
    osparc_product_name: ProductName,
    fake_collection_run_id: CollectionRunID,
    with_product: dict[str, Any],
):
    repo = CompRunsSnapshotTasksRepository(db_engine=sqlalchemy_async_engine)
    published_project1 = await publish_project()
    published_project2 = await publish_project()
    published_project3 = await publish_project()
    user_id = published_project1.user["id"]

    # Create 3 comp_runs, 2 with the same collection_run_id, 1 with a different one
    run1 = await create_comp_run(
        published_project1.user,
        published_project1.project,
        dag_adjacency_list=published_project1.pipeline.dag_adjacency_list,
        collection_run_id=f"{fake_collection_run_id}",
    )
    run2 = await create_comp_run(
        published_project2.user,
        published_project2.project,
        dag_adjacency_list=published_project2.pipeline.dag_adjacency_list,
        collection_run_id=f"{fake_collection_run_id}",
    )
    other_collection_run_id = CollectionRunID("00000000-0000-0000-0000-000000000001")
    run3 = await create_comp_run(
        published_project3.user,
        published_project3.project,
        dag_adjacency_list=published_project3.pipeline.dag_adjacency_list,
        collection_run_id=f"{other_collection_run_id}",
    )

    # Create snapshot tasks for each run
    tasks_run1 = await create_comp_run_snapshot_tasks(
        user=published_project1.user,
        project=published_project1.project,
        run_id=run1.run_id,
    )
    tasks_run2 = await create_comp_run_snapshot_tasks(
        user=published_project2.user,
        project=published_project2.project,
        run_id=run2.run_id,
    )
    tasks_run3 = await create_comp_run_snapshot_tasks(
        user=published_project3.user,
        project=published_project3.project,
        run_id=run3.run_id,
    )

    # Query for tasks with the shared collection_run_id
    total_count, tasks = await repo.list_computation_collection_run_tasks(
        product_name=osparc_product_name,
        user_id=user_id,
        collection_run_id=fake_collection_run_id,
    )
    expected_task_ids = {t.snapshot_task_id for t in tasks_run1 + tasks_run2}
    actual_task_ids = {t.snapshot_task_id for t in tasks}
    assert total_count == len(expected_task_ids)
    assert actual_task_ids == expected_task_ids
    # Ensure tasks from run3 are not included
    assert not any(
        t.snapshot_task_id in {tt.snapshot_task_id for tt in tasks_run3} for t in tasks
    )
