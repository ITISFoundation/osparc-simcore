from typing import Final

from servicelib.long_running_tasks import lrt_api
from servicelib.long_running_tasks.base_long_running_manager import (
    BaseLongRunningManager,
)
from servicelib.long_running_tasks.models import RabbitNamespace
from servicelib.long_running_tasks.task import TasksManager
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings


class NoWebAppLongRunningManager(BaseLongRunningManager):
    def __init__(
        self,
        tasks_manager: TasksManager,
        rabbit_settings: RabbitSettings,
        rabbit_namespace: RabbitNamespace,
    ):
        self._tasks_manager = tasks_manager

        self._rabbit_namespace = rabbit_namespace
        self.rabbit_settings = rabbit_settings
        self._rpc_server: RabbitMQRPCClient | None = None

    @property
    def tasks_manager(self) -> TasksManager:
        return self._tasks_manager

    @property
    def rpc_server(self):
        assert self._rpc_server is not None  # nosec
        return self._rpc_server

    @property
    def rabbit_namespace(self) -> str:
        return self._rabbit_namespace

    async def setup(self) -> None:
        self._rpc_server = await RabbitMQRPCClient.create(
            client_name=f"lrt-{self.rabbit_namespace}", settings=self.rabbit_settings
        )
        await lrt_api.register_rabbit_routes(self)

    async def teardown(self) -> None:
        if self._rpc_server is not None:
            await self._rpc_server.close()
            self._rpc_server = None


TEST_CHECK_STALE_INTERVAL_S: Final[float] = 1
