# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import aioredis

async def test_aioredis(loop, redis_client):
    await redis_client.set('my-key', 'value')
    val = await redis_client.get('my-key')
    assert val == 'value'

