# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=redefined-outer-name

import asyncio
import socket
from copy import deepcopy
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable
from unittest import mock

import aiodocker
import pytest
from dask_gateway_server.backends.db_base import Cluster, JobStatus
from faker import Faker
from osparc_gateway_server.backend.errors import NoHostFoundError
from osparc_gateway_server.backend.settings import AppSettings
from osparc_gateway_server.backend.utils import (
    _DASK_KEY_CERT_PATH_IN_SIDECAR,
    DockerSecret,
    create_or_update_secret,
    create_service_config,
    delete_secrets,
    get_cluster_information,
    get_network_id,
    get_next_empty_node_hostname,
    is_service_task_running,
)
from pytest_mock.plugin import MockerFixture
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed


@pytest.fixture
def minimal_config(monkeypatch):
    monkeypatch.setenv("GATEWAY_WORKERS_NETWORK", "atestnetwork")
    monkeypatch.setenv("GATEWAY_SERVER_NAME", "atestserver")
    monkeypatch.setenv("COMPUTATIONAL_SIDECAR_IMAGE", "test/localpytest:latest")
    monkeypatch.setenv(
        "COMPUTATIONAL_SIDECAR_VOLUME_NAME", "sidecar_computational_volume_name"
    )


@pytest.fixture()
async def create_docker_service(
    docker_swarm, async_docker_client: aiodocker.Docker, faker: Faker
) -> AsyncIterator[Callable[[dict[str, str]], Awaitable[dict[str, Any]]]]:
    created_services = []

    async def _creator(labels: dict[str, str]) -> dict[str, Any]:
        service = await async_docker_client.services.create(
            task_template={
                "ContainerSpec": {"Image": "busybox", "Command": ["sleep", "10000"]}
            },
            name=faker.pystr(),
            labels=labels,
        )
        assert service
        created_services.append(service)
        print(f"--> created docker service {service}")
        inspected_service = await async_docker_client.services.inspect(service["ID"])
        print(f"--> service inspected returned {inspected_service}")
        return inspected_service

    yield _creator

    await asyncio.gather(
        *[async_docker_client.services.delete(s["ID"]) for s in created_services]
    )


@pytest.fixture
def create_running_service(
    async_docker_client: aiodocker.Docker,
    create_docker_service: Callable[[dict[str, str]], Awaitable[dict[str, Any]]],
) -> Callable[[dict[str, str]], Awaitable[dict[str, Any]]]:
    async def _creator(labels: dict[str, str]) -> dict[str, Any]:
        service = await create_docker_service(labels)
        async for attempt in AsyncRetrying(
            reraise=True, wait=wait_fixed(1), stop=stop_after_delay(60)
        ):
            with attempt:
                tasks = await async_docker_client.tasks.list(
                    filters={"service": f"{service['Spec']['Name']}"}
                )
                task_states = [task["Status"]["State"] for task in tasks]
                num_running = sum(current == "running" for current in task_states)
                print(f"--> service task states {task_states=}")
                assert num_running == 1
                print(f"--> service {service['Spec']['Name']} is running now")
                return service
        raise AssertionError(f"service {service=} could not start")

    return _creator


@pytest.fixture
def mocked_logger(mocker: MockerFixture) -> mock.MagicMock:
    return mocker.MagicMock()


async def test_is_task_running(
    docker_swarm,
    minimal_config,
    async_docker_client: aiodocker.Docker,
    create_running_service: Callable[[dict[str, str]], Awaitable[dict[str, Any]]],
    mocked_logger: mock.MagicMock,
):
    service = await create_running_service({})
    # this service exists and run
    assert (
        await is_service_task_running(
            async_docker_client, service["Spec"]["Name"], mocked_logger
        )
        == True
    )

    # check unknown service raises error
    with pytest.raises(aiodocker.DockerError):
        await is_service_task_running(
            async_docker_client, "unknown_service", mocked_logger
        )


async def test_get_network_id(
    docker_swarm,
    async_docker_client: aiodocker.Docker,
    docker_network: Callable[..., Awaitable[dict[str, Any]]],
    mocked_logger: mock.MagicMock,
):
    # wrong name shall raise
    with pytest.raises(ValueError):
        await get_network_id(async_docker_client, "a_fake_network_name", mocked_logger)
    # create 1 bridge network, shall raise when looking for it
    bridge_network = await docker_network(**{"Driver": "bridge"})
    with pytest.raises(ValueError):
        await get_network_id(async_docker_client, bridge_network["Name"], mocked_logger)
    # create 1 overlay network
    overlay_network = await docker_network()
    network_id = await get_network_id(
        async_docker_client, overlay_network["Name"], mocked_logger
    )
    assert network_id == overlay_network["Id"]

    # create a second overlay network with the same name, shall raise on creation, so not possible
    with pytest.raises(aiodocker.exceptions.DockerError):
        await docker_network(**{"Name": overlay_network["Name"]})
    assert (
        True
    ), "If it is possible to have 2 networks with the same name, this must be handled"


@pytest.fixture
async def fake_cluster(faker: Faker) -> Cluster:
    return Cluster(id=faker.uuid4(), name=faker.pystr(), status=JobStatus.CREATED)


@pytest.fixture
async def docker_secret_cleaner(
    async_docker_client: aiodocker.Docker, fake_cluster: Cluster
) -> AsyncIterator:
    yield
    await delete_secrets(async_docker_client, fake_cluster)


async def test_create_service_config(
    docker_swarm,
    async_docker_client: aiodocker.Docker,
    minimal_config: None,
    faker: Faker,
    fake_cluster: Cluster,
    docker_secret_cleaner,
):
    # let's create some fake service config
    settings = AppSettings()  # type: ignore
    service_env = faker.pydict()
    service_name = faker.name()
    network_id = faker.uuid4()
    cmd = faker.pystr()
    fake_labels = faker.pydict()
    fake_placement = {"Constraints": [f"node.hostname=={faker.hostname()}"]}

    # create a second one
    secrets = [
        await create_or_update_secret(
            async_docker_client,
            faker.file_path(),
            fake_cluster,
            secret_data=faker.text(),
        )
        for n in range(3)
    ]

    assert len(await async_docker_client.secrets.list()) == 3

    # we shall have some env that tells the service where the secret is located
    expected_service_env = deepcopy(service_env)
    for s in secrets:
        fake_env_key = faker.pystr()
        service_env[fake_env_key] = s.secret_file_name
        expected_service_env[
            fake_env_key
        ] = f"{_DASK_KEY_CERT_PATH_IN_SIDECAR / Path(s.secret_file_name).name}"

    service_parameters = create_service_config(
        settings=settings,
        service_env=service_env,
        service_name=service_name,
        network_id=network_id,
        service_secrets=secrets,
        cmd=cmd,
        labels=fake_labels,
        placement=fake_placement,
    )
    assert service_parameters
    assert service_parameters["name"] == service_name
    assert network_id in service_parameters["networks"]

    for env_key, env_value in expected_service_env.items():
        assert env_key in service_parameters["task_template"]["ContainerSpec"]["Env"]
        assert (
            service_parameters["task_template"]["ContainerSpec"]["Env"][env_key]
            == env_value
        )
    assert service_parameters["task_template"]["ContainerSpec"]["Command"] == cmd
    assert service_parameters["labels"] == fake_labels
    assert len(service_parameters["task_template"]["ContainerSpec"]["Secrets"]) == 3
    for service_secret, original_secret in zip(
        service_parameters["task_template"]["ContainerSpec"]["Secrets"], secrets
    ):
        assert service_secret["SecretName"] == original_secret.secret_name
        assert service_secret["SecretID"] == original_secret.secret_id
        assert (
            service_secret["File"]["Name"]
            == f"{_DASK_KEY_CERT_PATH_IN_SIDECAR / Path(original_secret.secret_file_name).name}"
        )
    assert service_parameters["task_template"]["Placement"] == fake_placement


@pytest.fixture
def fake_secret_file(tmp_path) -> Path:
    fake_secret_file = Path(tmp_path / "fake_file")
    fake_secret_file.write_text("Hello I am a secret file")
    assert fake_secret_file.exists()
    return fake_secret_file


async def test_create_or_update_docker_secrets_with_invalid_call_raises(
    docker_swarm,
    async_docker_client: aiodocker.Docker,
    fake_cluster: Cluster,
    faker: Faker,
    docker_secret_cleaner,
):
    with pytest.raises(ValueError):
        await create_or_update_secret(
            async_docker_client,
            faker.file_path(),
            fake_cluster,
        )


async def test_create_or_update_docker_secrets(
    docker_swarm,
    async_docker_client: aiodocker.Docker,
    fake_secret_file: Path,
    fake_cluster: Cluster,
    faker: Faker,
    docker_secret_cleaner,
):
    list_of_secrets = await async_docker_client.secrets.list(
        filters={"label": f"cluster_id={fake_cluster.id}"}
    )
    assert len(list_of_secrets) == 0
    file_original_size = fake_secret_file.stat().st_size
    # check secret creation
    secret_target_file_name = faker.file_path()
    created_secret: DockerSecret = await create_or_update_secret(
        async_docker_client,
        secret_target_file_name,
        fake_cluster,
        file_path=fake_secret_file,
    )
    list_of_secrets = await async_docker_client.secrets.list(
        filters={"label": f"cluster_id={fake_cluster.id}"}
    )
    assert len(list_of_secrets) == 1
    secret = list_of_secrets[0]
    assert created_secret.secret_id == secret["ID"]
    inspected_secret = await async_docker_client.secrets.inspect(secret["ID"])

    assert created_secret.secret_name == inspected_secret["Spec"]["Name"]
    assert "cluster_id" in inspected_secret["Spec"]["Labels"]
    assert inspected_secret["Spec"]["Labels"]["cluster_id"] == fake_cluster.id
    assert "cluster_name" in inspected_secret["Spec"]["Labels"]
    assert inspected_secret["Spec"]["Labels"]["cluster_name"] == fake_cluster.name

    # check update of secret
    fake_secret_file.write_text("some additional stuff in the file")
    assert fake_secret_file.stat().st_size != file_original_size

    updated_secret: DockerSecret = await create_or_update_secret(
        async_docker_client,
        secret_target_file_name,
        fake_cluster,
        file_path=fake_secret_file,
    )
    assert updated_secret.secret_id != created_secret.secret_id
    secrets = await async_docker_client.secrets.list(
        filters={"label": f"cluster_id={fake_cluster.id}"}
    )
    assert len(secrets) == 1
    updated_secret = secrets[0]
    assert updated_secret != created_secret

    # create a second one
    secret_target_file_name2 = faker.file_path()
    created_secret: DockerSecret = await create_or_update_secret(
        async_docker_client,
        secret_target_file_name2,
        fake_cluster,
        secret_data=faker.text(),
    )
    secrets = await async_docker_client.secrets.list(
        filters={"label": f"cluster_id={fake_cluster.id}"}
    )
    assert len(secrets) == 2

    # test deletion
    await delete_secrets(async_docker_client, fake_cluster)
    secrets = await async_docker_client.secrets.list(
        filters={"label": f"cluster_id={fake_cluster.id}"}
    )
    assert len(secrets) == 0


async def test_get_cluster_information(
    docker_swarm,
    async_docker_client: aiodocker.Docker,
):
    cluster_information = await get_cluster_information(async_docker_client)
    assert cluster_information

    # in testing we do have 1 machine, that is... this very host
    assert len(cluster_information) == 1
    assert socket.gethostname() in cluster_information


@pytest.fixture()
def fake_docker_nodes(faker: Faker) -> list[dict[str, Any]]:
    return [
        {"ID": f"{faker.uuid4()}", "Description": {"Hostname": f"{faker.hostname()}"}},
        {"ID": f"{faker.uuid4()}", "Description": {"Hostname": f"{faker.hostname()}"}},
        {"ID": f"{faker.uuid4()}", "Description": {"Hostname": f"{faker.hostname()}"}},
    ]


@pytest.fixture()
def mocked_docker_nodes(mocker: MockerFixture, fake_docker_nodes):
    mocked_aiodocker_nodes = mocker.patch(
        "osparc_gateway_server.backend.utils.aiodocker.nodes.DockerSwarmNodes.list",
        autospec=True,
        return_value=fake_docker_nodes,
    )


async def test_get_empty_node_hostname_rotates_host_names(
    fake_docker_nodes: list[dict[str, Any]],
    mocked_docker_nodes,
    docker_swarm,
    async_docker_client: aiodocker.Docker,
    fake_cluster: Cluster,
):
    available_hostnames = [
        node["Description"]["Hostname"] for node in fake_docker_nodes
    ]
    num_nodes = len(fake_docker_nodes)
    for n in range(num_nodes):
        hostname = await get_next_empty_node_hostname(async_docker_client, fake_cluster)
        assert hostname in available_hostnames
        available_hostnames.pop(available_hostnames.index(hostname))
    # let's do it a second time, since it should again go over all the hosts
    available_hostnames = [
        node["Description"]["Hostname"] for node in fake_docker_nodes
    ]
    for n in range(num_nodes):
        hostname = await get_next_empty_node_hostname(async_docker_client, fake_cluster)
        assert hostname in available_hostnames
        available_hostnames.pop(available_hostnames.index(hostname))


async def test_get_empty_node_hostname_correctly_checks_services_labels(
    docker_swarm,
    async_docker_client: aiodocker.Docker,
    fake_cluster: Cluster,
    create_running_service,
):
    hostname = await get_next_empty_node_hostname(async_docker_client, fake_cluster)
    assert socket.gethostname() == hostname

    # only services with the required labels shall be used to find if a service is already on a machine
    invalid_labels = [
        # no labels
        {},
        # only one of the required label
        {
            "cluster_id": fake_cluster.id,
        },
        # only one of the required label
        {"type": "worker"},
    ]
    await asyncio.gather(*[create_running_service(labels=l) for l in invalid_labels])
    # these services have not the correct labels, so the host is still available
    hostname = await get_next_empty_node_hostname(async_docker_client, fake_cluster)
    assert socket.gethostname() == hostname

    # now create a service with the required labels
    required_labels = {"cluster_id": fake_cluster.id, "type": "worker"}
    await create_running_service(labels=required_labels)
    with pytest.raises(NoHostFoundError):
        await get_next_empty_node_hostname(async_docker_client, fake_cluster)
