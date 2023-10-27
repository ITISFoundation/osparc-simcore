# pylint:disable=redefined-outer-name

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest
import redis.asyncio as aioredis
from faker import Faker
from servicelib.osparc_resource_manager import (
    BaseResourceHandler,
    OsparcResoruceManager,
    OsparcResourceType,
    ResourceIdentifier,
    _get_key_resource_name,
)
from servicelib.redis import RedisClientSDK
from servicelib.utils import logged_gather
from settings_library.redis import RedisDatabase, RedisSettings

pytest_simcore_core_services_selection = [
    "redis",
]

pytest_simcore_ops_services_selection = [
    # "redis-commander",
]


@pytest.fixture
async def redis_client_sdk(
    redis_service: RedisSettings,
) -> AsyncIterator[RedisClientSDK]:
    redis_resources_dns = redis_service.build_redis_dsn(RedisDatabase.DYNAMIC_RESOURCES)
    client = RedisClientSDK(redis_resources_dns)
    assert client
    assert client.redis_dsn == redis_resources_dns
    await client.redis.flushall()
    await client.setup()

    yield client
    # cleanup, properly close the clients
    await client.redis.flushall()
    await client.shutdown()


@pytest.fixture
def resource_identifier(faker: Faker) -> ResourceIdentifier:
    return faker.pystr()


async def _is_key_present(redis: aioredis.Redis, key: str) -> bool:
    return await redis.get(key) is not None


async def test_workflow_resource_is_tracked(
    redis_client_sdk: RedisClientSDK, resource_identifier: ResourceIdentifier
):
    # setup oSPARC resource manager for handling a resource of type service
    manager = OsparcResoruceManager(redis_client_sdk=redis_client_sdk)

    resource_key = _get_key_resource_name(
        OsparcResourceType.DYNAMIC_SERVICE, resource_identifier
    )

    # resource does not exit
    assert not await _is_key_present(redis_client_sdk.redis, resource_key)
    await manager.add(
        OsparcResourceType.DYNAMIC_SERVICE, identifier=resource_identifier
    )

    # resource is now present
    assert await _is_key_present(redis_client_sdk.redis, resource_key)

    # check to ss
    assert await manager.get_resources(OsparcResourceType.DYNAMIC_SERVICE) == {
        resource_identifier
    }

    # resource was removed
    await manager.remove(
        OsparcResourceType.DYNAMIC_SERVICE, identifier=resource_identifier
    )
    assert not await _is_key_present(redis_client_sdk.redis, resource_key)


@pytest.mark.parametrize("concurrent_requests", [1, 2, 100])
async def test_workflow_resource_tracked_and_is_crated_then_destroyed_in_external_system(
    redis_client_sdk: RedisClientSDK,
    resource_identifier: ResourceIdentifier,
    concurrent_requests: int,
):
    @dataclass
    class ExternalSystemAPI:
        identifiers: dict[str, str] = field(default_factory=dict)

        def create(self, identifier: str, letter_count: int) -> None:
            self.identifiers[identifier] = "a" * letter_count

        def exists(self, identifier: str) -> bool:
            return identifier in self.identifiers

        def remove(self, identifier: str) -> None:
            del self.identifiers[identifier]

    class ExternalSystemResourceHandler(BaseResourceHandler):
        def __init__(self, api: ExternalSystemAPI) -> None:
            self.api = api

        async def is_present(self, identifier: ResourceIdentifier) -> bool:
            return self.api.exists(identifier)

        async def destroy(self, identifier: ResourceIdentifier) -> None:
            self.api.remove(identifier)

        # NOTE: here is how we customize the constructor to use additional parameters
        async def create(  # pylint: disable=arguments-differ
            self, identifier: ResourceIdentifier, letter_count: int
        ) -> None:
            self.api.create(identifier, letter_count)

    manager = OsparcResoruceManager(redis_client_sdk=redis_client_sdk)

    external_api = ExternalSystemAPI()
    manager.register(
        OsparcResourceType.DYNAMIC_SERVICE,
        resource_handler=ExternalSystemResourceHandler(api=external_api),
    )

    # not possible to create a resource without specifying the additional defined kwargs
    with pytest.raises(TypeError, match="required positional argument"):
        await manager.add(
            OsparcResourceType.DYNAMIC_SERVICE,
            identifier=resource_identifier,
            create=True,
        )

    async def _resource_exists(identifier: ResourceIdentifier) -> bool:
        return external_api.exists(identifier) and await _is_key_present(
            redis_client_sdk.redis,
            _get_key_resource_name(OsparcResourceType.DYNAMIC_SERVICE, identifier),
        )

    assert not await _resource_exists(resource_identifier)

    await logged_gather(
        *(
            manager.add(
                OsparcResourceType.DYNAMIC_SERVICE,
                identifier=resource_identifier,
                create=True,
                letter_count=10,
            )
            for _ in range(concurrent_requests)
        )
    )

    assert await _resource_exists(resource_identifier)

    await logged_gather(
        *(
            manager.remove(
                OsparcResourceType.DYNAMIC_SERVICE,
                identifier=resource_identifier,
                destroy=True,
            )
            for _ in range(concurrent_requests)
        )
    )

    assert not await _resource_exists(resource_identifier)


@pytest.fixture
def resource_identifiers(faker: Faker) -> set[ResourceIdentifier]:
    return {faker.pystr() for _ in range(100)}


async def test_remove_not_present_resources(
    redis_client_sdk: RedisClientSDK, resource_identifiers: list[ResourceIdentifier]
):
    class MockedExternalAPI:
        def __init__(self) -> None:
            self.reply_as_present: bool = True

        def is_present(self, _: ResourceIdentifier) -> bool:
            return self.reply_as_present

    # pylint: disable=abstract-method
    class ExternalSystemResourceHandler(BaseResourceHandler):
        def __init__(self, external_api: MockedExternalAPI) -> None:
            self.external_api: MockedExternalAPI = external_api

        async def is_present(self, identifier: ResourceIdentifier) -> bool:
            return self.external_api.is_present(identifier)

    mocked_api = MockedExternalAPI()

    manager = OsparcResoruceManager(redis_client_sdk=redis_client_sdk)

    manager.register(
        OsparcResourceType.DYNAMIC_SERVICE,
        resource_handler=ExternalSystemResourceHandler(external_api=mocked_api),
    )

    await logged_gather(
        *(
            manager.add(OsparcResourceType.DYNAMIC_SERVICE, identifier=identifier)
            for identifier in resource_identifiers
        )
    )

    assert (
        await manager.get_resources(OsparcResourceType.DYNAMIC_SERVICE)
        == resource_identifiers
    )

    # simulate resources are no longer present in the system
    mocked_api.reply_as_present = False

    await manager.remove_all_not_present_resources()

    # no more resources are tracked by the system
    assert await manager.get_resources(OsparcResourceType.DYNAMIC_SERVICE) == set()
