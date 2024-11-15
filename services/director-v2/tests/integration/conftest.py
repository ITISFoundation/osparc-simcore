# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from unittest.mock import AsyncMock

import httpx
import pytest
import sqlalchemy as sa
from models_library.api_schemas_directorv2.comp_tasks import ComputationGet
from models_library.projects import ProjectAtDB
from models_library.users import UserID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.models.projects import projects
from starlette import status
from tenacity import retry
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL


@pytest.fixture
def mock_env(mock_env: EnvVarsDict, minio_s3_settings_envs: EnvVarsDict) -> EnvVarsDict:
    # overwrite to add minio real settings
    return mock_env


@pytest.fixture
def update_project_workbench_with_comp_tasks(
    postgres_db: sa.engine.Engine,
) -> Callable:
    def updator(project_uuid: str):
        with postgres_db.connect() as con:
            result = con.execute(
                projects.select().where(projects.c.uuid == project_uuid)
            )
            prj_row = result.first()
            assert prj_row
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

    return updator


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

        computation_task = ComputationGet.model_validate(response.json())
        created_comp_tasks.append((user_id, computation_task))
        return computation_task

    yield _creator

    # cleanup the pipelines
    responses: list[httpx.Response] = await asyncio.gather(
        *(
            async_client.request(
                "DELETE", f"{task.url}", json={"user_id": user_id, "force": True}
            )
            for user_id, task in created_comp_tasks
        )
    )
    assert all(isinstance(r.raise_for_status(), httpx.Response) for r in responses)


@pytest.fixture
def mock_projects_repository(mocker: MockerFixture) -> None:
    mocked_obj = AsyncMock()
    mocked_obj.is_node_present_in_workbench(return_value=True)

    module_base = "simcore_service_director_v2.modules.db.repositories.projects"
    mocker.patch(
        f"{module_base}.ProjectsRepository.is_node_present_in_workbench",
        return_value=mocked_obj,
    )


@pytest.fixture
async def wait_for_catalog_service(
    services_endpoint: dict[str, URL]
) -> Callable[[UserID, str], Awaitable[None]]:
    async def _waiter(user_id: UserID, product_name: str) -> None:
        catalog_endpoint = list(
            filter(
                lambda service_endpoint: "catalog" in service_endpoint[0],
                services_endpoint.items(),
            )
        )
        assert (
            len(catalog_endpoint) == 1
        ), f"no catalog service found! {services_endpoint=}"
        catalog_endpoint = catalog_endpoint[0][1]
        print(f"--> found catalog endpoint at {catalog_endpoint=}")
        client = httpx.AsyncClient()

        @retry(
            wait=wait_fixed(1),
            stop=stop_after_delay(60),
            retry=retry_if_exception_type(AssertionError)
            | retry_if_exception_type(httpx.HTTPError),
        )
        async def _ensure_catalog_services_answers() -> None:
            print("--> checking catalog is up and ready...")
            response = await client.get(
                f"{catalog_endpoint}/v0/services",
                params={"details": False, "user_id": user_id},
                headers={"x-simcore-products-name": product_name},
                timeout=1,
            )
            assert (
                response.status_code == status.HTTP_200_OK
            ), f"catalog is not ready {response.status_code}:{response.text}, TIP: migration not completed or catalog broken?"
            services = response.json()
            assert services != [], "catalog is not ready: no services available"
            print(
                f"<-- catalog is up and ready, received {response.status_code}:{response.text}"
            )

        await _ensure_catalog_services_answers()

    return _waiter
