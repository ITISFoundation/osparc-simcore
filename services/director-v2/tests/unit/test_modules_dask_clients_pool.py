# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from collections.abc import AsyncIterator, Callable
from pathlib import Path
from random import choice
from typing import Any, cast, get_args
from unittest import mock

import pytest
from distributed.deploy.spec import SpecCluster
from faker import Faker
from fastapi import FastAPI
from models_library.clusters import (
    BaseCluster,
    ClusterAuthentication,
    ClusterTypeInModel,
    NoAuthentication,
    TLSAuthentication,
)
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
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
    monkeypatch.setenv("DIRECTOR_ENABLED", "0")
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

    with TestClient(app, raise_server_exceptions=True):  # noqa: SIM117
        with pytest.raises(ConfigurationError):
            DaskClientsPool.instance(app)


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

    with TestClient(app, raise_server_exceptions=True):
        mocked_dask_clients_pool.create.assert_called_once()
    mocked_dask_clients_pool.delete.assert_called_once()


@pytest.fixture
def fake_clusters(faker: Faker) -> Callable[[int], list[BaseCluster]]:
    def creator(num_clusters: int) -> list[BaseCluster]:
        return [
            BaseCluster.model_validate(
                {
                    "id": faker.pyint(),
                    "name": faker.name(),
                    "type": ClusterTypeInModel.ON_PREMISE,
                    "owner": faker.pyint(),
                    "endpoint": faker.uri(),
                    "authentication": choice(  # noqa: S311
                        [
                            NoAuthentication(),
                            TLSAuthentication(
                                tls_client_cert=Path(faker.file_path()),
                                tls_client_key=Path(faker.file_path()),
                                tls_ca_file=Path(faker.file_path()),
                            ),
                        ]
                    ),
                }
            )
            for _n in range(num_clusters)
        ]

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
    ]
)
def default_scheduler(
    default_scheduler_set_as_dask_scheduler,
    request,
):
    {
        "default_scheduler_set_as_dask_scheduler": default_scheduler_set_as_dask_scheduler,
    }[request.param]()


async def test_dask_clients_pool_acquisition_creates_client_on_demand(
    minimal_dask_config: None,
    mocker: MockerFixture,
    client: TestClient,
    fake_clusters: Callable[[int], list[BaseCluster]],
):
    assert client.app
    the_app = cast(FastAPI, client.app)
    mocked_dask_client = mocker.patch(
        "simcore_service_director_v2.modules.dask_clients_pool.DaskClient",
        autospec=True,
    )
    mocked_dask_client.create.return_value = mocked_dask_client
    clients_pool = DaskClientsPool.instance(the_app)
    mocked_dask_client.create.assert_not_called()
    mocked_dask_client.register_handlers.assert_not_called()

    clusters = fake_clusters(30)
    mocked_creation_calls = []
    assert isinstance(the_app.state.settings, AppSettings)
    for cluster in clusters:
        mocked_creation_calls.append(
            mock.call(
                app=client.app,
                settings=the_app.state.settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND,
                authentication=cluster.authentication,
                endpoint=cluster.endpoint,
                tasks_file_link_type=the_app.state.settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND.COMPUTATIONAL_BACKEND_DEFAULT_FILE_LINK_TYPE,
                cluster_type=ClusterTypeInModel.ON_PREMISE,
            )
        )
        async with clients_pool.acquire(cluster, ref=f"test-ref-{cluster.name}"):
            # on start it is created
            mocked_dask_client.create.assert_has_calls(mocked_creation_calls)

        async with clients_pool.acquire(cluster, ref=f"test-ref-{cluster.name}-2"):
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
    fake_clusters: Callable[[int], list[BaseCluster]],
):
    assert client.app
    the_app = cast(FastAPI, client.app)
    mocked_dask_client = mocker.patch(
        "simcore_service_director_v2.modules.dask_clients_pool.DaskClient",
        autospec=True,
    )
    mocked_dask_client.create.side_effect = Exception
    clients_pool = DaskClientsPool.instance(the_app)
    mocked_dask_client.assert_not_called()

    non_existing_cluster = fake_clusters(1)[0]
    with pytest.raises(DaskClientAcquisisitonError):
        async with clients_pool.acquire(
            non_existing_cluster, ref="test-non-existing-ref"
        ):
            ...


def test_default_cluster_correctly_initialized(
    minimal_dask_config: None, default_scheduler: None, client: TestClient
):
    assert client.app
    the_app = cast(FastAPI, client.app)
    dask_scheduler_settings = the_app.state.settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND
    default_cluster = dask_scheduler_settings.default_cluster
    assert default_cluster
    assert (
        default_cluster.endpoint
        == dask_scheduler_settings.COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL
    )

    assert isinstance(default_cluster.authentication, get_args(ClusterAuthentication))


@pytest.fixture()
async def dask_clients_pool(
    minimal_dask_config: None,
    default_scheduler,
    client: TestClient,
) -> AsyncIterator[DaskClientsPool]:
    assert client.app
    the_app = cast(FastAPI, client.app)
    clients_pool = DaskClientsPool.instance(the_app)
    assert clients_pool
    yield clients_pool
    await clients_pool.delete()


async def test_acquire_default_cluster(
    dask_clients_pool: DaskClientsPool,
    client: TestClient,
):
    assert client.app
    the_app = cast(FastAPI, client.app)
    dask_scheduler_settings = the_app.state.settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND
    default_cluster = dask_scheduler_settings.default_cluster
    assert default_cluster
    async with dask_clients_pool.acquire(
        default_cluster, ref="test-default-cluster-ref"
    ) as dask_client:

        def just_a_quick_fct(x, y):
            return x + y

        assert (
            dask_client.tasks_file_link_type
            == the_app.state.settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND.COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_FILE_LINK_TYPE
        )
        future = dask_client.backend.client.submit(just_a_quick_fct, 12, 23)
        assert future
        result = await future.result(timeout=10)
    assert result == 35


async def test_dask_clients_pool_reference_counting(
    minimal_dask_config: None,
    mocker: MockerFixture,
    client: TestClient,
    fake_clusters: Callable[[int], list[BaseCluster]],
):
    """Test that the reference counting mechanism works correctly."""
    assert client.app
    the_app = cast(FastAPI, client.app)
    mocked_dask_client = mocker.patch(
        "simcore_service_director_v2.modules.dask_clients_pool.DaskClient",
        autospec=True,
    )
    mocked_dask_client.create.return_value = mocked_dask_client
    clients_pool = DaskClientsPool.instance(the_app)

    # Create a cluster
    cluster = fake_clusters(1)[0]

    # Acquire the client with first reference
    ref1 = "test-ref-1"
    async with clients_pool.acquire(cluster, ref=ref1):
        # Client should be created
        mocked_dask_client.create.assert_called_once()
        # Reset the mock to check the next call
        mocked_dask_client.create.reset_mock()

    mocked_dask_client.delete.assert_not_called()
    # Acquire the same client with second reference
    ref2 = "test-ref-2"
    async with clients_pool.acquire(cluster, ref=ref2):
        # No new client should be created
        mocked_dask_client.create.assert_not_called()
    mocked_dask_client.delete.assert_not_called()

    # Release first reference, client should still exist
    await clients_pool.release_client_ref(ref1)
    mocked_dask_client.delete.assert_not_called()

    # Release second reference, which should delete the client
    await clients_pool.release_client_ref(ref2)
    mocked_dask_client.delete.assert_called_once()

    # calling again should not raise and not delete more
    await clients_pool.release_client_ref(ref2)
    mocked_dask_client.delete.assert_called_once()

    # Acquire again should create a new client
    mocked_dask_client.create.reset_mock()
    async with clients_pool.acquire(cluster, ref="test-ref-3"):
        mocked_dask_client.create.assert_called_once()
