from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings

from ..deferred_tasks import BaseDeferredHandler
from ._job_scheduler import JobScheduler


class RpcJobScheduler:
    def __init__(
        self, rabbit_settings: RabbitSettings, redis_settings: RedisSettings
    ) -> None:
        self._scheduler = JobScheduler(get_redis_client(redis_settings))

    async def register_deferred_task(self, deferred_taask: type[BaseDeferredHandler]):
        pass

    async def setup(self) -> None:
        await self._scheduler.setup()

    async def shutdown(self) -> None:
        await self._scheduler.shutdown()
