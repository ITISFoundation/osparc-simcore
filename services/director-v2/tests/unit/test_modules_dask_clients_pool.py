# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from random import choice
from typing import Any, AsyncIterator, Callable, Dict, List, get_args
from unittest import mock

import pytest
from _dask_helpers import DaskGatewayServer
from _pytest.monkeypatch import MonkeyPatch
from faker import Faker
from models_library.clusters import (
    Cluster,
    ClusterAuthentication,
    JupyterHubTokenAuthentication,
    KerberosAuthentication,
    NoAuthentication,
    SimpleAuthentication,
)
from pydantic import SecretStr
from pytest_mock.plugin import MockerFixture
from settings_library.utils_cli import create_json_encoder_wo_secrets
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
    mock_env: None,
    project_env_devel_environment: Dict[str, Any],
    monkeypatch: MonkeyPatch,
) -> None:
    """set a minimal configuration for testing the dask connection only"""
    monkeypatch.setenv("DIRECTOR_ENABLED", "0")
    monkeypatch.setenv("POSTGRES_ENABLED", "0")
    monkeypatch.setenv("REGISTRY_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SIDECAR_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V0_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "1")
    monkeypatch.setenv("DIRECTOR_V2_DASK_SCHEDULER_ENABLED", "0")
    monkeypatch.setenv("SC_BOOT_MODE", "production")


def test_dask_clients_pool_missing_raises_configuration_error(
    minimal_dask_config: None, monkeypatch: MonkeyPatch
):
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "0")
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
def fake_clusters(faker: Faker) -> Callable[[int], List[Cluster]]:
    def creator(num_clusters: int) -> List[Cluster]:
        fake_clusters = []
        for n in range(num_clusters):
            fake_clusters.append(
                Cluster.parse_obj(
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


async def test_dask_clients_pool_acquisition_creates_client_on_demand(
    minimal_dask_config: None,
    mocker: MockerFixture,
    client: TestClient,
    fake_clusters: Callable[[int], List[Cluster]],
):
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
                settings=client.app.state.settings.DASK_SCHEDULER,
                authentication=cluster.authentication,
                endpoint=cluster.endpoint,
            )
        )
        async with clients_pool.acquire(cluster) as dask_client:
            # on start it is created
            mocked_dask_client.create.assert_has_calls(mocked_creation_calls)

        async with clients_pool.acquire(cluster) as dask_client:
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
    fake_clusters: Callable[[int], List[Cluster]],
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


@pytest.fixture()
def default_scheduler_as_dask_scheduler(monkeypatch: MonkeyPatch, faker: Faker):
    def creator():
        monkeypatch.setenv("DIRECTOR_V2_DEFAULT_SCHEDULER_URL", faker.uri())

    return creator


@pytest.fixture()
def default_scheduler_as_dask_gateway(monkeypatch: MonkeyPatch, faker: Faker):
    def creator():
        monkeypatch.setenv("DIRECTOR_V2_DEFAULT_SCHEDULER_URL", faker.uri())
        monkeypatch.setenv(
            "DIRECTOR_V2_DEFAULT_SCHEDULER_AUTH",
            SimpleAuthentication(
                username=faker.user_name(), password=faker.password()
            ).json(),
        )

    return creator


@pytest.fixture(
    params=["default_scheduler_as_dask_scheduler", "default_scheduler_as_dask_gateway"]
)
def default_scheduler(
    default_scheduler_as_dask_scheduler, default_scheduler_as_dask_gateway, request
):
    {
        "default_scheduler_as_dask_scheduler": default_scheduler_as_dask_scheduler,
        "default_scheduler_as_dask_gateway": default_scheduler_as_dask_gateway,
    }[request.param]()


def test_default_cluster_correctly_initialized(
    minimal_dask_config: None, default_scheduler, client: TestClient
):
    dask_scheduler_settings = client.app.state.settings.DASK_SCHEDULER
    default_cluster = DaskClientsPool.default_cluster(dask_scheduler_settings)
    assert default_cluster
    assert (
        default_cluster.endpoint
        == dask_scheduler_settings.DIRECTOR_V2_DEFAULT_SCHEDULER_URL
    )

    assert default_cluster.id == dask_scheduler_settings.DIRECTOR_V2_DEFAULT_CLUSTER_ID
    assert isinstance(default_cluster.authentication, get_args(ClusterAuthentication))


@pytest.fixture()
def default_scheduler_set_as_osparc_gateway(
    local_dask_gateway_server: DaskGatewayServer, monkeypatch: MonkeyPatch, faker: Faker
):
    monkeypatch.setenv(
        "DIRECTOR_V2_DEFAULT_SCHEDULER_URL", local_dask_gateway_server.proxy_address
    )
    monkeypatch.setenv(
        "DIRECTOR_V2_DEFAULT_SCHEDULER_AUTH",
        SimpleAuthentication(
            username=faker.user_name(),
            password=SecretStr(local_dask_gateway_server.password),
        ).json(encoder=create_json_encoder_wo_secrets(SimpleAuthentication)),
    )


@pytest.fixture()
async def dask_clients_pool(
    minimal_dask_config: None,
    default_scheduler_set_as_osparc_gateway,
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
    dask_scheduler_settings = client.app.state.settings.DASK_SCHEDULER
    default_cluster = DaskClientsPool.default_cluster(dask_scheduler_settings)
    assert default_cluster
    async with dask_clients_pool.acquire(default_cluster) as dask_client:

        def just_a_quick_fct(x, y):
            return x + y

        future = dask_client.dask_subsystem.client.submit(just_a_quick_fct, 12, 23)
        assert future
        result = await future.result(timeout=10)
    assert result == 35
