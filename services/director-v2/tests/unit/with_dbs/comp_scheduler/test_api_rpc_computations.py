# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-positional-arguments

from collections.abc import Awaitable, Callable
from typing import Any

from models_library.api_schemas_directorv2.comp_runs import ComputationRunRpcGetPage
from models_library.projects import ProjectAtDB
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.director_v2 import (
    computations as rpc_computations,
)
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]
pytest_simcore_ops_services_selection = [
    "adminer",
]


# @pytest.fixture()
# def minimal_configuration(
#     mock_env: EnvVarsDict,
#     postgres_host_config: dict[str, str],
#     rabbit_service: RabbitSettings,
#     redis_service: RedisSettings,
#     monkeypatch: pytest.MonkeyPatch,
#     faker: Faker,
#     with_disabled_auto_scheduling: mock.Mock,
#     with_disabled_scheduler_publisher: mock.Mock,
# ):
#     monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SIDECAR_ENABLED", "false")
#     monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "1")
#     monkeypatch.setenv("COMPUTATIONAL_BACKEND_ENABLED", "1")
#     monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
#     monkeypatch.setenv("S3_ENDPOINT", faker.url())
#     monkeypatch.setenv("S3_ACCESS_KEY", faker.pystr())
#     monkeypatch.setenv("S3_REGION", faker.pystr())
#     monkeypatch.setenv("S3_SECRET_KEY", faker.pystr())
#     monkeypatch.setenv("S3_BUCKET_NAME", faker.pystr())


async def test_get_computation_from_published_computation_task(
    # minimal_configuration: None,
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_adjacency: dict[str, Any],
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[CompPipelineAtDB]],
    create_tasks: Callable[..., Awaitable[list[CompTaskAtDB]]],
    create_comp_run: Callable[..., Awaitable[CompRunsAtDB]],
    # async_client: httpx.AsyncClient,
    rpc_client: RabbitMQRPCClient,
):
    user = registered_user()
    proj = await project(user, workbench=fake_workbench_without_outputs)
    await create_pipeline(
        project_id=f"{proj.uuid}",
        dag_adjacency_list=fake_workbench_adjacency,
    )
    comp_tasks = await create_tasks(
        user=user, project=proj, state=StateType.PUBLISHED, progress=0
    )
    comp_runs = await create_comp_run(
        user=user, project=proj, result=StateType.PUBLISHED
    )
    assert comp_runs

    output = await rpc_computations.list_computations_latest_iteration_page(
        rpc_client, product_name="osparc", user_id=user["id"]
    )
    assert output.total == 1
    assert isinstance(output, ComputationRunRpcGetPage)

    # get_computation_url = httpx.URL(
    #     f"/v2/computations/{proj.uuid}?user_id={user['id']}"
    # )
    # response = await async_client.get(get_computation_url)
    # assert response.status_code == status.HTTP_200_OK, response.text
    # returned_computation = ComputationGet.model_validate(response.json())
    # assert returned_computation
    # expected_stop_url = async_client.base_url.join(
    #     f"/v2/computations/{proj.uuid}:stop?user_id={user['id']}"
    # )
