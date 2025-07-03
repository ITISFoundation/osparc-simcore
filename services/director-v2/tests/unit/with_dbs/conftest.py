# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


import datetime
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, cast

import arrow
import pytest
import sqlalchemy as sa
from _helpers import CompRunSnapshotTaskAtDBGet, PublishedProject, RunningProject
from dask_task_models_library.container_tasks.utils import generate_dask_job_id
from faker import Faker
from fastapi.encoders import jsonable_encoder
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import PositiveInt
from pydantic.main import BaseModel
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_run_snapshot_tasks import (
    comp_run_snapshot_tasks,
)
from simcore_postgres_database.models.comp_runs import comp_runs
from simcore_postgres_database.models.comp_tasks import NodeClass
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_runs import (
    CompRunsAtDB,
    ProjectMetadataDict,
    RunMetadataDict,
)
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB, Image
from simcore_service_director_v2.utils.computations import to_node_class
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
async def create_pipeline(
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
) -> Callable[..., Awaitable[CompPipelineAtDB]]:
    async def _(**pipeline_kwargs) -> CompPipelineAtDB:
        created_pipeline_dict = await create_pipeline(**pipeline_kwargs)
        return CompPipelineAtDB.model_validate(created_pipeline_dict)

    return _


@pytest.fixture
async def create_tasks_from_project(
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
) -> Callable[..., Awaitable[list[CompTaskAtDB]]]:
    async def _(
        user: dict[str, Any], project: ProjectAtDB, **overrides_kwargs
    ) -> list[CompTaskAtDB]:
        created_tasks: list[CompTaskAtDB] = []
        for internal_id, (node_id, node_data) in enumerate(project.workbench.items()):
            task_config = {
                "project_id": f"{project.uuid}",
                "node_id": f"{node_id}",
                "schema": {"inputs": {}, "outputs": {}},
                "inputs": (
                    {
                        key: (
                            value.model_dump(
                                mode="json", by_alias=True, exclude_unset=True
                            )
                            if isinstance(value, BaseModel)
                            else value
                        )
                        for key, value in node_data.inputs.items()
                    }
                    if node_data.inputs
                    else {}
                ),
                "outputs": (
                    {
                        key: (
                            value.model_dump(
                                mode="json", by_alias=True, exclude_unset=True
                            )
                            if isinstance(value, BaseModel)
                            else value
                        )
                        for key, value in node_data.outputs.items()
                    }
                    if node_data.outputs
                    else {}
                ),
                "image": Image(name=node_data.key, tag=node_data.version).model_dump(
                    by_alias=True, exclude_unset=True
                ),
                "node_class": to_node_class(node_data.key),
                "internal_id": internal_id + 1,
                "job_id": generate_dask_job_id(
                    service_key=node_data.key,
                    service_version=node_data.version,
                    user_id=user["id"],
                    project_id=project.uuid,
                    node_id=NodeID(node_id),
                ),
            }
            task_config.update(**overrides_kwargs)
            task_dict = await create_comp_task(**task_config)
            new_task = CompTaskAtDB.model_validate(task_dict)
            created_tasks.append(new_task)
        return created_tasks

    return _


@pytest.fixture
def project_metadata(faker: Faker) -> ProjectMetadataDict:
    return ProjectMetadataDict(
        parent_node_id=cast(NodeID, faker.uuid4(cast_to=None)),
        parent_node_name=faker.pystr(),
        parent_project_id=cast(ProjectID, faker.uuid4(cast_to=None)),
        parent_project_name=faker.pystr(),
        root_parent_project_id=cast(ProjectID, faker.uuid4(cast_to=None)),
        root_parent_project_name=faker.pystr(),
        root_parent_node_id=cast(NodeID, faker.uuid4(cast_to=None)),
        root_parent_node_name=faker.pystr(),
    )


@pytest.fixture
def run_metadata(
    osparc_product_name: str,
    simcore_user_agent: str,
    project_metadata: ProjectMetadataDict,
    faker: Faker,
) -> RunMetadataDict:
    return RunMetadataDict(
        node_id_names_map={},
        project_name=faker.name(),
        product_name=osparc_product_name,
        simcore_user_agent=simcore_user_agent,
        user_email=faker.email(),
        wallet_id=faker.pyint(min_value=1),
        wallet_name=faker.name(),
        project_metadata=project_metadata,
    )


@pytest.fixture
async def create_comp_run(
    sqlalchemy_async_engine: AsyncEngine, run_metadata: RunMetadataDict
) -> AsyncIterator[Callable[..., Awaitable[CompRunsAtDB]]]:
    created_run_ids: list[int] = []

    async def _(
        user: dict[str, Any], project: ProjectAtDB, **run_kwargs
    ) -> CompRunsAtDB:
        run_config = {
            "project_uuid": f"{project.uuid}",
            "user_id": user["id"],
            "iteration": 1,
            "result": StateType.NOT_STARTED,
            "metadata": jsonable_encoder(run_metadata),
            "use_on_demand_clusters": False,
            "dag_adjacency_list": {},
        }
        run_config.update(**run_kwargs)
        async with sqlalchemy_async_engine.begin() as conn:
            result = await conn.execute(
                comp_runs.insert()
                .values(**run_config)
                .returning(sa.literal_column("*"))
            )
            new_run = CompRunsAtDB.model_validate(result.first())
            created_run_ids.append(new_run.run_id)
            return new_run

    yield _

    # cleanup
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_runs.delete().where(comp_runs.c.run_id.in_(created_run_ids))
        )


@pytest.fixture
async def create_comp_run_snapshot_tasks(
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[Callable[..., Awaitable[list[CompRunSnapshotTaskAtDBGet]]]]:
    created_task_ids: list[int] = []

    async def _(
        user: dict[str, Any],
        project: ProjectAtDB,
        run_id: PositiveInt,
        **overrides_kwargs,
    ) -> list[CompRunSnapshotTaskAtDBGet]:
        created_run_snapshot_tasks: list[CompRunSnapshotTaskAtDBGet] = []
        for internal_id, (node_id, node_data) in enumerate(project.workbench.items()):
            if to_node_class(node_data.key) != NodeClass.COMPUTATIONAL:
                continue

            task_config = {
                "run_id": run_id,  # <-- this is the run_id from comp_runs
                "project_id": f"{project.uuid}",
                "node_id": f"{node_id}",
                "schema": {"inputs": {}, "outputs": {}},
                "inputs": (
                    {
                        key: (
                            value.model_dump(
                                mode="json", by_alias=True, exclude_unset=True
                            )
                            if isinstance(value, BaseModel)
                            else value
                        )
                        for key, value in node_data.inputs.items()
                    }
                    if node_data.inputs
                    else {}
                ),
                "outputs": (
                    {
                        key: (
                            value.model_dump(
                                mode="json", by_alias=True, exclude_unset=True
                            )
                            if isinstance(value, BaseModel)
                            else value
                        )
                        for key, value in node_data.outputs.items()
                    }
                    if node_data.outputs
                    else {}
                ),
                "image": Image(name=node_data.key, tag=node_data.version).model_dump(
                    by_alias=True, exclude_unset=True
                ),
                "node_class": to_node_class(node_data.key),
                "internal_id": internal_id + 1,
                "job_id": generate_dask_job_id(
                    service_key=node_data.key,
                    service_version=node_data.version,
                    user_id=user["id"],
                    project_id=project.uuid,
                    node_id=NodeID(node_id),
                ),
            }
            task_config.update(**overrides_kwargs)
            async with sqlalchemy_async_engine.begin() as conn:
                result = await conn.execute(
                    comp_run_snapshot_tasks.insert()
                    .values(**task_config)
                    .returning(sa.literal_column("*"))
                )
                new_run_snapshot_task = CompRunSnapshotTaskAtDBGet.model_validate(
                    result.first()
                )
                created_run_snapshot_tasks.append(new_run_snapshot_task)
            created_task_ids.extend(
                [t.snapshot_task_id for t in created_run_snapshot_tasks]
            )
        return created_run_snapshot_tasks

    yield _

    # cleanup
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_run_snapshot_tasks.delete().where(
                comp_run_snapshot_tasks.c.snapshot_task_id.in_(created_task_ids)
            )
        )


@pytest.fixture
async def publish_project(
    create_registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks_from_project: Callable[..., Awaitable[list[CompTaskAtDB]]],
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
) -> Callable[[], Awaitable[PublishedProject]]:
    user = create_registered_user()

    async def _() -> PublishedProject:
        created_project = await project(user, workbench=fake_workbench_without_outputs)
        return PublishedProject(
            user=user,
            project=created_project,
            pipeline=await create_pipeline(
                project_id=f"{created_project.uuid}",
                dag_adjacency_list=fake_workbench_adjacency,
            ),
            tasks=await create_tasks_from_project(
                user=user, project=created_project, state=StateType.PUBLISHED
            ),
        )

    return _


@pytest.fixture
async def published_project(
    with_product: dict[str, Any],
    publish_project: Callable[[], Awaitable[PublishedProject]],
) -> PublishedProject:
    return await publish_project()


@pytest.fixture
async def running_project(
    with_product: dict[str, Any],
    create_registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks_from_project: Callable[..., Awaitable[list[CompTaskAtDB]]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    create_comp_run_snapshot_tasks: Callable[
        ..., Awaitable[list[CompRunSnapshotTaskAtDBGet]]
    ],
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
) -> RunningProject:
    user = create_registered_user()
    created_project = await project(user, workbench=fake_workbench_without_outputs)
    now_time = arrow.utcnow().datetime
    _comp_run = await create_comp_run(
        user=user,
        project=created_project,
        started=now_time,
        result=StateType.RUNNING,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    return RunningProject(
        user=user,
        project=created_project,
        pipeline=await create_pipeline(
            project_id=f"{created_project.uuid}",
            dag_adjacency_list=fake_workbench_adjacency,
        ),
        tasks=await create_tasks_from_project(
            user=user,
            project=created_project,
            state=StateType.RUNNING,
            progress=0.0,
            start=now_time,
        ),
        runs=_comp_run,
        runs_snapshot_tasks=await create_comp_run_snapshot_tasks(
            user=user,
            project=created_project,
            run_id=_comp_run.run_id,
            state=StateType.RUNNING,
            progress=0.0,
            start=now_time,
        ),
        task_to_callback_mapping={},
    )


@pytest.fixture
async def running_project_mark_for_cancellation(
    create_registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks_from_project: Callable[..., Awaitable[list[CompTaskAtDB]]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    create_comp_run_snapshot_tasks: Callable[
        ..., Awaitable[list[CompRunSnapshotTaskAtDBGet]]
    ],
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    with_product: dict[str, Any],
) -> RunningProject:
    user = create_registered_user()
    created_project = await project(user, workbench=fake_workbench_without_outputs)
    now_time = arrow.utcnow().datetime
    _comp_run = await create_comp_run(
        user=user,
        project=created_project,
        result=StateType.RUNNING,
        started=now_time,
        cancelled=now_time + datetime.timedelta(seconds=5),
        dag_adjacency_list=fake_workbench_adjacency,
    )
    return RunningProject(
        user=user,
        project=created_project,
        pipeline=await create_pipeline(
            project_id=f"{created_project.uuid}",
            dag_adjacency_list=fake_workbench_adjacency,
        ),
        tasks=await create_tasks_from_project(
            user=user,
            project=created_project,
            state=StateType.RUNNING,
            progress=0.0,
            start=now_time,
        ),
        runs=_comp_run,
        runs_snapshot_tasks=await create_comp_run_snapshot_tasks(
            user=user,
            project=created_project,
            run_id=_comp_run.run_id,
            state=StateType.RUNNING,
            progress=0.0,
            start=now_time,
        ),
        task_to_callback_mapping={},
    )


@pytest.fixture
def simcore_user_agent(faker: Faker) -> str:
    return faker.pystr()
