import asyncio
from typing import AsyncIterator, Awaitable, Callable, Iterator

import httpx
import pytest
import sqlalchemy as sa
from models_library.projects import ProjectAtDB
from models_library.users import UserID
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.models.projects import projects
from simcore_service_director_v2.models.schemas.comp_tasks import ComputationGet
from starlette import status


@pytest.fixture
def update_project_workbench_with_comp_tasks(
    postgres_db: sa.engine.Engine,
) -> Iterator[Callable]:
    def updator(project_uuid: str):
        with postgres_db.connect() as con:
            result = con.execute(
                projects.select().where(projects.c.uuid == project_uuid)
            )
            prj_row = result.first()
            prj_workbench = prj_row.workbench

            result = con.execute(
                comp_tasks.select().where(comp_tasks.c.project_id == project_uuid)
            )
            # let's get the results and run_hash
            for task_row in result:
                # pass these to the project workbench
                prj_workbench[task_row.node_id]["outputs"] = task_row.outputs
                prj_workbench[task_row.node_id]["runHash"] = task_row.run_hash

            con.execute(
                projects.update()  # pylint:disable=no-value-for-parameter
                .values(workbench=prj_workbench)
                .where(projects.c.uuid == project_uuid)
            )

    yield updator


@pytest.fixture(scope="session")
def osparc_product_name() -> str:
    # NOTE: this is the default the catalog currently uses
    return "osparc"


COMPUTATION_URL: str = "v2/computations"


@pytest.fixture
async def create_pipeline(
    async_client: httpx.AsyncClient,
) -> AsyncIterator[Callable[..., Awaitable[ComputationGet]]]:
    created_comp_tasks: list[tuple[UserID, ComputationGet]] = []

    async def _creator(
        client: httpx.AsyncClient,
        *,
        project: ProjectAtDB,
        user_id: UserID,
        product_name: str,
        start_pipeline: bool,
        **kwargs,
    ) -> ComputationGet:
        response = await client.post(
            COMPUTATION_URL,
            json={
                "user_id": user_id,
                "project_id": str(project.uuid),
                "start_pipeline": start_pipeline,
                "product_name": product_name,
                **kwargs,
            },
        )
        response.raise_for_status()
        assert response.status_code == status.HTTP_201_CREATED

        computation_task = ComputationGet.parse_obj(response.json())
        created_comp_tasks.append((user_id, computation_task))
        return computation_task

    yield _creator

    # cleanup the pipelines
    responses: list[httpx.Response] = await asyncio.gather(
        *(
            async_client.request(
                "DELETE", task.url, json={"user_id": user_id, "force": True}
            )
            for user_id, task in created_comp_tasks
        )
    )
    assert all(r.raise_for_status() is None for r in responses)
