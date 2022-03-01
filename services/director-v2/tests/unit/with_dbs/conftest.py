# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


from typing import Any, Callable, Dict, List

import pytest
from _helpers import PublishedProject, RunningProject  # type: ignore
from models_library.projects import ProjectAtDB
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_service_director_v2.models.domains.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.domains.comp_runs import CompRunsAtDB
from simcore_service_director_v2.models.domains.comp_tasks import CompTaskAtDB


@pytest.fixture
def published_project(
    project: Callable[..., ProjectAtDB],
    pipeline: Callable[..., CompPipelineAtDB],
    tasks: Callable[..., List[CompTaskAtDB]],
    fake_workbench_without_outputs: Dict[str, Any],
    fake_workbench_adjacency: Dict[str, Any],
) -> PublishedProject:
    created_project = project(workbench=fake_workbench_without_outputs)
    return PublishedProject(
        project=created_project,
        pipeline=pipeline(
            project_id=f"{created_project.uuid}",
            dag_adjacency_list=fake_workbench_adjacency,
        ),
        tasks=tasks(project=created_project, state=StateType.PUBLISHED),
    )


@pytest.fixture
def running_project(
    project: Callable[..., ProjectAtDB],
    pipeline: Callable[..., CompPipelineAtDB],
    tasks: Callable[..., List[CompTaskAtDB]],
    runs: Callable[..., CompRunsAtDB],
    fake_workbench_without_outputs: Dict[str, Any],
    fake_workbench_adjacency: Dict[str, Any],
) -> RunningProject:
    created_project = project(workbench=fake_workbench_without_outputs)
    return RunningProject(
        project=created_project,
        pipeline=pipeline(
            project_id=f"{created_project.uuid}",
            dag_adjacency_list=fake_workbench_adjacency,
        ),
        tasks=tasks(project=created_project, state=StateType.RUNNING),
        runs=runs(project=created_project, result=StateType.RUNNING),
    )
