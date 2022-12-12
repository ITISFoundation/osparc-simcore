from pytest_mock.plugin import MockerFixture
from simcore_service_autoscaling.modules.docker import AutoscalingDocker


async def test_docker_client():
    client = AutoscalingDocker()
    assert await client.ping() is True


async def test_docker_client_ping_with_no_connection(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_autoscaling.modules.docker.AutoscalingDocker.version",
        autospec=True,
        side_effect=RuntimeError,
    )
    client = AutoscalingDocker()
    assert await client.ping() is False
