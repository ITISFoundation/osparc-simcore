# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments

import datetime as dt
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from fastapi import status
from models_library.api_schemas_directorv2.computations import ComputationGet
from models_library.projects import ProjectAtDB
from models_library.projects_state import RunningState
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_get_computation_does_not_expose_stopped_timestamp_until_run_is_completed(
    minimal_configuration: None,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks_from_project: Callable[..., Awaitable[list[CompTaskAtDB]]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    async_client: httpx.AsyncClient,
):
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    started_at = dt.datetime.now(tz=dt.UTC)
    stopped_at = started_at + dt.timedelta(seconds=1)

    await create_pipeline(
        project_id=f"{proj.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    await create_tasks_from_project(
        user=user,
        project=proj,
        state=StateType.SUCCESS,
        progress=1,
        start=started_at,
        end=stopped_at,
    )
    await create_comp_run(
        user=user,
        project=proj,
        result=StateType.RUNNING,
        started=started_at,
        dag_adjacency_list=fake_workbench_adjacency,
    )

    get_computation_url = httpx.URL(f"/v2/computations/{proj.uuid}?user_id={user['id']}")
    response = await async_client.get(get_computation_url)

    assert response.status_code == status.HTTP_200_OK, response.text
    returned_computation = ComputationGet.model_validate(response.json())
    assert returned_computation.state == RunningState.STARTED
    assert returned_computation.started == started_at
    assert returned_computation.pipeline_details.progress == 1
    assert {node_state.current_status for node_state in returned_computation.pipeline_details.node_states.values()} == {
        RunningState.SUCCESS
    }
    assert returned_computation.stopped is None


async def test_get_computation_uses_comp_run_timestamps_for_top_level_lifecycle(
    minimal_configuration: None,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks_from_project: Callable[..., Awaitable[list[CompTaskAtDB]]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    async_client: httpx.AsyncClient,
):
    user = create_registered_user()
    proj = await create_project(user, workbench=fake_workbench_without_outputs)
    started_at = dt.datetime.now(tz=dt.UTC)
    task_stopped_at = started_at + dt.timedelta(seconds=1)
    run_stopped_at = started_at + dt.timedelta(seconds=2)

    await create_pipeline(
        project_id=f"{proj.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    await create_tasks_from_project(
        user=user,
        project=proj,
        state=StateType.SUCCESS,
        progress=1,
        start=started_at,
        end=task_stopped_at,
    )
    await create_comp_run(
        user=user,
        project=proj,
        result=StateType.SUCCESS,
        started=started_at,
        ended=run_stopped_at,
        dag_adjacency_list=fake_workbench_adjacency,
    )

    get_computation_url = httpx.URL(f"/v2/computations/{proj.uuid}?user_id={user['id']}")
    response = await async_client.get(get_computation_url)

    assert response.status_code == status.HTTP_200_OK, response.text
    returned_computation = ComputationGet.model_validate(response.json())
    assert returned_computation.state == RunningState.SUCCESS
    assert returned_computation.started == started_at
    assert returned_computation.stopped == run_stopped_at
    assert returned_computation.stopped != task_stopped_at
