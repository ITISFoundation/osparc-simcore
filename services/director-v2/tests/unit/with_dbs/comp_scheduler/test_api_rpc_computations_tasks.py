from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from faker import Faker
from models_library.api_schemas_directorv2.computations import TaskLogFileIdGet
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_state import RunningState
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.director_v2 import (
    computations_tasks as rpc_computations_tasks,
)
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_service_director_v2.api.errors.rpc_error import (
    ComputationalTaskMissingError,
)
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB

_faker = Faker()

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_get_computation_task_log_file_ids(
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks: Callable[..., Awaitable[list[CompTaskAtDB]]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    rpc_client: RabbitMQRPCClient,
):
    user = create_registered_user()
    proj = await project(user, workbench=fake_workbench_without_outputs)
    await create_pipeline(
        project_id=f"{proj.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    comp_tasks = await create_tasks(
        user=user, project=proj, state=StateType.PUBLISHED, progress=None
    )
    comp_runs = await create_comp_run(
        user=user,
        project=proj,
        result=RunningState.PUBLISHED,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    assert comp_runs

    output = await rpc_computations_tasks.get_computation_task_log_file_ids(
        rpc_client, project_id=proj.uuid
    )
    assert isinstance(output, list)
    assert len(output) <= len(
        comp_tasks
    )  # output doesn't contain e.g. filepickers and dynamic services
    assert all(isinstance(elm, TaskLogFileIdGet) for elm in output)


async def test_get_computation_task_log_file_ids_no_pipeline(
    rpc_client: RabbitMQRPCClient,
):
    with pytest.raises(ComputationalTaskMissingError):
        await rpc_computations_tasks.get_computation_task_log_file_ids(
            rpc_client, project_id=ProjectID(_faker.uuid4())
        )
