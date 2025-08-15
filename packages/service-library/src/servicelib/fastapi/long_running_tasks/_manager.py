import datetime

from fastapi import FastAPI
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings

from ...long_running_tasks import lrt_api
from ...long_running_tasks.base_long_running_manager import BaseLongRunningManager
from ...long_running_tasks.models import RabbitNamespace
from ...long_running_tasks.task import RedisNamespace, TasksManager
from ...rabbitmq._client_rpc import RabbitMQRPCClient


class FastAPILongRunningManager(BaseLongRunningManager):
    def __init__(
        self,
        app: FastAPI,
        stale_task_check_interval: datetime.timedelta,
        stale_task_detect_timeout: datetime.timedelta,
        redis_settings: RedisSettings,
        rabbit_settings: RabbitSettings,
        redis_namespace: RedisNamespace,
        rabbit_namespace: RabbitNamespace,
    ):
        self._app = app
        self._tasks_manager = TasksManager(
            stale_task_check_interval=stale_task_check_interval,
            stale_task_detect_timeout=stale_task_detect_timeout,
            redis_settings=redis_settings,
            redis_namespace=redis_namespace,
        )
        self._rabbit_namespace = rabbit_namespace
        self.rabbit_settings = rabbit_settings
        self._rpc_server: RabbitMQRPCClient | None = None
        self._rpc_client: RabbitMQRPCClient | None = None

    @property
    def tasks_manager(self) -> TasksManager:
        return self._tasks_manager

    @property
    def rpc_server(self) -> RabbitMQRPCClient:
        assert self._rpc_server is not None  # nosec
        return self._rpc_server

    @property
    def rpc_client(self) -> RabbitMQRPCClient:
        assert self._rpc_client is not None  # nosec
        return self._rpc_client

    @property
    def rabbit_namespace(self) -> str:
        return self._rabbit_namespace

    async def setup(self) -> None:
        await self._tasks_manager.setup()
        self._rpc_server = await RabbitMQRPCClient.create(
            client_name=f"lrt-server-{self.rabbit_namespace}",
            settings=self.rabbit_settings,
        )
        self._rpc_client = await RabbitMQRPCClient.create(
            client_name=f"lrt-client-{self.rabbit_namespace}",
            settings=self.rabbit_settings,
        )
        await lrt_api.register_rabbit_routes(self)

    async def teardown(self) -> None:
        await self._tasks_manager.teardown()

        if self._rpc_server is not None:
            await self._rpc_server.close()
            self._rpc_server = None

        if self._rpc_client is not None:
            await self._rpc_client.close()
            self._rpc_client = None
