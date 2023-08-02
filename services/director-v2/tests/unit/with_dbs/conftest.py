# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


import datetime
import json
from typing import Any, Awaitable, Callable, Iterator
from uuid import uuid4

import pytest
import sqlalchemy as sa
from _helpers import PublishedProject, RunningProject
from models_library.clusters import Cluster
from models_library.projects import ProjectAtDB
from models_library.projects_nodes_io import NodeID
from pydantic.main import BaseModel
from simcore_postgres_database.models.cluster_to_groups import cluster_to_groups
from simcore_postgres_database.models.clusters import clusters
from simcore_postgres_database.models.comp_pipeline import StateType, comp_pipeline
from simcore_postgres_database.models.comp_runs import comp_runs
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB, Image
from simcore_service_director_v2.utils.computations import to_node_class
from simcore_service_director_v2.utils.dask import generate_dask_job_id
from simcore_service_director_v2.utils.db import to_clusters_db
from sqlalchemy.dialects.postgresql import insert as pg_insert


@pytest.fixture
def pipeline(
    postgres_db: sa.engine.Engine,
) -> Iterator[Callable[..., CompPipelineAtDB]]:
    created_pipeline_ids: list[str] = []

    def creator(**pipeline_kwargs) -> CompPipelineAtDB:
        pipeline_config = {
            "project_id": f"{uuid4()}",
            "dag_adjacency_list": {},
            "state": StateType.NOT_STARTED,
        }
        pipeline_config.update(**pipeline_kwargs)
        with postgres_db.begin() as conn:
            result = conn.execute(
                comp_pipeline.insert()
                .values(**pipeline_config)
                .returning(sa.literal_column("*"))
            )
            assert result

            new_pipeline = CompPipelineAtDB.from_orm(result.first())
            created_pipeline_ids.append(f"{new_pipeline.project_id}")
            return new_pipeline

    yield creator

    # cleanup
    with postgres_db.connect() as conn:
        conn.execute(
            comp_pipeline.delete().where(
                comp_pipeline.c.project_id.in_(created_pipeline_ids)
            )
        )


@pytest.fixture
def tasks(
    postgres_db: sa.engine.Engine,
) -> Iterator[Callable[..., list[CompTaskAtDB]]]:
    created_task_ids: list[int] = []

    def creator(
        user: dict[str, Any], project: ProjectAtDB, **overrides_kwargs
    ) -> list[CompTaskAtDB]:
        created_tasks: list[CompTaskAtDB] = []
        for internal_id, (node_id, node_data) in enumerate(project.workbench.items()):
            task_config = {
                "project_id": f"{project.uuid}",
                "node_id": f"{node_id}",
                "schema": {"inputs": {}, "outputs": {}},
                "inputs": {
                    key: json.loads(value.json(by_alias=True, exclude_unset=True))
                    if isinstance(value, BaseModel)
                    else value
                    for key, value in node_data.inputs.items()
                }
                if node_data.inputs
                else {},
                "outputs": {
                    key: json.loads(value.json(by_alias=True, exclude_unset=True))
                    if isinstance(value, BaseModel)
                    else value
                    for key, value in node_data.outputs.items()
                }
                if node_data.outputs
                else {},
                "image": Image(name=node_data.key, tag=node_data.version).dict(  # type: ignore
                    by_alias=True, exclude_unset=True
                ),  # type: ignore
                "node_class": to_node_class(node_data.key),
                "internal_id": internal_id + 1,
                "submit": datetime.datetime.now(tz=datetime.timezone.utc),
                "job_id": generate_dask_job_id(
                    service_key=node_data.key,
                    service_version=node_data.version,
                    user_id=user["id"],
                    project_id=project.uuid,
                    node_id=NodeID(node_id),
                ),
            }
            task_config.update(**overrides_kwargs)
            with postgres_db.connect() as conn:
                result = conn.execute(
                    comp_tasks.insert()
                    .values(**task_config)
                    .returning(sa.literal_column("*"))
                )
                new_task = CompTaskAtDB.from_orm(result.first())
                created_tasks.append(new_task)
            created_task_ids.extend([t.task_id for t in created_tasks if t.task_id])
        return created_tasks

    yield creator

    # cleanup
    with postgres_db.connect() as conn:
        conn.execute(
            comp_tasks.delete().where(comp_tasks.c.task_id.in_(created_task_ids))
        )


@pytest.fixture
def runs(postgres_db: sa.engine.Engine) -> Iterator[Callable[..., CompRunsAtDB]]:
    created_run_ids: list[int] = []

    def creator(
        user: dict[str, Any], project: ProjectAtDB, **run_kwargs
    ) -> CompRunsAtDB:
        run_config = {
            "project_uuid": f"{project.uuid}",
            "user_id": f"{user['id']}",
            "iteration": 1,
            "result": StateType.NOT_STARTED,
        }
        run_config.update(**run_kwargs)
        with postgres_db.connect() as conn:
            result = conn.execute(
                comp_runs.insert()
                .values(**run_config)
                .returning(sa.literal_column("*"))
            )
            new_run = CompRunsAtDB.from_orm(result.first())
            created_run_ids.append(new_run.run_id)
            return new_run

    yield creator

    # cleanup
    with postgres_db.connect() as conn:
        conn.execute(comp_runs.delete().where(comp_runs.c.run_id.in_(created_run_ids)))


@pytest.fixture
def cluster(
    postgres_db: sa.engine.Engine,
) -> Iterator[Callable[..., Cluster]]:
    created_cluster_ids: list[str] = []

    def creator(user: dict[str, Any], **cluster_kwargs) -> Cluster:
        cluster_config = Cluster.Config.schema_extra["examples"][1]
        cluster_config["owner"] = user["primary_gid"]
        cluster_config.update(**cluster_kwargs)
        new_cluster = Cluster.parse_obj(cluster_config)
        assert new_cluster

        with postgres_db.connect() as conn:
            # insert basic cluster
            created_cluster = conn.execute(
                sa.insert(clusters)
                .values(to_clusters_db(new_cluster, only_update=False))
                .returning(sa.literal_column("*"))
            ).one()
            created_cluster_ids.append(created_cluster.id)
            if "access_rights" in cluster_kwargs:
                for gid, rights in cluster_kwargs["access_rights"].items():
                    conn.execute(
                        pg_insert(cluster_to_groups)
                        .values(cluster_id=created_cluster.id, gid=gid, **rights.dict())
                        .on_conflict_do_update(
                            index_elements=["gid", "cluster_id"], set_=rights.dict()
                        )
                    )
            access_rights_in_db = {}
            for row in conn.execute(
                sa.select(
                    cluster_to_groups.c.gid,
                    cluster_to_groups.c.read,
                    cluster_to_groups.c.write,
                    cluster_to_groups.c.delete,
                )
                .select_from(clusters.join(cluster_to_groups))
                .where(clusters.c.id == created_cluster.id)
            ):
                access_rights_in_db[row.gid] = {
                    "read": row[cluster_to_groups.c.read],
                    "write": row[cluster_to_groups.c.write],
                    "delete": row[cluster_to_groups.c.delete],
                }

            return Cluster(
                id=created_cluster.id,
                name=created_cluster.name,
                description=created_cluster.description,
                type=created_cluster.type,
                owner=created_cluster.owner,
                endpoint=created_cluster.endpoint,
                authentication=created_cluster.authentication,
                access_rights=access_rights_in_db,
                thumbnail=None,
            )

    yield creator

    # cleanup
    with postgres_db.connect() as conn:
        conn.execute(
            # pylint: disable=no-value-for-parameter
            clusters.delete().where(clusters.c.id.in_(created_cluster_ids))
        )


@pytest.fixture
async def published_project(
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    pipeline: Callable[..., CompPipelineAtDB],
    tasks: Callable[..., list[CompTaskAtDB]],
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
) -> PublishedProject:
    user = registered_user()
    created_project = await project(user, workbench=fake_workbench_without_outputs)
    return PublishedProject(
        project=created_project,
        pipeline=pipeline(
            project_id=f"{created_project.uuid}",
            dag_adjacency_list=fake_workbench_adjacency,
        ),
        tasks=tasks(user=user, project=created_project, state=StateType.PUBLISHED),
    )


@pytest.fixture
async def running_project(
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    pipeline: Callable[..., CompPipelineAtDB],
    tasks: Callable[..., list[CompTaskAtDB]],
    runs: Callable[..., CompRunsAtDB],
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
) -> RunningProject:
    user = registered_user()
    created_project = await project(user, workbench=fake_workbench_without_outputs)
    return RunningProject(
        project=created_project,
        pipeline=pipeline(
            project_id=f"{created_project.uuid}",
            dag_adjacency_list=fake_workbench_adjacency,
        ),
        tasks=tasks(
            user=user, project=created_project, state=StateType.RUNNING, progress=0.0
        ),
        runs=runs(user=user, project=created_project, result=StateType.RUNNING),
    )
