# pylint:disable=unused-argument

import docker
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings
from tenacity.asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "redis",
]


# NOTE: keep this test ONLY tes tin the file!
# It breaks the service `redis` from `pytest_simcore_core_services_selection`
# since the service is being removed.
async def test_redis_client_sdk_lost_connection(
    mock_redis_socket_timeout: None,
    redis_service: RedisSettings,
    docker_client: docker.client.DockerClient,
):
    redis_client_sdk = RedisClientSDK(
        redis_service.build_redis_dsn(RedisDatabase.RESOURCES), client_name="pytest"
    )
    assert redis_client_sdk.client_name == "pytest"
    await redis_client_sdk.setup()

    assert await redis_client_sdk.ping() is True
    # now let's put down the rabbit service
    for rabbit_docker_service in (
        docker_service
        for docker_service in docker_client.services.list()
        if "redis" in docker_service.name  # type: ignore
    ):
        rabbit_docker_service.remove()  # type: ignore

    # check that connection was lost
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(60), wait=wait_fixed(0.5), reraise=True
    ):
        with attempt:
            assert await redis_client_sdk.ping() is False

    await redis_client_sdk.shutdown()
