# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-positional-arguments

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from faker import Faker
from models_library.api_schemas_directorv2.comp_runs import (
    ComputationCollectionRunRpcGetPage,
    ComputationCollectionRunTaskRpcGetPage,
    ComputationRunRpcGetPage,
    ComputationTaskRpcGetPage,
)
from models_library.computations import CollectionRunID
from models_library.projects import ProjectAtDB
from models_library.projects_state import RunningState
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.director_v2 import (
    computations as rpc_computations,
)
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_run_snapshot_tasks import (
    CompRunSnapshotTaskDBGet,
)
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_rpc_list_computation_runs_and_tasks(
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks_from_project: Callable[..., Awaitable[list[CompTaskAtDB]]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    rpc_client: RabbitMQRPCClient,
    with_product: dict[str, Any],
):
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    await create_pipeline(
        project_id=f"{proj.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    comp_tasks = await create_tasks_from_project(
        user=user, project=proj, state=StateType.PUBLISHED, progress=None
    )
    comp_runs = await create_comp_run(
        user=user,
        project=proj,
        result=RunningState.PUBLISHED,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    assert comp_runs

    output = await rpc_computations.list_computations_latest_iteration_page(
        rpc_client, product_name="osparc", user_id=user["id"]
    )
    assert output.total == 1
    assert isinstance(output, ComputationRunRpcGetPage)
    assert output.items[0].iteration == 1

    comp_runs_2 = await create_comp_run(
        user=user,
        project=proj,
        result=RunningState.PENDING,
        started=datetime.now(tz=UTC),
        iteration=2,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    output = await rpc_computations.list_computations_latest_iteration_page(
        rpc_client, product_name="osparc", user_id=user["id"]
    )
    assert output.total == 1
    assert isinstance(output, ComputationRunRpcGetPage)
    assert output.items[0].iteration == 2
    assert output.items[0].started_at is not None
    assert output.items[0].ended_at is None

    comp_runs_3 = await create_comp_run(
        user=user,
        project=proj,
        result=RunningState.SUCCESS,
        started=datetime.now(tz=UTC),
        ended=datetime.now(tz=UTC),
        iteration=3,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    output = await rpc_computations.list_computations_latest_iteration_page(
        rpc_client, product_name="osparc", user_id=user["id"]
    )
    assert output.total == 1
    assert isinstance(output, ComputationRunRpcGetPage)
    assert output.items[0].iteration == 3
    assert output.items[0].ended_at is not None

    # Tasks

    output = await rpc_computations.list_computations_latest_iteration_tasks_page(
        rpc_client, product_name="osparc", user_id=user["id"], project_ids=[proj.uuid]
    )
    assert output
    assert output.total == 4
    assert isinstance(output, ComputationTaskRpcGetPage)
    assert len(output.items) == 4


async def test_rpc_list_computation_runs_with_filtering(
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks_from_project: Callable[..., Awaitable[list[CompTaskAtDB]]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    rpc_client: RabbitMQRPCClient,
    with_product: dict[str, Any],
):
    user = create_registered_user()

    proj_1 = await create_project(user, workbench=fake_workbench_without_outputs)
    await create_pipeline(
        project_id=f"{proj_1.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    comp_tasks = await create_tasks_from_project(
        user=user, project=proj_1, state=StateType.PUBLISHED, progress=None
    )
    comp_runs = await create_comp_run(
        user=user,
        project=proj_1,
        result=RunningState.PUBLISHED,
        dag_adjacency_list=fake_workbench_adjacency,
    )

    proj_2 = await create_project(user, workbench=fake_workbench_without_outputs)
    await create_pipeline(
        project_id=f"{proj_2.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    comp_tasks = await create_tasks_from_project(
        user=user, project=proj_2, state=StateType.SUCCESS, progress=None
    )
    comp_runs = await create_comp_run(
        user=user,
        project=proj_2,
        result=RunningState.SUCCESS,
        dag_adjacency_list=fake_workbench_adjacency,
    )

    # Test default behaviour `filter_only_running=False`
    output = await rpc_computations.list_computations_latest_iteration_page(
        rpc_client, product_name="osparc", user_id=user["id"]
    )
    assert output.total == 2

    # Test filtering
    output = await rpc_computations.list_computations_latest_iteration_page(
        rpc_client, product_name="osparc", user_id=user["id"], filter_only_running=True
    )
    assert output.total == 1
    assert output.items[0].project_uuid == proj_1.uuid


async def test_rpc_list_computation_runs_history(
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks_from_project: Callable[..., Awaitable[list[CompTaskAtDB]]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    rpc_client: RabbitMQRPCClient,
    with_product: dict[str, Any],
):
    user = create_registered_user()

    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    await create_pipeline(
        project_id=f"{proj.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    comp_tasks = await create_tasks_from_project(
        user=user, project=proj, state=StateType.PUBLISHED, progress=None
    )
    assert comp_tasks
    comp_runs_1 = await create_comp_run(
        user=user,
        project=proj,
        result=RunningState.SUCCESS,
        started=datetime.now(tz=UTC) - timedelta(minutes=120),
        ended=datetime.now(tz=UTC) - timedelta(minutes=100),
        iteration=1,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    assert comp_runs_1
    comp_runs_2 = await create_comp_run(
        user=user,
        project=proj,
        result=RunningState.SUCCESS,
        started=datetime.now(tz=UTC) - timedelta(minutes=90),
        ended=datetime.now(tz=UTC) - timedelta(minutes=60),
        iteration=2,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    assert comp_runs_2
    comp_runs_3 = await create_comp_run(
        user=user,
        project=proj,
        result=RunningState.FAILED,
        started=datetime.now(tz=UTC) - timedelta(minutes=50),
        ended=datetime.now(tz=UTC),
        iteration=3,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    assert comp_runs_3

    output = await rpc_computations.list_computations_iterations_page(
        rpc_client, product_name="osparc", user_id=user["id"], project_ids=[proj.uuid]
    )
    assert output.total == 3
    assert isinstance(output, ComputationRunRpcGetPage)


async def test_rpc_list_computation_collection_runs_page_and_collection_run_tasks_page(
    fake_workbench_without_outputs: dict[str, Any],  # <-- Has 4 nodes
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks_from_project: Callable[..., Awaitable[list[CompTaskAtDB]]],
    create_comp_run_snapshot_tasks: Callable[
        ..., Awaitable[list[CompRunSnapshotTaskDBGet]]
    ],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    rpc_client: RabbitMQRPCClient,
    faker: Faker,
    with_product: dict[str, Any],
):
    user = create_registered_user()
    projects = [
        await create_project(user, workbench=fake_workbench_without_outputs)
        for _ in range(3)
    ]

    default_collection_run_id = CollectionRunID(f"{faker.uuid4(cast_to=None)}")
    not_default_collection_run_id = CollectionRunID(f"{faker.uuid4(cast_to=None)}")

    collection_run_id_project_list = [
        default_collection_run_id,
        default_collection_run_id,
        not_default_collection_run_id,
    ]

    running_state_project_list = [
        RunningState.SUCCESS,
        RunningState.PENDING,
        RunningState.SUCCESS,
    ]

    for proj, collection_run_id, running_state in zip(
        projects,
        collection_run_id_project_list,
        running_state_project_list,
        strict=True,
    ):
        await create_pipeline(
            project_id=f"{proj.uuid}",
            dag_adjacency_list=fake_workbench_adjacency,
        )
        await create_tasks_from_project(
            user=user, project=proj, state=running_state, progress=None
        )
        run = await create_comp_run(
            user=user,
            project=proj,
            result=running_state,
            started=datetime.now(tz=UTC) - timedelta(minutes=120),
            ended=datetime.now(tz=UTC) - timedelta(minutes=100),
            iteration=1,
            dag_adjacency_list=fake_workbench_adjacency,
            collection_run_id=f"{collection_run_id}",
        )
        await create_comp_run_snapshot_tasks(
            user=user,
            project=proj,
            run_id=run.run_id,
        )

    output = await rpc_computations.list_computation_collection_runs_page(
        rpc_client, product_name="osparc", user_id=user["id"], project_ids=None
    )
    assert output.total == 2
    assert len(output.items) == 2
    assert isinstance(output, ComputationCollectionRunRpcGetPage)
    assert len(output.items[0].project_ids) == 1
    assert len(output.items[1].project_ids) == 2

    output = await rpc_computations.list_computation_collection_run_tasks_page(
        rpc_client,
        product_name="osparc",
        user_id=user["id"],
        collection_run_id=default_collection_run_id,
    )
    assert output.total == 8
    assert len(output.items) == 8
    isinstance(output, ComputationCollectionRunTaskRpcGetPage)

    output = await rpc_computations.list_computation_collection_run_tasks_page(
        rpc_client,
        product_name="osparc",
        user_id=user["id"],
        collection_run_id=not_default_collection_run_id,
    )
    assert output.total == 4
    assert len(output.items) == 4
    isinstance(output, ComputationCollectionRunTaskRpcGetPage)

    # Test filtering only running collection runs
    output = await rpc_computations.list_computation_collection_runs_page(
        rpc_client,
        product_name="osparc",
        user_id=user["id"],
        project_ids=None,
        filter_only_running=True,  # <-- This is the tested filter
    )
    assert output.total == 1
    assert len(output.items) == 1
    assert isinstance(output, ComputationCollectionRunRpcGetPage)
    assert len(output.items[0].project_ids) == 2


async def test_rpc_list_computation_collection_runs_empty_ids_when_user_has_already_run_history(
    fake_workbench_without_outputs: dict[str, Any],  # <-- Has 4 nodes
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks_from_project: Callable[..., Awaitable[list[CompTaskAtDB]]],
    create_comp_run_snapshot_tasks: Callable[
        ..., Awaitable[list[CompRunSnapshotTaskDBGet]]
    ],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    rpc_client: RabbitMQRPCClient,
    faker: Faker,
    with_product: dict[str, Any],
):
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)

    await create_pipeline(
        project_id=f"{proj.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    await create_tasks_from_project(
        user=user, project=proj, state=RunningState.SUCCESS, progress=None
    )
    run = await create_comp_run(
        user=user,
        project=proj,
        result=RunningState.SUCCESS,
        started=datetime.now(tz=UTC) - timedelta(minutes=120),
        ended=datetime.now(tz=UTC) - timedelta(minutes=100),
        iteration=1,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    await create_comp_run_snapshot_tasks(
        user=user,
        project=proj,
        run_id=run.run_id,
    )

    output = await rpc_computations.list_computation_collection_runs_page(
        rpc_client, product_name="osparc", user_id=user["id"], project_ids=None
    )
    assert output.total == 1
    assert len(output.items) == 1
    assert isinstance(output, ComputationCollectionRunRpcGetPage)

    # Test filtering only running collection runs
    output = await rpc_computations.list_computation_collection_runs_page(
        rpc_client,
        product_name="osparc",
        user_id=user["id"],
        project_ids=None,
        filter_only_running=True,  # <-- This is the tested filter
    )
    assert output.total == 0
    assert len(output.items) == 0


async def test_rpc_list_computation_collection_runs_empty_ids_when_user_do_not_have_run_history(
    create_registered_user: Callable[..., dict[str, Any]],
    rpc_client: RabbitMQRPCClient,
    with_product: dict[str, Any],
):
    user = create_registered_user()

    # Test with empty collection_run_ids
    output = await rpc_computations.list_computation_collection_runs_page(
        rpc_client,
        product_name="osparc",
        user_id=user["id"],
        project_ids=None,
        filter_only_running=True,  # This will result in empty collection_run_ids
    )
    assert output.total == 0
    assert len(output.items) == 0
    assert isinstance(output, ComputationCollectionRunRpcGetPage)
