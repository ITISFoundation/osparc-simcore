# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from fastapi import FastAPI
from simcore_service_autoscaling.modules.redis import get_redis_client


async def test_redis_raises_if_missing(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
):
    client = get_redis_client(initialized_app)
    assert await client.ping() is True
