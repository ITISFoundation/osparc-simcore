import redis.asyncio as aioredis

from ._models import Announcement


async def list_announcements(redis_client: aioredis.Redis) -> list[Announcement]:
    hash_key = "announcements"
    print(hash_key)
    raw_announcements: list[str] = await redis_client.get(hash_key)
    print(raw_announcements)
    return []
    # return [Announcement.parse_raw(x) for x in raw_announcements]
