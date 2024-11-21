# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from random import choice
from typing import Any, AsyncIterator, Callable, get_args
from unittest import mock

import pytest
from _dask_helpers import DaskGatewayServer
from common_library.json_serialization import json_dumps
from common_library.serialization import model_dump_with_secrets
from distributed.deploy.spec import SpecCluster
from faker import Faker
from models_library.clusters import (
    DEFAULT_CLUSTER_ID,
    Cluster,
    ClusterAuthentication,
    ClusterTypeInModel,
    JupyterHubTokenAuthentication,
    KerberosAuthentication,
    NoAuthentication,
    SimpleAuthentication,
)
from pydantic import SecretStr
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.clusters import ClusterType
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.errors import (
    ConfigurationError,
    DaskClientAcquisisitonError,
)
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.modules.dask_clients_pool import DaskClientsPool
from starlette.testclient import TestClient


@pytest.fixture
def minimal_dask_config(
    disable_postgres: None,
    mock_env: EnvVarsDict,
    project_env_devel_environment: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """set a minimal configuration for testing the dask connection only"""
    monkeypatch.setenv("DIRECTOR_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SIDECAR_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V0_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_CATALOG", "null")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "1")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_ENABLED", "0")
    monkeypatch.setenv("SC_BOOT_MODE", "production")


def test_dask_clients_pool_missing_raises_configuration_error(
    minimal_dask_config: None, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "0")
    settings = AppSettings.create_from_envs()
    app = init_app(settings)

    with TestClient(app, raise_server_exceptions=True) as client:
        with pytest.raises(ConfigurationError):
            DaskClientsPool.instance(client.app)


def test_dask_clients_pool_properly_setup_and_deleted(
    minimal_dask_config: None, mocker: MockerFixture
):
    mocked_dask_clients_pool = mocker.patch(
        "simcore_service_director_v2.modules.dask_clients_pool.DaskClientsPool",
        autospec=True,
    )
    mocked_dask_clients_pool.create.return_value = mocked_dask_clients_pool
    settings = AppSettings.create_from_envs()
    app = init_app(settings)

    with TestClient(app, raise_server_exceptions=True) as client:
        mocked_dask_clients_pool.create.assert_called_once()
    mocked_dask_clients_pool.delete.assert_called_once()


@pytest.fixture
def fake_clusters(faker: Faker) -> Callable[[int], list[Cluster]]:
    def creator(num_clusters: int) -> list[Cluster]:
        fake_clusters = []
        for n in range(num_clusters):
            fake_clusters.append(
                Cluster.model_validate(
                    {
                        "id": faker.pyint(),
                        "name": faker.name(),
                        "type": ClusterType.ON_PREMISE,
                        "owner": faker.pyint(),
                        "endpoint": faker.uri(),
                        "authentication": choice(
                            [
                                NoAuthentication(),
                                SimpleAuthentication(
                                    username=faker.user_name(),
                                    password=faker.password(),
                                ),
                                KerberosAuthentication(),
                                JupyterHubTokenAuthentication(api_token=faker.uuid4()),
                            ]
                        ),
                    }
                )
            )
        return fake_clusters

    return creator


@pytest.fixture()
def default_scheduler_set_as_osparc_gateway(
    local_dask_gateway_server: DaskGatewayServer,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
) -> Callable:
    def creator():
        monkeypatch.setenv(
            "COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL",
            local_dask_gateway_server.proxy_address,
        )
        monkeypatch.setenv(
            "COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_AUTH",
            json_dumps(
                model_dump_with_secrets(
                    SimpleAuthentication(
                        username=faker.user_name(),
                        password=SecretStr(local_dask_gateway_server.password),
                    ),
                    show_secrets=True,
                )
            ),
        )

    return creator


@pytest.fixture()
def default_scheduler_set_as_dask_scheduler(
    dask_spec_local_cluster: SpecCluster, monkeypatch: pytest.MonkeyPatch
) -> Callable:
    def creator():
        monkeypatch.setenv(
            "COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL",
            dask_spec_local_cluster.scheduler_address,
        )

    return creator


@pytest.fixture(
    params=[
        "default_scheduler_set_as_dask_scheduler",
        "default_scheduler_set_as_osparc_gateway",
    ]
)
def default_scheduler(
    default_scheduler_set_as_dask_scheduler,
    default_scheduler_set_as_osparc_gateway,
    request,
):
    {
        "default_scheduler_set_as_dask_scheduler": default_scheduler_set_as_dask_scheduler,
        "default_scheduler_set_as_osparc_gateway": default_scheduler_set_as_osparc_gateway,
    }[request.param]()


async def test_dask_clients_pool_acquisition_creates_client_on_demand(
    minimal_dask_config: None,
    mocker: MockerFixture,
    client: TestClient,
    fake_clusters: Callable[[int], list[Cluster]],
):
    assert client.app
    mocked_dask_client = mocker.patch(
        "simcore_service_director_v2.modules.dask_clients_pool.DaskClient",
        autospec=True,
    )
    mocked_dask_client.create.return_value = mocked_dask_client
    clients_pool = DaskClientsPool.instance(client.app)
    mocked_dask_client.create.assert_not_called()
    mocked_dask_client.register_handlers.assert_not_called()

    clusters = fake_clusters(30)
    mocked_creation_calls = []
    for cluster in clusters:
        mocked_creation_calls.append(
            mock.call(
                app=client.app,
                settings=client.app.state.settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND,
                authentication=cluster.authentication,
                endpoint=cluster.endpoint,
                tasks_file_link_type=client.app.state.settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND.COMPUTATIONAL_BACKEND_DEFAULT_FILE_LINK_TYPE,
                cluster_type=ClusterTypeInModel.ON_PREMISE,
            )
        )
        async with clients_pool.acquire(cluster):
            # on start it is created
            mocked_dask_client.create.assert_has_calls(mocked_creation_calls)

        async with clients_pool.acquire(cluster):
            # the connection already exists, so there is no new call to create
            mocked_dask_client.create.assert_has_calls(mocked_creation_calls)

    # now let's delete the pool, this will trigger deletion of all the clients
    await clients_pool.delete()
    mocked_deletion_calls = [mock.call()] * len(clusters)
    mocked_dask_client.delete.assert_has_calls(mocked_deletion_calls)


async def test_acquiring_wrong_cluster_raises_exception(
    minimal_dask_config: None,
    mocker: MockerFixture,
    client: TestClient,
    fake_clusters: Callable[[int], list[Cluster]],
):
    mocked_dask_client = mocker.patch(
        "simcore_service_director_v2.modules.dask_clients_pool.DaskClient",
        autospec=True,
    )
    mocked_dask_client.create.side_effect = Exception
    clients_pool = DaskClientsPool.instance(client.app)
    mocked_dask_client.assert_not_called()

    non_existing_cluster = fake_clusters(1)[0]
    with pytest.raises(DaskClientAcquisisitonError):
        async with clients_pool.acquire(non_existing_cluster):
            ...


def test_default_cluster_correctly_initialized(
    minimal_dask_config: None, default_scheduler: None, client: TestClient
):
    dask_scheduler_settings = (
        client.app.state.settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND
    )
    default_cluster = dask_scheduler_settings.default_cluster
    assert default_cluster
    assert (
        default_cluster.endpoint
        == dask_scheduler_settings.COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL
    )

    assert default_cluster.id == DEFAULT_CLUSTER_ID
    assert isinstance(default_cluster.authentication, get_args(ClusterAuthentication))


@pytest.fixture()
async def dask_clients_pool(
    minimal_dask_config: None,
    default_scheduler,
    client: TestClient,
) -> AsyncIterator[DaskClientsPool]:
    clients_pool = DaskClientsPool.instance(client.app)
    assert clients_pool
    yield clients_pool
    await clients_pool.delete()


async def test_acquire_default_cluster(
    dask_clients_pool: DaskClientsPool,
    client: TestClient,
):
    assert client.app
    dask_scheduler_settings = (
        client.app.state.settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND
    )
    default_cluster = dask_scheduler_settings.default_cluster
    assert default_cluster
    async with dask_clients_pool.acquire(default_cluster) as dask_client:

        def just_a_quick_fct(x, y):
            return x + y

        assert (
            dask_client.tasks_file_link_type
            == client.app.state.settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND.COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_FILE_LINK_TYPE
        )
        future = dask_client.backend.client.submit(just_a_quick_fct, 12, 23)
        assert future
        result = await future.result(timeout=10)
    assert result == 35
