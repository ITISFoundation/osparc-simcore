from dataclasses import dataclass, field

from settings_library.redis import RedisDatabase, RedisSettings

from ._client import RedisClientSDK
from ._models import RedisManagerDBConfig


@dataclass
class RedisClientsManager:
    """
    Manages the lifetime of redis client sdk connections
    """

    databases_configs: set[RedisManagerDBConfig]
    settings: RedisSettings
    client_name: str

    _client_sdks: dict[RedisDatabase, RedisClientSDK] = field(default_factory=dict)

    async def setup(self) -> None:
        for config in self.databases_configs:
            self._client_sdks[config.database] = RedisClientSDK(
                redis_dsn=self.settings.build_redis_dsn(config.database),
                decode_responses=config.decode_responses,
                health_check_interval=config.health_check_interval,
                client_name=f"{self.client_name}",
            )

        for client in self._client_sdks.values():
            await client.setup()

    async def shutdown(self) -> None:
        # NOTE: somehow using logged_gather is not an option
        # doing so will make the shutdown procedure hang
        for client in self._client_sdks.values():
            await client.shutdown()

    def client(self, database: RedisDatabase) -> RedisClientSDK:
        return self._client_sdks[database]

    async def __aenter__(self) -> "RedisClientsManager":
        await self.setup()
        return self

    async def __aexit__(self, *args) -> None:
        await self.shutdown()
