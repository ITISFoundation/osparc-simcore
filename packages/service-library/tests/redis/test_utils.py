# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


from faker import Faker
from servicelib.redis import RedisClientSDK, handle_redis_returns_union_types

pytest_simcore_core_services_selection = [
    "redis",
]

pytest_simcore_ops_services_selection = [
    "redis-commander",
]


async def test_handle_redis_returns_union_types(
    redis_client_sdk: RedisClientSDK, faker: Faker
):
    await handle_redis_returns_union_types(
        redis_client_sdk.redis.hset(
            faker.pystr(), mapping={faker.pystr(): faker.pystr()}
        )
    )
