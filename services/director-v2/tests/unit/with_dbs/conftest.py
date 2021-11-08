from dataclasses import dataclass
from typing import Any, Callable, Dict, List

import pytest
from models_library.projects import ProjectAtDB
from models_library.projects_state import RunningState
from simcore_service_director_v2.models.domains.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.domains.comp_tasks import CompTaskAtDB


@dataclass
class PublishedProject:
    project: ProjectAtDB
    pipeline: CompPipelineAtDB
    tasks: List[CompTaskAtDB]


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
        tasks=tasks(project=created_project, state=RunningState.PUBLISHED),
    )
